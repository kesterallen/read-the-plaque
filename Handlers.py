# -*- coding: utf-8 -*-

import datetime
import jinja2
import json
import logging
import math
import mimetypes
import os
import random
import re
import urllib
import webapp2

from google.appengine.api import images
from google.appengine.api import mail
from google.appengine.api import memcache
from google.appengine.api import search 
from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from google.appengine.ext.db import BadValueError

import lib.cloudstorage as gcs

from Models import Comment, Plaque

ADMIN_EMAIL = 'kester+readtheplaque@gmail.com'
NOTIFICATION_SENDER_EMAIL = ADMIN_EMAIL

# TODO before go-live
# * Search for plaque text and title
# * Make plaque submission require login
#       possibly multiple OAUTH login
# * GPS picker for submission location
# * Change .net to .com for final deploy

# The wordpress admin dashboard is pretty easy to use and the process to
# publish pending the pending plaques is straightforward.
#
# Here is my proposed plan of action:
#
# 0) Disable comments entirely. They appear to be at least 99.9% spam, with
#    over twenty thousand pending comments.
# 1) Publish the ~200 pending plaque posts. This will take a couple months at
#    the level of effort that I can give to this.
# 2) Go through the ~100 plaques on the #readtheplaque hashtag, post those.
# 3) Copy all of the data from the wordpress site to my revamp of the site.
#    Verify that the data is identical.
# 4) Switch the domain to point to the new site.
# 5) Announce a relauch of the site, from both Roman and Alexis


# GCS_BUCKET configuration: This appears to work for the bucket named
# 'read-the-plaque.appspot.com', but it is different from surlyfritter. I
# suspect I did something different/wrong in the setup, but not sure.
#
GCS_BUCKET = '/read-the-plaque.appspot.com'

DEFAULT_PLAQUESET_NAME = 'public'
DEFAULT_PLAQUES_PER_PAGE = 24

# Load templates from the /templates dir. Check if this works on deploy
JINJA_ENVIRONMENT = jinja2.Environment (
    loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__),
                     'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=False)#True) # turn off autoescape to allow html redering of descriptions

# Set a parent key on the Plaque objects to ensure that they are all in the
# same entity group. Queries across the single entity group will be consistent.
# However, the write rate should be limited to ~1/second.

def plaqueset_key(plaqueset_name=DEFAULT_PLAQUESET_NAME):
    """
    Constructs a Datastore key for a Plaque entity. Use plaqueset_name as
    the key.
    """
    return ndb.Key('Plaque', plaqueset_name)

def last_five_approved(cls):
    new_items = cls.query(cls.approved == True
                  ).order(-cls.created_on
                  ).fetch(limit=5)
    return new_items

def get_pages_list(plaques_per_page=DEFAULT_PLAQUES_PER_PAGE):
    num_pages = int(math.ceil(float(Plaque.num_approved()) /
                              float(plaques_per_page)))
    pages_list = [1+p for p in range(num_pages)]
    return pages_list

def get_footer_items():
    """
    Just 5 tags for the footer.
    Memcache the output of this so it doesn't get calculated every time.
    """
    footer_items = memcache.get('get_footer_items')
    if footer_items is None:
        tags = set()
        for p in Plaque.query(Plaque.approved == True).fetch():
            for t in p.tags:
                tags.add(t)
        while len(tags) > 5:
            tags.pop()

        footer_items = {'tags': tags,
                        'new_plaques': last_five_approved(Plaque),
                        'new_comments': last_five_approved(Comment)}

        memcache_status = memcache.set('get_footer_items', footer_items)
        if not memcache_status:
            logging.debug("memcaching for get_footer_items failed")
    else:
        logging.debug("memcache.get worked for get_footer_items")

    return footer_items

