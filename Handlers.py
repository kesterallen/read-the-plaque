# -*- coding: utf-8 -*-

from collections import defaultdict
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

from Models import Comment, Plaque, FeaturedPlaque

PLAQUE_SEARCH_INDEX_NAME = 'plaque_index'
ADMIN_EMAIL = 'kester+readtheplaque@gmail.com'
NOTIFICATION_SENDER_EMAIL = 'kester@gmail.com'
ADD_STATE_SUCCESS = 'success'
ADD_STATE_ERROR = 'error'
ADD_STATES = {'ADD_STATE_SUCCESS': ADD_STATE_SUCCESS,
              'ADD_STATE_ERROR': ADD_STATE_ERROR}
#TODO: fix
FETCH_LIMIT_PLAQUES = 500

# GCS_BUCKET configuration: This appears to work for the bucket named
# 'read-the-plaque.appspot.com', but it is different from surlyfritter. I
# suspect I did something different/wrong in the setup, but not sure.
#
GCS_BUCKET = '/read-the-plaque.appspot.com'
# Don't change this to, say, readtheplaque.com

DEFAULT_PLAQUESET_NAME = 'public'
DEFAULT_NUM_PER_PAGE = 20
DEFAULT_MAP_ICON_SIZE_PIX = 16

# Load templates from the /templates dir
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__),
                     'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=False) # turn off autoescape to allow html descriptions

class SubmitError(Exception):
    pass

# Set a parent key on the Plaque objects to ensure that they are all in the
# same entity group. Queries across the single entity group will be consistent.
# However, the write rate should be limited to ~1/second.

def get_default_template_values(**kwargs):
    #MEMCACHE TODO: set template_values to None to turn off memcaching
    template_values = memcache.get('default_template_values')
    if template_values is None:
        template_values = {
            'num_pending': Plaque.num_pending(),
            'footer_items': get_footer_items(),
            'loginout': loginout(),
            'pages_list': get_pages_list(),
            'icon_size': DEFAULT_MAP_ICON_SIZE_PIX,
        }
        memcache_status = memcache.set('default_template_values',
                                       template_values)
        if not memcache_status:
            logging.debug("memcaching for default_template_values failed")
    else:
        logging.debug("memcache.get worked for default_template_values")

    for k, v in kwargs.items():
        template_values[k] = v
    return template_values

def email_admin(msg, body):
    try:
        mail.send_mail(sender=NOTIFICATION_SENDER_EMAIL,
                       to=ADMIN_EMAIL,
                       subject=msg,
                       body=body,
                       html=body)
    except Exception as err:
        logging.debug('mail failed: %s, %s' % (msg, err))

def get_plaqueset_key(plaqueset_name=DEFAULT_PLAQUESET_NAME):
    """
    Constructs a Datastore key for a Plaque entity. Use plaqueset_name as
    the key.
    """
    return ndb.Key('Plaque', plaqueset_name)

def earliest_approved(cls):
    item = cls.query(cls.approved == True
                  ).order(cls.created_on
                  ).get()
    return item

def last_five_approved(cls):
    new_items = cls.query(cls.approved == True
                  ).order(-cls.created_on
                  ).fetch(limit=5)
    return new_items

def random_five_approved(cls):
    items = cls.query(cls.approved == True).fetch()
    random.shuffle(items)
    return items[:5]

def random_tags(num=5):
    tags = set()
    for p in Plaque.query(Plaque.approved == True).fetch():
        for t in p.tags:
            tags.add(t)

    tags = list(tags)
    random.shuffle(tags)
    if len(tags) > num:
        tags = tags[:num]
    return tags

def get_pages_list(per_page=DEFAULT_NUM_PER_PAGE):
    num_pages = int(math.ceil(float(Plaque.num_approved()) /
                              float(per_page)))
    pages_list = [1+p for p in range(num_pages)]
    return pages_list

def get_footer_items():
    """
    Just 5 tags for the footer.
    Memcache the output of this so it doesn't get calculated every time.
    """
    #MEMCACHE TODO: set footer_items to None to turn off memcaching
    footer_items = memcache.get('get_footer_items')
    if footer_items is None:
        footer_items = {'tags': random_tags(),
                        'new_plaques': random_five_approved(Plaque),
                        'new_comments': last_five_approved(Comment)}

        memcache_status = memcache.set('get_footer_items', footer_items)
        if not memcache_status:
            logging.debug("memcaching for get_footer_items failed")
    else:
        logging.debug("memcache.get worked for get_footer_items")

    return footer_items

def loginout():
    # Login/Logout link:
    user = users.get_current_user()
    if user:
        loginout = {'is_admin': users.is_current_user_admin(),
                    'url': users.create_logout_url('/flush'),
                    'text': 'Log out'}
    else:
        loginout = {'is_admin': users.is_current_user_admin(),
                    'url': users.create_login_url('/flush'),
                    'text': 'Admin login'}
    return loginout

def get_featured():
    featured = FeaturedPlaque.query().order(-Plaque.created_on).get()
    if featured is not None:
        plaque = Plaque.query().filter(Plaque.key == featured.plaque).get()
    else:
        plaque = None
    return plaque

def set_featured(plaque):
    featured = FeaturedPlaque()
    featured.plaque = plaque.key
    featured.put()

def handle_404(request, response, exception):
    email_admin('404 error!', '404 error!\n\n%s\n\n%s\n\n%s' %
                              (request, response, exception))
    template = JINJA_ENVIRONMENT.get_template('error.html')
    response.write(template.render({'code': 404, 'error_text': exception}))
    response.set_status(404)

def handle_500(request, response, exception):
    email_admin('500 error!', '500 error!\n\n%s\n\n%s\n\n%s' %
                              (request, response, exception))
    template = JINJA_ENVIRONMENT.get_template('error.html')
    logging.error(exception)
    response.write(template.render({'code': 500, 'error_text': exception}))
    response.set_status(500)

class ViewPlaquesPage(webapp2.RequestHandler):
    def head(self, page_num=1, per_page=DEFAULT_NUM_PER_PAGE, is_random=False, is_featured=True):
        self.get(page_num=1, per_page=DEFAULT_NUM_PER_PAGE, is_featured=is_featured)
        self.response.clear()

    def _get_template_values(self, page_num, per_page, is_random, is_featured, limit=250, disable_memcache=False):
        # Grab all plaques for the map
        plaques = Plaque.approved_list(limit=limit, disable_memcache=disable_memcache)
        map_plaques = plaques
        if is_random:
            random.shuffle(plaques)
            map_plaques = plaques[:per_page]
        start_index = per_page * (page_num - 1)
        end_index = start_index + per_page

        template_values = get_default_template_values(
                              all_plaques=map_plaques,
                              plaques=plaques,
                              start_index=start_index,
                              end_index=end_index,
                              page_num=page_num,
                              static_map=is_featured,
                          )
        if is_featured:
            featured = get_featured()
            template_values['featured_plaque'] = featured

        return template_values

    def _get(self, page_num=1, per_page=DEFAULT_NUM_PER_PAGE, is_random=False, is_featured=True):
        """
        View the nth per_page plaques on a grid.
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
            per_page = int(per_page)
        except ValueError as err:
            logging.error(err)
            per_page = DEFAULT_NUM_PER_PAGE
        if per_page < 1:
            per_page = 1

        # If the requested page is not random, get the memcache.
        #
        is_admin = users.is_current_user_admin()
        user = users.get_current_user()
        name = "anon" if user is None else user.nickname()
        logging.debug("User %s is admin: %s" % (name, is_admin))
        memcache_name = 'view_plaques_page_featured_%s_%s_%s' % (
            page_num, per_page, is_admin)
        if is_random:
            template_text = None
        else:
            #MEMCACHE TODO: set template_text to None to turn off memcaching
            template_text = memcache.get(memcache_name)
            logging.debug("memcaching worked for ViewPlaquesPage %s" %
                memcache_name)

        if template_text is None:
            template_values = self._get_template_values(page_num, per_page, is_random, is_featured)
            template = JINJA_ENVIRONMENT.get_template('all.html')
            template_text = template.render(template_values)
            if not is_random:
                memcache_status = memcache.set(memcache_name, template_text)
                if not memcache_status:
                    logging.debug("memcache.set failed for ViewPlaquesPage %s" %
                        memcache_name)
                else:
                    logging.debug(
                        "memcache.set worked for ViewPlaquesPage %s" %
                        memcache_name)

        return template_text

    def get(self, page_num=1, per_page=DEFAULT_NUM_PER_PAGE, is_random=False, is_featured=True):
        template_text = self._get(page_num, per_page, is_random, is_featured)
        self.response.write(template_text)

class RenderMapSetup(ViewPlaquesPage):
    def get(self, page_num=1, per_page=DEFAULT_NUM_PER_PAGE, is_random=False, is_featured=True):
        template_values = self._get_template_values(page_num, per_page, is_random, is_featured, limit=5000, disable_memcache=True)
        template = JINJA_ENVIRONMENT.get_template('parts/big_map_dynamic.html')
        template_text = template.render(template_values)
        self.response.write(template_text)

## Deprecated, but used by Random. Figure out how to combine this with Featured
#class ViewPlaquesPage(webapp2.RequestHandler):
#    def head(self, page_num=1, per_page=DEFAULT_NUM_PER_PAGE, is_random=False):
#        self.get(page_num=1, per_page=DEFAULT_NUM_PER_PAGE)
#        self.response.clear()
#
#    def _get(self, page_num=1, per_page=DEFAULT_NUM_PER_PAGE, is_random=False):
#        """
#        View the nth per_page plaques on a grid.
#        page_num is a one-based integer
#        """
#        try:
#            page_num = int(page_num)
#        except ValueError as err:
#            logging.error(err)
#            page_num = 1
#        if page_num < 1:
#            page_num = 1
#
#        try:
#            per_page = int(per_page)
#        except ValueError as err:
#            logging.error(err)
#            per_page = DEFAULT_NUM_PER_PAGE
#        if per_page < 1:
#            per_page = 1
#
#        is_admin = users.is_current_user_admin()
#        logging.debug("User is admin: %s" % is_admin)
#        memcache_name = 'view_plaques_page_%s_%s_%s' % (
#            page_num, per_page, is_admin)
#        if is_random:
#            template_text = None
#        else:
#            template_text = memcache.get(memcache_name)
#            logging.debug("memcaching worked for ViewPlaquesPage %s" %
#                memcache_name)
#
#        if template_text is None:
#            # Grab all plaques for the map
#            plaques = Plaque.approved_list()
#            map_plaques = plaques
#            if is_random:
#                random.shuffle(plaques)
#                map_plaques = plaques[:per_page]
#            start_index = per_page * (page_num - 1)
#            end_index = start_index + per_page
#
#            template = JINJA_ENVIRONMENT.get_template('all.html')
#            template_values = get_default_template_values(
#                                  all_plaques=map_plaques,
#                                  plaques=plaques,
#                                  start_index=start_index,
#                                  end_index=end_index,
#                                  page_num=page_num,
#                              )
#
#            template_text = template.render(template_values)
#            if not is_random:
#                memcache_status = memcache.set(memcache_name, template_text)
#                if not memcache_status:
#                    logging.debug("memcaching failed for ViewPlaquesPage %s" %
#                        memcache_name)
#                else:
#                    logging.debug(
#                        "memcaching set worked for ViewPlaquesPage %s" %
#                        memcache_name)
#
#        return template_text
#
#    def get(self, page_num=1, per_page=DEFAULT_NUM_PER_PAGE, is_random=False):
#        template_text = self._get(page_num, per_page, is_random)
#        self.response.write(template_text)