class ViewPlaquesPage(webapp2.RequestHandler):
    def get(self, page_num=1, plaques_per_page=DEFAULT_PLAQUES_PER_PAGE):
        """
        View the nth plaques_per_page plaques on a grid.
        page_num is a one-based integer
        """
        try:
            page_num = int(page_num)
        except ValueError as err:
            logging.error(err)
            page_num = 1
        if page_num < 1:
            page_num = 1

        try:
            plaques_per_page = int(plaques_per_page)
        except ValueError as err:
            logging.error(err)
            plaques_per_page = DEFAULT_PLAQUES_PER_PAGE
        if plaques_per_page < 1:
            plaques_per_page = 1


        # Grab all plaques for the map
        plaques = Plaque.all_approved()
        start_index = plaques_per_page * (page_num - 1)
        end_index = start_index + plaques_per_page 

        template = JINJA_ENVIRONMENT.get_template('all.html')
        template_values = {
            'all_plaques': plaques,
            'plaques': plaques,
            'pages_list': get_pages_list(),
            'start_index': start_index,
            'end_index': end_index, 
            'mapzoom': 2,
            'footer_items': get_footer_items(),
        }

        memcache_name = 'view_plaques_page_%s_%s' % (page_num, plaques_per_page)
        template_text = memcache.get(memcache_name)
        if template_text is None:
            template_text = template.render(template_values)
            memcache_status = memcache.set(memcache_name, template_text)
            if not memcache_status:
                logging.debug("memcaching for ViewPlaquesPage failed")
        else:
            logging.debug("memcaching worked for ViewPlaquesPage")

        self.response.write(template_text)

class ViewOnePlaqueParent(webapp2.RequestHandler):
    def get(self):
        raise NotImplementedError("Don't call ViewOnePlaqueParent.get directly")

    def _random_plaque_key(self):
        logging.debug("Neither comment_key nor plaque_key is specified. "
                      "Grab a random plaque.")
        count = Plaque.query().count()
        if not count:
            raise ValueError("No plaques!")

        iplaque = random.randint(1, count)
        plaques = Plaque.query().order(Plaque.created_on).fetch(offset=iplaque,
                                                                limit=1)
        plaque_key = plaques[0].key.urlsafe()
        return plaque_key

    def _get_from_key(self, comment_key=None, plaque_key=None):
        """
        Put the single plaque into a list for rendering so that the common
        map functionality can be used unchanged.
        """
        if comment_key is not None:
            comment = ndb.Key(urlsafe=comment_key).get()
            plaque = Plaque.query().filter(Plaque.approved == True
                                  ).filter(Plaque.comments == comment.key
                                  ).get()
        elif plaque_key is not None:
            plaque = ndb.Key(urlsafe=plaque_key).get()
        else:
        #TODO: put plaque-from-title logic here
            logging.debug("Neither comment_key nor plaque_key is specified. "
                          "Grab a random plaque.")
            key = self._random_plaque_key()
            self.redirect('/plaque/' + key)
            return

        template = JINJA_ENVIRONMENT.get_template('one.html')
        template_values = {
            'all_plaques': [plaque],
            'plaques': [plaque],
            'pages_list': get_pages_list(),
            'mapzoom': 8,
            'footer_items': get_footer_items(),
        }
        self.response.write(template.render(template_values))

class ViewOnePlaqueFromComment(ViewOnePlaqueParent):
    """
    Render the single-plaque page from a comment key.
    """
    def get(self, comment_key):
        self._get_from_key(comment_key=comment_key)

class JsonOnePlaque(ViewOnePlaqueParent):
    """
    Render the single-plaque page from a plaque key, or get a random plaque.
    """
    def get(self, plaque_key=None):
        if plaque_key is None:
            plaque_key = self._random_plaque_key()

        plaque = ndb.Key(urlsafe=plaque_key).get()
        self.response.write(
            json.dumps({
                'plaque_key': plaque.key.urlsafe(),
                'title': plaque.title,
            }))

class ViewOnePlaque(ViewOnePlaqueParent):
    """
    Render the single-plaque page from a plaque key, or get a random plaque.
    """
    def get(self, plaque_key=None):
        self._get_from_key(plaque_key=plaque_key)

class ViewAllTags(webapp2.RequestHandler):
    def get(self):

        tags_sized = Plaque.all_tags_sized()

        template = JINJA_ENVIRONMENT.get_template('tags.html')
        template_values = {
            'tags': tags_sized,
            'mapzoom': 2,
            'footer_items': get_footer_items(),
            'pages_list': get_pages_list(),
        }
        self.response.write(template.render(template_values))