class ViewOnePlaqueParent(webapp2.RequestHandler):
    def get(self):
        raise NotImplementedError("Don't call ViewOnePlaqueParent.get directly")

    def _random_plaque_key(self):
        count = Plaque.query().filter(Plaque.approved == True).count()
        if not count:
            raise ValueError("No plaques!")

        iplaque = random.randint(0, count-1)
        plaques = Plaque.query().filter(Plaque.approved == True
                               ).order(Plaque.created_on
                               ).fetch(offset=iplaque, limit=1)
        try:
            plaque_key = plaques[0].key.urlsafe()
        except IndexError as err:
            logging.error(err)
            raise IndexError("This plaque (%s of %s) has not been reviewed yet. "
                             "Please try again later!" % (iplaque, plaques))

        return plaque_key

    def _get_from_key(self, comment_key=None, plaque_key=None):
        """
        Put the single plaque into a list for rendering so that the common
        map functionality can be used unchanged. Attempt to serve a valid
        plaque, but if the inputs are completely messed up, serve a random
        plaque.
        """
        is_admin = users.is_current_user_admin()
        memcache_name = 'view_one_%s_%s' % (plaque_key, is_admin)
        #MEMCACHE TODO: set page_text to None to turn off memcaching
        page_text = memcache.get(memcache_name)
        if page_text is None:
            plaque = None
            logging.info("plaque_key=%s" % plaque_key)
            if comment_key is not None:
                logging.debug("Using comment key")
                comment = ndb.Key(urlsafe=comment_key).get()
                plaque = Plaque.query().filter(Plaque.approved == True
                                      ).filter(Plaque.comments == comment.key
                                      ).get()
            elif plaque_key is not None:
                try:
                    logging.debug("Trying old_site_id")
                    old_site_id = int(plaque_key)
                    plaque = Plaque.query(
                        ).filter(Plaque.approved == True
                        ).filter(Plaque.old_site_id == old_site_id
                        ).get()
                except ValueError as err:
                    # Get by title, allowing only admins to see unapproved ones:
                    logging.debug("Using plaque.title_url: '%s'" % plaque_key)
                    query = Plaque.query().filter(Plaque.title_url == plaque_key)
                    if not users.is_current_user_admin():
                        query = query.filter(Plaque.approved == True)
                    logging.debug("query is %s " % query)
                    plaque = query.get()
                    if plaque is None:
                        try:
                            logging.debug("Using plaque_key: '%s'" % plaque_key)
                            plaque = ndb.Key(urlsafe=plaque_key).get()
                            logging.debug("Using plaque_key, "
                                          "plaque retrieved was: '%s'" % plaque)
                        except:
                            pass

            if plaque is None:
                logging.debug("Neither comment_key nor plaque_key is specified. "
                              "Serve the first plaque, so that memcache will "
                              "always serve the same thing.")
                plaque = earliest_approved(Plaque)
                self.redirect(plaque.title_page_url)
                return

            logging.debug("Plaque: %s" % plaque)
            template = JINJA_ENVIRONMENT.get_template('one.html')
            template_values = get_default_template_values(
                                  all_plaques=[plaque],
                                  plaques=[plaque],
                                  icon_size=32,
                              )

            page_text = template.render(template_values)
            memcache_status = memcache.set(memcache_name, page_text)
            if not memcache_status:
                logging.debug("memcaching for _get_from_key failed for %s" %
                              memcache_name)
        else:
            logging.debug("memcache.get worked for _get_from_key for %s" %
                          memcache_name)

        return page_text

class AdminLogin(webapp2.RequestHandler):
    def get(self):
        url = users.create_login_url('/flush'),
        self.response.write("<a href='%s'>Login</a>" % url)

class ViewOnePlaque(ViewOnePlaqueParent):
    """
    Render the single-plaque page from a plaque key, or get a random plaque.
    """
    def head(self, plaque_key=None, ignored_cruft=None):
        self.get(plaque_key=None, ignored_cruft=None)
        self.response.clear()

    def get(self, plaque_key=None, ignored_cruft=None):
        page_text = self._get_from_key(plaque_key=plaque_key)
        self.response.write(page_text)

class RandomPlaquesPage(ViewPlaquesPage):
    """
    Get a page of random plaques.
    """
    def get(self):
        page_text = self._get(per_page=6, is_random=True, is_featured=False)
        self.response.write(page_text)

class RandomPlaque(ViewOnePlaqueParent):
    """
    Get a random plaque.
    """
    def get(self):
        plaque_key = self._random_plaque_key()
        plaque = ndb.Key(urlsafe=plaque_key).get()
        self.redirect(plaque.title_page_url)

#class ViewOnePlaqueFromComment(ViewOnePlaqueParent):
#    """
#    Render the single-plaque page from a comment key.
#    """
#    def get(self, comment_key):
#        page_text = self._get_from_key(comment_key=comment_key)
#        self.response.write(page_text)

class JsonOnePlaque(ViewOnePlaqueParent):
    """
    Get one plaque's JSON repr.
    """
    def get(self, plaque_key=None):
        if plaque_key is None:
            plaque_key = self._random_plaque_key()

        plaque = ndb.Key(urlsafe=plaque_key).get()
        set_featured(plaque)
        memcache.flush_all()
        self.response.write(json.dumps(plaque.to_dict()))

class JsonAllPlaques(webapp2.RequestHandler):
    """
    Get every plaques' JSON repr.
    """
    def get(self):
        plaques = Plaque.query().order(-Plaque.created_on).fetch()
        jsons = []
        for plaque in plaques:
            jsons.append(json.dumps(plaque.to_dict()))

        self.response.write(json.dumps(jsons))

class ViewAllTags(webapp2.RequestHandler):
    def get(self):

        tags_sized = Plaque.all_tags_sized()

        template = JINJA_ENVIRONMENT.get_template('tags.html')
        template_values = get_default_template_values(tags=tags_sized)
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
        template_values = get_default_template_values(
                              all_plaques=plaques,
                              plaques=plaques,
                              start_index=0,
                              end_index=len(plaques),
                          )
        self.response.write(template.render(template_values))

class About(webapp2.RequestHandler):
    def get(self):
        """
        Render the About page from the common template.
        """
        template = JINJA_ENVIRONMENT.get_template('about.html')
        template_values = get_default_template_values(
                              all_plaques=Plaque.approved_list())
        self.response.write(template.render(template_values))

#class AddComment(webapp2.RequestHandler):
#    @ndb.transactional(xg=True)
#    def post(self):
#        plaque_key = self.request.get('plaque_key')
#        plaque = ndb.Key(urlsafe=plaque_key).get()
#
#        comment_text = self.request.get('comment_text')
#        comment = Comment()
#        comment.text = comment_text
#        comment.put()
#
#        if len(plaque.comments) < 1:
#            plaque.comments = [comment.key]
#        else:
#            plaque.comments.append(comment.key)
#        plaque.put()
#        memcache.flush_all()
#
#        #email_admin(plaque, comment)
#        self.redirect(plaque.title_url)