class ViewTag(webapp2.RequestHandler):
    def get(self, tag):
        """
        View plaque with a given tag on a grid.
        """
        plaques = Plaque.query().filter(Plaque.approved == True
                               ).filter(Plaque.tags == tag
                               ).order(-Plaque.created_on
                               ).fetch()
        template = JINJA_ENVIRONMENT.get_template('all.html')
        template_values = {
            'pages_list': get_pages_list(),
            'plaques': plaques,
            'pages_list': get_pages_list(),
            'start_index': 0,
            'end_index': len(plaques),
            'mapzoom': 2,
            'footer_items': get_footer_items(),
        }
        self.response.write(template.render(template_values))

class About(webapp2.RequestHandler):
    def get(self):
        """
        Render the About page from the common template.
        """
        template = JINJA_ENVIRONMENT.get_template('about.html')
        template_values = {
            'all_plaques': Plaque.all_approved(),
            'pages_list': get_pages_list(),
            'footer_items': get_footer_items(),
        }
        self.response.write(template.render(template_values))

class AddComment(webapp2.RequestHandler):
    @ndb.transactional(xg=True)
    def post(self):
        plaque_key = self.request.get('plaque_key')
        plaque = ndb.Key(urlsafe=plaque_key).get()

        comment_text = self.request.get('comment_text')
        comment = Comment()
        comment.text = comment_text
        comment.put()

        if len(plaque.comments) < 1:
            plaque.comments = [comment.key]
        else:
            plaque.comments.append(comment.key)
        plaque.put()

        # Email notify admin:
        msg = """Comment<hr><p>%s</p><hr> added  
              <a href="http://readtheplaque.net%s">here</a>""" % (
                comment.text, plaque.url)
        mail.send_mail(
            sender=NOTIFICATION_SENDER_EMAIL,
            to=ADMIN_EMAIL,
            subject='Comment added to %s' % plaque.url,
            body=msg,
            html=msg,
        )

        self.redirect(plaque.url)

class AddPlaque(webapp2.RequestHandler):
    """
    Add a plaque entity. Transactional in the _post method.
    """
    def get(self, message=None):
        template = JINJA_ENVIRONMENT.get_template('add.html')
        template_values = {
            'mapzoom': 5,
        }
        if message is not None:
            template_values['message'] = message

        template = JINJA_ENVIRONMENT.get_template('add.html')
        self.response.write(template.render(template_values))

    def post(self):
        self._post(False)

    @ndb.transactional
    def _post(self, is_migration=False):
        """
        We set the same parent key on the 'Plaque' to ensure each Plauqe is in
        the same entity group. Queries across the single entity group will be
        consistent. However, the write rate to a single entity group should be
        limited to ~1/second.
        """

        try:
            plaqueset_name = self.request.get('plaqueset_name',
                                              DEFAULT_PLAQUESET_NAME)
            location, created_by, title, description, image, tags = \
                self._get_form_args()

            plaque = Plaque(parent=plaqueset_key(plaqueset_name))
            plaque.location = location
            plaque.title = title
            plaque.description = description
            plaque.tags = tags
            if is_migration:
                plaque.approved = True

            if is_migration:
                img_name = os.path.basename(image)
                img_fh = urllib.urlopen(image)
            else:
                img_name = image.filename
                img_fh = image.file

            gcs_file_name, gcs_url = self._upload_image_to_gcs(img_name, img_fh)
            plaque.pic = gcs_file_name
            plaque.pic_url = gcs_url
            plaque.put()
        except (BadValueError, ValueError) as err:
            msg = "Sorry, your plaque submission had this error: '%s'" % err
            self.get(message=msg)
            return

        # Email notify admin:
        msg = """<p>Plaque '%s'</p>
                 <p>at %s</p>
                 <p>%s</p> added <a href="http://readtheplaque.net%s">here</a> """ % (
            plaque.title,
            plaque.location,
            plaque.description,
            plaque.url
        )
        mail.send_mail(
            sender=NOTIFICATION_SENDER_EMAIL,
            to=ADMIN_EMAIL,
            subject='Plaque added: %s' % plaque.url,
            body=msg,
            html=msg,
        )

        if not is_migration:
            msg = """Hooray! And thank you. We'll geocode your 
                  plaque and you'll see it appear on the map shortly 
                  <a href="%s">here</a>.""" % plaque.url
            self.get(message=msg)
        return

    def _get_form_args(self):

        latlng = self.request.get('location')
        lat, lng = [float(l) for l in latlng.split(',')]
        location = ndb.GeoPt(lat, lng)

        if users.get_current_user():
            created_by = users.get_current_user()
        else:
            created_by = None

        title = self.request.get('title')
        if len(title) > 1500:
            title = title[:1499]
        description = self.request.get('description')
        image = self.request.POST.get('plaque_image')

        # Get and tokenize tags
        tags_str = self.request.get('tags')
        tags_untokenized = tags_str.split(',')
        tags = [re.sub('\s+', ' ', t.strip().lower()) for t in tags_untokenized]
        tags = [t for t in tags if t] # Remove empties

        return location, created_by, title, description, image, tags

    def _upload_image_to_gcs(self, image_name, image_fh):
        """
        Upload pic into GCS

        The blobstore.create_gs_key and images.get_serving_url calls are
        outside of the with block; I think this is correct. The
        blobstore.create_gs_key call was erroring out on production when it was
        inside the with block.
        """
        date_slash_time = datetime.datetime.now().strftime("%Y%m%d/%H%M%S")
        gcs_fn= '%s/%s/%s' % (GCS_BUCKET, date_slash_time, image_name)

        ct = mimetypes.guess_type(image_name)[0]
        op = {b'x-goog-acl': b'public-read'}
        with gcs.open(gcs_fn, 'w', content_type=ct, options=op) as gcs_file:
            image_contents = image_fh.read()
            gcs_file.write(image_contents)

        blobstore_gs_key = blobstore.create_gs_key('/gs' + gcs_fn)
        gcs_file_url = images.get_serving_url(blobstore_gs_key)

        return gcs_fn, gcs_file_url