class AddPlaque(webapp2.RequestHandler):
    """
    Add a plaque entity. Transactional in the _post method.
    """
    def _get_message(self, message):
        if message is None:
            message = self.request.get('message')

        state = self.request.get('state')
        if state is not None:
            if state == ADD_STATE_SUCCESS:
                if users.is_current_user_admin():
                    message = """Plaque added by admin:
                        <a href="%s">here</a>.""" % message
                else:
                    message = """Hooray! And thank you. We'll review your
                        plaque and you'll see it appear on the map shortly."""

            elif state == ADD_STATE_ERROR:
                message = """
                    Sorry, your plaque submission had this error:
                    <font color="red">'%s'</font>
                    """ % message
        return message

    def get(self, message=None):
        maptext = "Click the plaque's location on the map, or search " + \
                  "for it, or enter its lat/lng location"
        template_values = get_default_template_values(maptext=maptext)
        message = self._get_message(message)
        if message is not None:
            template_values['message'] = message
        message = self.request.get('message')

        template = JINJA_ENVIRONMENT.get_template('add.html')
        self.response.write(template.render(template_values))

    @ndb.transactional
    def post(self, is_edit=False):
        """
        We set the same parent key on the 'Plaque' to ensure each Plauqe is in
        the same entity group. Queries across the single entity group will be
        consistent. However, the write rate to a single entity group should be
        limited to ~1/second.
        """

        if users.is_current_user_admin():
            memcache.flush_all()
        try:
            plaqueset_name = self.request.get('plaqueset_name',
                                              DEFAULT_PLAQUESET_NAME)
            plaqueset_key = get_plaqueset_key(plaqueset_name)

            # Create new plaque entity:
            #
            logging.info('creating or updating plaque entity')
            plaque = self._create_or_update_plaque(is_edit, plaqueset_key)
            logging.info("Plaque %s is added with is_edit %s." % 
                (plaque.title, is_edit))

            # Make the plaque searchable:
            #
            logging.info('making search document')
            try:
                plaque_search_index = search.Index(PLAQUE_SEARCH_INDEX_NAME)
                plaque_search_index.put(plaque.to_search_document())
            except search.Error as err:
                logging.error(err)
                raise err

            # Notify admin:
            #
            logging.info('creating email')
            post_type = 'Updated' if is_edit else 'New'
            user = users.get_current_user()
            name = "anon" if user is None else user.nickname()
            msg = '%s %s plaque! %s' %  (name, post_type, plaque.title_page_url)
            body = """
                <p>
                    <a href="http://readtheplaque.com{1.title_page_url}">
                        {0} plaque!
                    </a>
                </p>
                <p>
                    <a href="http://readtheplaque.com{1.title_page_url}">
                        <img alt="plaque alt" title="plaque title" src="{1.img_url}"/>
                    </a>
                </p>
                """.format(post_type, plaque)
            #logging.info('sending email')
            #email_admin(msg, body)
            state = ADD_STATES['ADD_STATE_SUCCESS']
            msg = plaque.title_page_url
        except (BadValueError, ValueError, SubmitError) as err:
            msg = err
            state = ADD_STATES['ADD_STATE_ERROR']
            logging.info(msg)
            # Delete the GCS image, if it exists (the GCS images are not
            # managed by the transaction, apparently)
            try:
                gcs.delete(plaque.pic)
            except:
                pass

        self.redirect('/add?state=%s&message=%s' % (state, msg))

    def _create_or_update_plaque(self, is_edit, plaqueset_key):
        """
        Create a new plaque entity if it does not exist, or update one if it
        does.
        """
        if not is_edit:
            plaque = Plaque(parent=plaqueset_key)
        else:
            plaque_key = self.request.get('plaque_key')
            plaque = ndb.Key(urlsafe=plaque_key).get()

        location, created_by, title, description, img_name, img_fh, tags = \
            self._get_form_args()

        plaque.location = location
        plaque.title = title
        plaque.set_title_url(plaqueset_key, is_edit)
        plaque.description = description
        plaque.tags = tags
        plaque.approved = users.is_current_user_admin()
        plaque.updated_on = datetime.datetime.now()

        # Upload the image for a new plaque, or update the image for an
        # editted plaque, if specified.
        is_upload_pic = (is_edit and img_name is not None) or (not is_edit)
        if is_upload_pic:
            self._upload_image(img_name, img_fh, plaque)

        # Write to the updated_* fields if this is an edit:
        #
        if is_edit:
            plaque.updated_by = users.get_current_user()
            plaque.updated_on = datetime.datetime.now()
            img_rot = self.request.get('img_rot')
            if img_rot is not None and img_rot != 0:
                plaque.img_rot = int(img_rot)
        else:
            plaque.created_by = created_by
            plaque.updated_by = None

        old_site_id = self.request.get('old_site_id', None)
        if old_site_id is not None:
            try:
                plaque.old_site_id = int(old_site_id)
            except ValueError as err:
                logging.info('Eating bad ValueError for '
                             'old_site_id in AddPlaque')
        plaque.put()
        return plaque

    def _get_form_args(self):
        """Get the arguments from the form and return them."""

        lat = self.request.get('lat')
        lng = self.request.get('lng')

        if lat is None or lng is None or lat == '' or lng == '':
            geo_search_term = self.request.get('searchfield')
            geo_url = 'http://maps.googleapis.com/maps/api/geocode/'
            url = geo_url + 'json?address=' + geo_search_term
            geo_fh = urllib.urlopen(url)
            geo_json = json.load(geo_fh)

            if geo_json['results']:
                loc_json = geo_json['results'][0]['geometry']['location']
                lat = loc_json['lat']
                lng = loc_json['lng']

        try:
            location = ndb.GeoPt(lat, lng)
        except:
            err = SubmitError("The plaque location wasn't specified. Please "
                              "click the back button and resubmit.")
            raise err

        if users.get_current_user():
            created_by = users.get_current_user()
        else:
            created_by = None

        title = self.request.get('title')
        if len(title) > 1500:
            title = title[:1499]
        description = self.request.get('description')

        img_file = self.request.POST.get('plaque_image_file')
        img_url = self.request.POST.get('plaque_image_url')

        # Prefer the file to the URL, if both are given.
        #
        if img_file != '' and img_file is not None:
            img_name = img_file.filename
            img_fh = img_file.file
        elif img_url != '':
            img_name = os.path.basename(img_url)
            img_fh = urllib.urlopen(img_url)
        else:
            img_name = None
            img_fh = None
            #don't do anything (for edits where the image isn't being updated)

        # Get and tokenize tags
        tags_str = self.request.get('tags')
        tags_split = tags_str.split(',')
        tags = [re.sub(r'\s+', ' ', t.strip().lower()) for t in tags_split]
        tags = [t for t in tags if t] # Remove empties

        return location, created_by, title, description, img_name, img_fh, tags

    def _upload_image(self, img_name, img_fh, plaque):
        """
        Upload pic into GCS

        The blobstore.create_gs_key and images.get_serving_url calls are
        outside of the with block; I think this is correct. The
        blobstore.create_gs_key call was erroring out on production when it was
        inside the with block.

        If gcs_fn is specified, overwrite that gcs filename. This is used
        for updating the picture.
        """

#       Turn this off while Tony Bonomolo is editing:
#
#        # Kill old image and URL, if they exist. Tolerate failure in case
#        # this is a redo:
#        if plaque.pic is not None:
#            try:
#                gcs.delete(plaque.pic)
#            except:
#                pass
#        if plaque.img_url is not None:
#            try:
#                images.delete_serving_url(plaque.img_url)
#            except:
#                pass

        # Make GCS filename
        date_slash_time = datetime.datetime.now().strftime("%Y%m%d/%H%M%S")
        gcs_filename = '%s/%s/%s' % (GCS_BUCKET, date_slash_time, img_name)
        plaque.pic = gcs_filename

        # Write image to GCS
        try:
            ct, op = self._gcs_extras(img_name)
            with gcs.open(gcs_filename, 'w', content_type=ct, options=op) as fh:
                img_contents = img_fh.read()
                fh.write(img_contents)
        except AttributeError:
            submit_err = SubmitError("The image for the plaque was not "
                                     "specified-- please click the back button "
                                     "and resubmit.")
            logging.error(submit_err)
            raise submit_err

        # Make serving_url for image:
        blobstore_gs_key = blobstore.create_gs_key('/gs' + gcs_filename)
        plaque.img_url = images.get_serving_url(blobstore_gs_key)

    def _gcs_extras(self, img_name):
        """Hide this here to clarify what _upload_image is doing."""
        ct = 'image/jpeg'
        try:
            if ct is None:
                guess_type = mimetypes.guess_type(img_name)
                if len(guess_type) > 0:
                    ct = guess_type[0]
        except:
            pass
        op = {b'x-goog-acl': b'public-read'}
        return ct, op

class EditPlaque(AddPlaque):
    """
    Edit a plaque entity. Transactional in the _post method.
    """
    def get(self, plaque_key=None, message=None):
        if plaque_key is None:
            self.redirect('/')
            return
        else:
            plaque = ndb.Key(urlsafe=plaque_key).get()
            if plaque is None:
                message = None
            else:
                message = "Editing Plaque"

        template = JINJA_ENVIRONMENT.get_template('add.html')
        template_values = {
            'plaque': plaque,
            'maptext': 'Click the map, do a search, or click "Get My Location"',
            'loginout': loginout()
        }
        if message is not None:
            template_values['message'] = message

        template = JINJA_ENVIRONMENT.get_template('edit.html')
        self.response.write(template.render(template_values))

    def post(self):
        if users.is_current_user_admin():
            super(EditPlaque, self).post(is_edit=True)


class SearchPlaques(webapp2.RequestHandler):
    """Run a search in the title and description."""
    def post(self):
        search_term = self.request.get('search_term')
        self.get(search_term)

    def get(self, search_term=None):
        logging.debug('search term is "%s"' % search_term)
        if search_term is None:
            plaques = []
        else:
            search_term = '"%s"' % search_term.replace('"', '')
            plaque_search_index = search.Index(PLAQUE_SEARCH_INDEX_NAME)
            results = plaque_search_index.search(search_term)
            logging.debug('search results are "%s"' % results)
            plaques = [ndb.Key(urlsafe=r.doc_id).get() for r in results]
            plaques = [p for p in plaques if p is not None]

        template = JINJA_ENVIRONMENT.get_template('all.html')
        template_values = get_default_template_values(
                              all_plaques=plaques,
                              plaques=plaques,
                              start_index=0,
                              end_index=len(plaques),
                          )
        self.response.write(template.render(template_values))