class AddPlaqueMigrate(AddPlaque):
    """
    Add a plaque, but use an URL for the image instead of an uploaded image.
    Used for scraping the old readtheplaque.com site.
    """
    def get(self):
        raise NotImplementedError("No get method for AddPlaqueMigrate")

    def post(self):
        self._post(is_migration=True)

# TODO: See:
#     http://stackoverflow.com/questions/13305302/using-search-api-python-google-app-engine-big-table
#     https://cloud.google.com/appengine/docs/python/search/ for details
#
#class SearchPlaques(webapp2.RequestHandler):
#    """Run a search in the title and description."""
#    def get(self):
#        raise NotImplementedError("No get method for SearchPlaques")
#
#    def post(self):
#        search_term = self.request.get('search_term')
#        plaques = Plaque.query().filter(Plaque.approved == True
#                               ).filter(Plaque.tags == tag
#                               ).order(-Plaque.created_on
#                               ).fetch()

class FlushMemcache(webapp2.RequestHandler):
    def get(self):
        memcache.flush_all()
        self.redirect('/')

    def post(self):
        memcache.flush_all()
        self.redirect('/')

class Counts(webapp2.RequestHandler):
    def get(self):
        num_comments = Comment.query().count()
        num_plaques = Plaque.query().count()
        num_images = 0
        images = gcs.listbucket(GCS_BUCKET)
        for image in images:
            num_images += 1

        msg = "There are %s comments, %s plaques, %s images" % (
                num_comments, num_plaques, num_images)
        self.response.write(msg)

class DeleteEverything(webapp2.RequestHandler):
    def get(self):
        comments = Comment.query().fetch()
        for comment in comments:
            comment.key.delete()

        plaques = Plaque.query().fetch()
        for plaque in plaques:
            plaque.key.delete()

        num_images = 0
        images = gcs.listbucket(GCS_BUCKET)
        for image in images:
            num_images += 1
            gcs.delete(image.filename)

        msg = "Deleted %s comments, %s plaques, %s images" % (
                len(comments), len(plaques), num_images)
        self.response.write(msg)

class RssFeed(webapp2.RequestHandler):
    def get(self, num_entries=10):
        plaques = Plaque.query(
                      ).filter(Plaque.approved == True
                      ).order(-Plaque.created_on
                      ).fetch(limit=num_entries)
        template = JINJA_ENVIRONMENT.get_template('feed.xml') # TODO: update this
        template_values = {'plaques': plaques}
        self.response.write(template.render(template_values))