class SearchPlaquesGeo(webapp2.RequestHandler):
    """Run a geographic search: plaques within radius of center are returned."""

    def _serve_form(self, redir):
        maptext = 'Click the map, or type a search here'
        step1text = 'Click the map to pick where to search'
        if redir:
            step1text = '<span style="color:red">%s</span>' % step1text

        template_values = get_default_template_values(maptext=maptext,
                                                      step1text=step1text)
        template = JINJA_ENVIRONMENT.get_template('geosearch.html')
        self.response.write(template.render(template_values))

    def _serve_response(self, lat, lng, search_radius_meters):
        plaque_search_index = search.Index(PLAQUE_SEARCH_INDEX_NAME)

        query_string = 'distance(location, geopoint(%s, %s)) < %s' % (
                        lat, lng, search_radius_meters)
        query = search.Query(query_string)
        results = plaque_search_index.search(query)
        plaques = [ndb.Key(urlsafe=r.doc_id).get() for r in results]
        approved_plaques = [p for p in plaques if p is not None and p.approved]

        template = JINJA_ENVIRONMENT.get_template('all.html')
        template_values = get_default_template_values(
                              all_plaques=approved_plaques,
                              plaques=approved_plaques,
                              start_index=0,
                              end_index=len(plaques),
                              mapcenter={'lat': lat, 'lng': lng},
                              static_map=False,
                          )
        self.response.write(template.render(template_values))

    def get(self, lat=None, lng=None, search_radius_meters=None, redir=False):

        # Serve the form if a search hasn't been specified, otherwise show the
        # results:
        #
        search_not_specified = (lat is None or lat == '') or \
                               (lng is None or lng == '') or \
                               (search_radius_meters is None or \
                                search_radius_meters == '')
        if search_not_specified:
            self._serve_form(redir)
        else:
            self._serve_response(lat, lng, search_radius_meters)

    def post(self):
        try:
            lat = self.request.get('lat')
            lng = self.request.get('lng')
            search_radius_meters = self.request.get('search_radius_meters')
        except:
            err = SubmitError(
                    "The search area wasn't specified correctly ((%s, %s) < %s)"
                    ". Please try again." % (lat, lng, search_radius_meters))
            raise err
        self.get(lat, lng, search_radius_meters, redir=True)

class FlushMemcache(webapp2.RequestHandler):
    def get(self):
        memcache.flush_all()
        self.redirect('/')

    def post(self):
        memcache.flush_all()
        self.redirect('/')

class Counts(webapp2.RequestHandler):
    def get(self):
        find_orphans = self.request.get('find_orphans')
        num_comments = Comment.query().count()
        num_plaques = Plaque.query().count()
        num_images = 0
        images = gcs.listbucket(GCS_BUCKET)
        for image in images:
            num_images += 1

        orphan_pics = set()
        pics_count = defaultdict(int)
        pics = set()

        if find_orphans == 'true':
            # Record which pics are linked to a plaque:
            plaques = Plaque.query().fetch()
            for plaque in plaques:
                pics.add(plaque.pic)
                pics_count[plaque.pic] += 1

            # Find pics that aren't:
            for pic in images:
                if pic not in pics:
                    orphan_pics.add(pic)
        else:
            orphan_pics.add("didn't check for orphans")

        msg = "There are %s comments, %s plaques, %s images, orphan pics: %s<hr>%s" % (
                num_comments, num_plaques, num_images, orphan_pics, pics_count)
        self.response.write(msg)

class DeleteOnePlaque(webapp2.RequestHandler):
    def get(self):
        raise NotImplementedError("no get in DeleteOnePlaque")

    @ndb.transactional
    def post(self):
        """Remove one plaque and its associated Comments and GCS image."""
        user = users.get_current_user()
        name = "anon" if user is None else user.nickname()

        plaque_key = self.request.get('plaque_key')
        plaque = ndb.Key(urlsafe=plaque_key).get()

        if name != 'kester':
            email_admin('Delete warning!', '%s tried to delete %s' % (name, plaque.title_url))
            raise NotImplementedError("delete is turned off for now")

        for comment in plaque.comments:
            comment.delete()
        try:
            gcs.delete(plaque.pic)

            #TODO: delete search index for this document
            #plaque_search_index = search.Index(PLAQUE_SEARCH_INDEX_NAME)
            #results = plaque_search_index.search(search_term)
            #for result in results:
            #    plaques = [ndb.Key(urlsafe=r.doc_id).get() for r in results]
            #    plaque_search_index.delete(result.doc_id)
        except:
            pass

        plaque.key.delete()
        memcache.flush_all()
        email_admin('%s Deleted plaque %s' % (name, plaque.title_url),
                    '%s Deleted plaque %s' % (name, plaque.title_url))
        self.redirect('/')

#class DeleteEverything(webapp2.RequestHandler):
#    def get(self):
#        comments = Comment.query().fetch()
#        for comment in comments:
#            comment.key.delete()
#
#        plaques = Plaque.query().fetch()
#        for plaque in plaques:
#            plaque.key.delete()
#
#        num_images = 0
#        images = gcs.listbucket(GCS_BUCKET)
#        for image in images:
#            num_images += 1
#            try:
#                gcs.delete(image.filename)
#            except:
#                pass
#
#        msg = "Deleted %s comments, %s plaques, %s images" % (
#                len(comments), len(plaques), num_images)
#
#        memcache.flush_all()
#        self.response.write(msg)

class ViewPending(webapp2.RequestHandler):
    def get(self):
        plaques = Plaque.pending_list()
        user = users.get_current_user()
        name = "anon" if user is None else user.nickname()
        logging.info("User %s is viewing pending plaques" % name)

        template = JINJA_ENVIRONMENT.get_template('all.html')
        template_values = get_default_template_values(
                              all_plaques=plaques,
                              plaques=plaques,
                              start_index=0,
                              end_index=len(plaques),
                          )
        template_text = template.render(template_values)
        self.response.write(template_text)

class DeleteOneSearchIndex(webapp2.RequestHandler):
    def get(self, doc_id):
        plaque_search_index = search.Index(PLAQUE_SEARCH_INDEX_NAME)
        try:
            plaque_search_index.delete(doc_id)
        except search.Error:
            msg = "Error removing doc id %s" % doc_id
            logging.exception(msg)
            self.response.write(msg)

class AddSearchIndexAll(webapp2.RequestHandler):
    def get(self):
        plaques = Plaque.query().fetch()
        plaque_search_index = search.Index(PLAQUE_SEARCH_INDEX_NAME)
        igood = 0
        ibad = 0
        for plaque in plaques:
            try:
                plaque_search_index.put(plaque.to_search_document())
                igood += 1
            except search.Error as err:
                ibad += 1
                logging.error(err)
            logging.debug('in process: wrote %s good docs, %s failed' % (
                          igood, ibad))
        self.response.write('wrote %s good docs, %s failed' % (igood, ibad))

class AddTitleUrlAll(webapp2.RequestHandler):
    def get(self):
        plaques = Plaque.query().fetch()
        for plaque in plaques:
            plaque.set_title_url()
            plaque.put()
        memcache.flush_all()
        self.redirect('/')

class ApproveAllPending(webapp2.RequestHandler):
    """Approve all pending plaques"""
    def get(self):
        plaques = Plaque.pending_list()
        for plaque in plaques:
            plaque.approved = True
            plaque.put()
        memcache.flush_all()
        self.redirect('/')

class ApprovePending(webapp2.RequestHandler):
    """Approve a plaque"""
    @ndb.transactional
    def post(self):
        memcache.flush_all()
        plaque_key = self.request.get('plaque_key')
        plaque = ndb.Key(urlsafe=plaque_key).get()
        logging.info("Approving plaque {0.title}".format(plaque))
        plaque.approved = True
        plaque.created_on = datetime.datetime.now()
        plaque.put()
        self.redirect('/pending')

class DisapprovePlaque(webapp2.RequestHandler):
    """Disapprove a plaque"""
    @ndb.transactional
    def post(self):
        memcache.flush_all()
        plaque_key = self.request.get('plaque_key')
        plaque = ndb.Key(urlsafe=plaque_key).get()
        logging.info("disapproving plaque {0.title}".format(plaque))
        plaque.approved = False
        plaque.put()
        self.redirect('/')

class RssFeed(webapp2.RequestHandler):
    def get(self, num_entries=10):
        plaques = Plaque.query(
                      ).filter(Plaque.approved == True
                      ).order(-Plaque.created_on
                      ).fetch(limit=num_entries)
        template = JINJA_ENVIRONMENT.get_template('feed.xml')
        template_values = {'plaques': plaques}
        self.response.write(template.render(template_values))

class SetUpdatedOn(webapp2.RequestHandler):
    def get(self):
        plaques = Plaque.query(
                      ).filter(Plaque.updated_on == None
                      ).order(-Plaque.created_on
                      ).fetch()
        for plaque in plaques:
            plaque.updated_on = plaque.created_on
            plaque.put()
        self.response.write([p.title for p in plaques])
        
class SetFeatured(webapp2.RequestHandler):
    def get(self, plaque_key):
        if users.is_current_user_admin():
            plaque = ndb.Key(urlsafe=plaque_key).get()
            logging.info("setting plaque {0.title} to featured".format(plaque))
            set_featured(plaque)
            memcache.flush_all()
            self.redirect('/')

