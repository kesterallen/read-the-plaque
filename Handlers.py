# -*- coding: utf-8 -*-

#TODO: New uploader for Openbenches (auto approve)
#TODO: new class to lazyload the openbenches images
#           * might need new column in Plaque to indicate if a given row has been loaded or not

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
import urllib2
from utils import (
    DEF_NUM_PENDING,
    email_admin,
    get_random_plaque,
    get_random_plaque_key,
    get_template_values,
    latlng_angles_to_dec,
    loginout,
    PLAQUE_SEARCH_INDEX_NAME,
    SubmitError,
)
import webapp2

from google.appengine.api import images
from google.appengine.api import memcache
from google.appengine.api import search
from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from google.appengine.ext.db import BadValueError
from google.appengine.ext.ndb.google_imports import ProtocolBuffer

import lib.cloudstorage as gcs

from Models import Plaque, FeaturedPlaque

ADD_STATE_SUCCESS = 'success'
ADD_STATE_ERROR = 'error'
ADD_STATES = {'ADD_STATE_SUCCESS': ADD_STATE_SUCCESS,
              'ADD_STATE_ERROR': ADD_STATE_ERROR}

# GCS_BUCKET configuration: This appears to work for the bucket named
# 'read-the-plaque.appspot.com', but it is different from surlyfritter. I
# suspect I did something different/wrong in the setup, but not sure.
#
GCS_BUCKET = '/read-the-plaque.appspot.com'
# Don't change this to, say, readtheplaque.com

DEF_PLAQUESET_NAME = 'public'

DEF_NUM_PER_PAGE = 25
DEF_NUM_NEARBY = 5
DEF_MAP_ICON_SIZE_PIX = 16

# Load templates from the /templates dir
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=False, # turn off autoescape to allow html descriptions
)

# Set a parent key on the Plaque objects to ensure that they are all in the
# same entity group. Queries across the single entity group will be consistent.
# However, the write rate should be limited to ~1/second.

def get_plaqueset_key(plaqueset_name=DEF_PLAQUESET_NAME):
    """
    Constructs a Datastore key for a Plaque entity. Use plaqueset_name as
    the key.
    """
    return ndb.Key('Plaque', plaqueset_name)

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
    error_text = '500 error!\n{}\n{}\n{}'.format(request, response, exception)
    email_admin('500 error!', error_text)
    template = JINJA_ENVIRONMENT.get_template('error.html')
    logging.error(exception)
    error_text = exception
    response.write(template.render({'code': 500, 'error_text': error_text}))
    response.set_status(500)

class FakePlaqueForRootUrlPreviews(object):
    """Probably a better way to do this."""
    def __init__(self):
        self.title_page_url = "https://readtheplaque.com"
        self.title = "Read the Plaque"
        self.description = "A gigantic map of all the cool plaques in the world"
        self.img_url_thumbnail = "https://readtheplaque.com/images/rtp_logo_600square.jpg"

class ViewPlaquesPage(webapp2.RequestHandler):
    def head(self, start_curs_str=None):
        self.get()
        self.response.clear()

    def get(self, cursor_urlsafe=None):
        template_text = self._get_template_text(
            cursor_urlsafe, is_random=False, is_featured=True)
        self.response.write(template_text)

    def _get_template_text(
            self, cursor_urlsafe=None, per_page=DEF_NUM_PER_PAGE,
            is_random=False, is_featured=True
        ):
        """
        View the nth per_page plaques on a grid.
        """
        try:
            per_page = int(per_page)
        except ValueError as err:
            logging.error(err)
            per_page = DEF_NUM_PER_PAGE
        if per_page < 1:
            per_page = 1

        # If the requested page is not random, get the memcache.
        #
        is_admin = users.is_current_user_admin()
        user = users.get_current_user()
        name = "anon" if user is None else user.nickname()
        memcache_name = 'plaques_%s_%s_%s' % (per_page, cursor_urlsafe, is_admin)
        if is_random:
            template_text = None
        else:
            template_text = memcache.get(memcache_name)
            logging.debug("memcache.get worked ViewPlaquesPage %s" % memcache_name)

        if template_text is None:
            template_values = self._get_template_values(
                per_page, cursor_urlsafe, is_random, is_featured)
            template = JINJA_ENVIRONMENT.get_template('all.html')
            template_text = template.render(template_values)
            if not is_random:
                memcache_status = memcache.set(memcache_name, template_text)
                ms = "failed" if not memcache_status else "success"
                logging.debug("memcache.set %s ViewPlaquesPage %s" % (ms, memcache_name))

        return template_text

    def _get_template_values(self, per_page, cursor_urlsafe, is_random, is_featured):
        if is_random:
            plaques = []
            cursor_urlsafe = None
            more = False
            for i in range(per_page):
                plaques.append(get_random_plaque())
        else:
            plaques, next_cursor, more = Plaque.fetch_page(
                per_page, start_cursor=cursor_urlsafe, urlsafe=True)

            if next_cursor is None:
                cursor_urlsafe = ''
            else:
                cursor_urlsafe = next_cursor.urlsafe()

        template_values = get_template_values(
            plaques=plaques, next_cursor_urlsafe=cursor_urlsafe, more=more)
        if is_featured:
            featured = get_featured()
            template_values['featured_plaque'] = featured
            fake = FakePlaqueForRootUrlPreviews()
            template_values['fake_plaque_for_root_url_previews'] = fake

        return template_values

class BigMap(ViewPlaquesPage):
    @property
    def template_file(self):
        return "bigmap.html"

    def get(self, lat=None, lng=None, zoom=None):

        template_values = get_template_values(bigmap=True)
        query = Plaque.query()
        num_plaques = query.filter(Plaque.approved == True).count()
        template_values['counts'] = num_plaques
        logging.debug(template_values)
        if lat is not None and lng is not None:
            template_values['bigmap_center'] = True
            template_values['bigmap_lat'] = lat
            template_values['bigmap_lng'] = lng

            if zoom is not None:
                template_values['bigmap_zoom'] = zoom

        template = JINJA_ENVIRONMENT.get_template(self.template_file)
        template_text = template.render(template_values)
        self.response.write(template_text)

class ExifText(BigMap):
    @property
    def template_file(self):
        return "exif.html"

    def get(self):
        template = JINJA_ENVIRONMENT.get_template(self.template_file)
        template_values = get_template_values()
        template_text = template.render(template_values)
        self.response.write(template_text)

class ViewOnePlaqueParent(webapp2.RequestHandler):
    def get(self):
        raise NotImplementedError("Don't call ViewOnePlaqueParent.get directly")


    # TODO: Separate this out to return the Plaque object GEOJSON
    def _get_plaque_from_key(self, plaque_key=None):
        # Get plaque from db from db:
        plaque = None
        logging.info("plaque_key=%s" % plaque_key)
        if plaque_key is not None:
            # Get by title, allowing only admins to see unapproved ones:
            logging.debug("Using plaque.title_url: '%s'" % plaque_key)
            query = Plaque.query().filter(Plaque.title_url == plaque_key)
            if not users.is_current_user_admin():
                query = query.filter(Plaque.approved == True)
            logging.debug("query is %s " % query)
            plaque = query.get()

            if plaque is None:
                try:
                    plaque = ndb.Key(urlsafe=plaque_key).get()
                except:
                    pass
        return plaque

    def _get_page_from_key(self, plaque_key=None):
        """
        Put the single plaque into a list for rendering so that the common map
        functionality can be used unchanged. Attempt to serve a valid plaque,
        but if the inputs are completely messed up, serve the oldest plaque.
        """

        # If it's memecached, use that:
        is_admin = users.is_current_user_admin()
        memcache_name = 'plaque_%s_%s' % (plaque_key, is_admin)
        page_text = memcache.get(memcache_name)
        if page_text is not None:
            return page_text

        # If page is not memcached, get the plaque from the db:
        plaque = self._get_plaque_from_key(plaque_key)

        # If that didn't find anything, serve the default couldn't-find-it
        # plaque (currently hacked in as the earliest plaque):
        if plaque is None:
            earliest_plaque = Plaque.query(
                Plaque.approved == True).order(Plaque.created_on).get()
            self.redirect(earliest_plaque.title_page_url)
            return

        template_values = get_template_values(plaques=[plaque])

        template = JINJA_ENVIRONMENT.get_template('one.html')
        page_text = template.render(template_values)
        memcache_status = memcache.set(memcache_name, page_text)
        if not memcache_status:
            logging.debug("memcache.set for _get_page_from_key failed for %s" %
                          memcache_name)

        return page_text

class AdminLogin(webapp2.RequestHandler):
    def get(self):
        #url = users.create_login_url('/flush'),
        url = users.create_login_url('/'),
        self.response.write("<a href='%s'>Login</a>" % url)

class ViewOnePlaque(ViewOnePlaqueParent):
    """
    Render the single-plaque page from a plaque key, or get a random plaque.
    """
    def head(self, plaque_key=None, ignored_cruft=None):
        self.get(plaque_key=None, ignored_cruft=None)
        self.response.clear()

    def get(self, plaque_key=None, ignored_cruft=None):
        page_text = self._get_page_from_key(plaque_key=plaque_key)
        self.response.write(page_text)

class RandomPlaquesPage(ViewPlaquesPage):
    """
    Get a page of random plaques.
    """
    def get(self, per_page=5):
        page_text = self._get_template_text(per_page=per_page, is_random=True, is_featured=False)
        self.response.write(page_text)

class RandomPlaque(ViewOnePlaqueParent):
    """
    Get a single random plaque.
    """
    def get(self):
        plaque = get_random_plaque()
        self.redirect(plaque.title_page_url)

class GeoJson(ViewOnePlaqueParent):
    """ Get one plaque's geoJSON """
    def get(self, plaque_key=None):
        # TODO: use _get_from_key when it's ready
        # TODO Separate this out to return the Plaque object GEOJSON
        plaque = self._get_plaque_from_key(plaque_key)
        self.response.write(plaque.geojson)

class TweetText(ViewOnePlaqueParent):
    """
    Get one plaque's JSON repr, and set it to be the featured plaque.
    """
    def get(self, plaque_key=None, summary=True):
        if plaque_key is None:
            plaque_key = get_random_plaque_key()

        plaque = ndb.Key(urlsafe=plaque_key).get()
        set_featured(plaque)
        # TODO: If plaque.description matches r'Submitted by @(.*)', tweet to that submitter
        memcache.flush_all()
        logging.info(plaque.json_for_tweet)
        self.response.write(plaque.json_for_tweet)

class JsonAllPlaques(webapp2.RequestHandler):
    """
    Get every plaques' JSON repr.
    """
    def _plaques_to_json(self, plaques, summary=True):
        if plaques:
            logging.info("plaque date range is %s - %s" %
                (plaques[0].created_on, plaques[-1].created_on))
        plaque_dicts = [p.to_dict(summary=summary) for p in plaques]
        json_output = json.dumps(plaque_dicts)
        return json_output

    def _json_for_keys(self, plaque_keys_str=None, summary=True):
        self.json_for_all(summary)
        plaque_keys = plaque_keys_str.split('&')

        plaques = []
        for plaque_key in plaque_keys:
            try:
                plaque = ndb.Key(urlsafe=plaque_key).get()
                plaques.append(plaque)
            except ProtocolBuffer.ProtocolBufferDecodeError:
                pass
        plaques = [p for p in plaques if p] # Remove empties

        if not plaques:
            json_output = ''
        else:
            json_output = self._plaques_to_json(plaques, summary)

        return json_output

    def _json_for_update(self, updated_on, summary=True):
        logging.info("Updated_on is %s in _json_for_update" % updated_on)
        plaques = Plaque.query(
                       ).filter(Plaque.approved == True
                       ).filter(Plaque.created_on > updated_on
                       ).order(-Plaque.created_on
                       ).fetch()
        logging.info("_json_for_update got %s plaques" % len(plaques))
        for i, plaque in enumerate(plaques):
            logging.info("_json_for_update plaque %s date: %s" % (
                i, plaque.updated_on))
        json_output = self._plaques_to_json(plaques, summary)
        return json_output

    def _json_for_all(self, summary=True):
        plaques_all = []
        num = 1000
        more = True
        cursor = None
        while more:
            plaques, cursor, more = Plaque.fetch_page(
                num=num, start_cursor=cursor, urlsafe=False)
            plaques_all.extend(plaques)
            logging.info("tot: %s, current: %s, cursor: %s, more?: %s" % (
                len(plaques_all), len(plaques_all), cursor, more))

        json_output = self._plaques_to_json(plaques_all, summary)
        return json_output

    def get(self, plaque_keys_str=None, summary=True):
        """
        Does all the plaques, unless keys are specified, in which case it only
        does those plaques.
        """
        if plaque_keys_str is not None:
            logging.info("plaque_keys_str is not None")
            json_output = self._json_for_keys(plaque_keys_str, summary)
        else:
            logging.info("plaque_keys_str is None")
            json_output = self._json_for_all(summary)
        self.response.write(json_output)

    def post(self):
        """Updates just the new plaques."""
        date_fmt =  "%Y-%m-%d %H:%M:%S.%f"
        updated_on_str = self.request.get('updated_on')
        updated_on = datetime.datetime.strptime(updated_on_str, date_fmt)
        logging.info('updated_on_str: %s, updated_on %s' % (
            updated_on_str, updated_on))
        json_output = self._json_for_update(updated_on, summary=True)
        self.response.write(json_output)

class JsonAllPlaquesFull(JsonAllPlaques):
    """
    Dump the full json.

    Expensive, don't use this more often than necessary..
    """
    def get(self):
        json_output = self._json_for_all(summary=False)
        self.response.write(json_output)


#class ViewAllTags(webapp2.RequestHandler):
#    def get(self):
#        tags_sized = Plaque.all_tags_sized()
#        template = JINJA_ENVIRONMENT.get_template('tags.html')
#        template_values = get_template_values(tags=tags_sized)
#        self.response.write(template.render(template_values))

class ViewTag(webapp2.RequestHandler):
    def get(self, tag, view_all=False):
        """
        View plaques with a given tag on a grid.
        """
        memcache_name = 'plaques_tag_%s' % tag
        page_text = memcache.get(memcache_name)

        if page_text is None:
            query = Plaque.query()
            if not view_all:
                query = query.filter(Plaque.approved == True)

            # TODO: NDB cursor pagination?
            plaques = query.filter(Plaque.tags == tag
                           ).order(-Plaque.created_on
                           ).fetch(limit=DEF_NUM_PER_PAGE)

            template = JINJA_ENVIRONMENT.get_template('all.html')
            template_values = get_template_values(plaques=plaques)
            page_text = template.render(template_values)
            memcache_status = memcache.set(memcache_name, page_text)
            if not memcache_status:
                logging.debug("ViewTag memcache.set for %s failed" %
                    memcache_name)
        else:
            logging.debug("ViewTag memcache.get worked for %s" %
                memcache_name)

        self.response.write(page_text)

class About(webapp2.RequestHandler):
    def get(self):
        """
        Render the About page from the common template.
        """
        template = JINJA_ENVIRONMENT.get_template('about.html')
        template_values = get_template_values()
        self.response.write(template.render(template_values))

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
                    url = message
                    title = message.split('/')[-1]

                    message = """Thanks, admin!
                        <a style="float: right" href="%s">%s</a>""" % (url, title)
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
        template_values = get_template_values(maptext=maptext, mapzoom=10, page_title="Add Plaque")
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

        try:
            plaqueset_name = self.request.get('plaqueset_name',
                                              DEF_PLAQUESET_NAME)
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
            #logging.info('creating email')
            post_type = 'Updated' if is_edit else 'New'
            user = users.get_current_user()
            name = "anon" if user is None else user.nickname()
            msg = '%s %s plaque! %s' %  (name, post_type, plaque.title_page_url)
            body = """
<p>
    <a href="https://readtheplaque.com{1.title_page_url}">
        {0} plaque!
    </a>
</p>
<p>
    <a href="https://readtheplaque.com{1.title_page_url}">
        <img alt="plaque alt" title="plaque title" src="{1.img_url}"/>
    </a>
</p>
            """.format(post_type, plaque)
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
        if title != plaque.title:
            plaque.title = title
            plaque.set_title_url(plaqueset_key)
        else:
            plaque.title = title

        plaque.description = description
        plaque.tags = tags
        if not is_edit:
            plaque.approved = False
        plaque.updated_on = datetime.datetime.now()

        # Upload the image for a new plaque, or update the image for an
        # editted plaque, if specified.
        is_upload_pic = (is_edit and img_name is not None) or (not is_edit)
        if is_upload_pic:
            #TODO openbenches: disable upload here?
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

    def _get_latlng_exif(self, img_fh):
        logging.info("Getting exif lat lng in _get_latlng_exif")
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS

        gps_data = {}
        image = Image.open(img_fh)
        info = image._getexif()
        img_fh.seek(0) # reset file handle
        if info:
            for tag, value in info.items():
                decoded = TAGS.get(tag, tag)
                if decoded == "GPSInfo":
                    for gps_tag in value:
                        gps_tag_decoded = GPSTAGS.get(gps_tag, gps_tag)
                        gps_data[gps_tag_decoded] = value[gps_tag]

        try:
            gps_lat = gps_data['GPSLatitude']
            gps_lng = gps_data['GPSLongitude']
        except KeyError:
            pass # TODO: is this right?

        gps_lat_angles = (
            float(gps_lat[0][0]) / float(gps_lat[0][1]), # degrees
            float(gps_lat[1][0]) / float(gps_lat[1][1]), # hours
            float(gps_lat[2][0]) / float(gps_lat[2][1]), # minutes
        )
        gps_lng_angles = (
            float(gps_lng[0][0]) / float(gps_lng[0][1]), # degrees
            float(gps_lng[1][0]) / float(gps_lng[1][1]), # hours
            float(gps_lng[2][0]) / float(gps_lng[2][1]), # minutes
        )
        gps_lat_ref = gps_data['GPSLatitudeRef'] # N/S
        gps_lng_ref = gps_data['GPSLongitudeRef'] # E/W

        lat = latlng_angles_to_dec(gps_lat_ref, gps_lat_angles)
        lng = latlng_angles_to_dec(gps_lng_ref, gps_lng_angles)

        logging.info('Converting "%s %s, %s %s" to "%s %s"' % (
            gps_lat_ref, gps_lat_angles, gps_lng_ref, gps_lng_angles, lat, lng))

        return lat, lng

    def _get_location(self, img_fh):
        # If the location has been specified, use that:
        lat = self.request.get('lat')
        lng = self.request.get('lng')

        # If it hasn't, but there's something in the search field, try that:
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

        # If that doesn't work, try to get the location from the image's EXIF
        # info:
        try:
            location = ndb.GeoPt(lat, lng)
        except BadValueError as bve:
            logging.error(bve)

            try:
                lat, lng = self._get_latlng_exif(img_fh)
                location = ndb.GeoPt(lat, lng)
            except Exception as err2:
                logging.error(err2)
                err = SubmitError(
                    "The plaque location wasn't specified. Please click the "
                    "back button, select a location, and click 'Add your "
                    "Plaque' again. Error (%s)" % err2)
                raise err

        return location

    def _get_img(self, img_file=None, img_url=None):
        """
        Prefer the file to the URL, if both are given.
        """
        if img_file != '' and img_file is not None:
            img_name = img_file.filename
            img_fh = img_file.file
        elif img_url != '':
            img_name = os.path.basename(img_url)
            img_fh = urllib.urlopen(img_url)
            # TODO: Raise error if the img_url doesn't point at an image
            # TODO openbenches: disable the image download here?
        else:
            img_name = None
            img_fh = None
            #don't do anything (for edits where the image isn't being updated)

        return img_name, img_fh

    def _get_form_args(self):
        """Get the arguments from the form and return them."""

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

        # TODO openbenches: disable the image download here
        img_name, img_fh = self._get_img(img_file, img_url)

        location = self._get_location(img_fh)

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

        # TODO openbenches: set plaque.pic to None?
        # TODO openbenches: skip this try block, set plaque.img_url and return immediately?
        # TODO openbenches: set img_url to the hotlink URL?

        # Write image to GCS
        try:
            ct = 'image/jpeg'
            op = {b'x-goog-acl': b'public-read'}
            with gcs.open(gcs_filename, 'w', content_type=ct, options=op) as fh:
                img_contents = img_fh.read()
                fh.write(img_contents)

            # Make serving_url for image:
            blobstore_gs_key = blobstore.create_gs_key('/gs' + gcs_filename)
            plaque.img_url = images.get_serving_url(blobstore_gs_key)

        except AttributeError:
            submit_err = SubmitError("The image for the plaque was not "
                                     "specified-- please click the back button "
                                     "and resubmit.")
            logging.error(submit_err)
            raise submit_err

class DuplicateChecker(AddPlaque):
    def post(self):
        title_raw = self.request.POST.get('title_url')
        title = Plaque.tokenize_title(title_raw)
        n_matches = Plaque.num_same_title_urls_published(title, get_plaqueset_key())
        response_text = title if n_matches > 0 else ""
        self.response.write(response_text)

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
            'loginout': loginout()
        }
        if message is not None:
            template_values['message'] = message

        logging.debug("In EditPlaque, img_rot is {.img_rot}".format(plaque))
        template = JINJA_ENVIRONMENT.get_template('edit.html')
        self.response.write(template.render(template_values))

    def post(self):
        if users.is_current_user_admin():
            super(EditPlaque, self).post(is_edit=True)


class SearchPlaques(webapp2.RequestHandler):
    """Run a search in the title and description."""
    def post(self):
        search_term = self.request.get('search_term')
        self.redirect('/search/%s' % search_term)

    def _search_plaques(self, search_term):
        search_term = '"%s"' % search_term.replace('"', '') #search_term.encode('unicode-escape')
        search_term = str(search_term.decode("ascii", "ignore")) # TODO: this doesn't crash on e.g. 'Piñata'

        plaque_search_index = search.Index(PLAQUE_SEARCH_INDEX_NAME)
        results = plaque_search_index.search(search_term)

        plaques = [ndb.Key(urlsafe=r.doc_id).get() for r in results]
        plaques = [p for p in plaques if p is not None]

        return plaques

    def get(self, search_term=None):
        if search_term is None:
            plaques = []
        else:
            # TODO: NDB cursor pagination?
            plaques = self._search_plaques(search_term)

            # Allow admin to see unpublished plaques, hide these from others
            if not users.is_current_user_admin():
                plaques = [p for p in plaques if p.approved]

        template = JINJA_ENVIRONMENT.get_template('all.html')
        template_values = get_template_values(plaques=plaques)
        self.response.write(template.render(template_values))

class SearchPlaquesPending(SearchPlaques):
    """Admin-only: a search the un-approved plaques."""

    def post(self):
        raise NotImplementedError("POST not allowed for SearchPlaquesPending")

    def get(self, search_term=None):
        logging.info("SearchPlaquesPending: search_term: {}".format(search_term))

        logging.info("SearchPlaquesPending: IS admin")
        # Unpublished plaques matching the search term:
        plaques = self._search_plaques(search_term)
        logging.info("SearchPlaquesPending: number of plaques {}".format(len(plaques)))
        plaques = [p for p in plaques if not p.approved]
        logging.info("SearchPlaquesPending: number of not-approved plaques {}".format(len(plaques)))

        template = JINJA_ENVIRONMENT.get_template('all.html')
        template_values = get_template_values(plaques=plaques)
        self.response.write(template.render(template_values))

class SearchPlaquesGeo(webapp2.RequestHandler):
    """Run a geographic search: plaques within radius of center are returned."""

    def _geo_search(self, lat=None, lng=None, search_radius_meters=5000):
        """
        Return plaques within search_radius_meters of lat/lng, sorted by
        distance from lat/lng.
        """
        search_radius_meters = int(search_radius_meters)
        plaque_search_index = search.Index(PLAQUE_SEARCH_INDEX_NAME)

        loc_expr = 'distance(location, geopoint({}, {}))'.format(lat, lng)
        query    = '{} < {}'.format(loc_expr, search_radius_meters)
        sortexpr = search.SortExpression(
            expression=loc_expr,
            direction=search.SortExpression.ASCENDING,
            default_value=search_radius_meters)

        search_query = search.Query(
            query_string=query,
            options=search.QueryOptions(
                sort_options=search.SortOptions(expressions=[sortexpr])
        ))

        results = plaque_search_index.search(search_query)
        keys = [ndb.Key(urlsafe=r.doc_id) for r in results]
        raw_plaques = ndb.get_multi(keys)
        plaques = [p for p in raw_plaques if p is not None and p.approved]
        return plaques

    def _serve_form(self, redir):
        maptext = 'Click the map, or type a search here'
        step1text = 'Click the map to pick where to search'
        if redir:
            step1text = '<span style="color:red">%s</span>' % step1text

        template_values = get_template_values(
            maptext=maptext, step1text=step1text)
        template = JINJA_ENVIRONMENT.get_template('geosearch.html')
        self.response.write(template.render(template_values))

    def _write_geo_page(self, geo_plaques_approved, lat, lng):
        template = JINJA_ENVIRONMENT.get_template('all.html')
        template_values = get_template_values(
            plaques=geo_plaques_approved,
            mapcenter={'lat': lat, 'lng': lng})
        self.response.write(template.render(template_values))

    def _serve_response(self, lat, lng, search_radius_meters):
        geo_plaques_approved = self._geo_search(lat, lng, search_radius_meters)
        self._write_geo_page(geo_plaques_approved, lat, lng)

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

class NearbyPage(SearchPlaquesGeo):
    """
    Run successively larger geo searches, stopping when num plaques are found.
    """
    def get(self, lat, lng, num=DEF_NUM_NEARBY):
        # 8m to 1600 km, in geometric steps
        try:
            num = int(num)
        except:
            num = DEF_NUM_NEARBY

        #TODO: NDB cursor pagination
        if num > 20:
            num = 20

        # Reduce search billing cost by making nearby search less granular:
        # 5 m, 500 m, 5 km, 50 km, 500 km, 5000 km
        search_radii_meters = [5*10**i for i in [1, 3, 4, 5, 6, 7]]
        for i, search_radius_meters in enumerate(search_radii_meters):
            logging.info(
                "%s/%s: searching within %s meters of (%s,%s)" % (
                i+1, len(search_radii_meters), search_radius_meters, lat, lng))
            plaques = self._geo_search(lat, lng, search_radius_meters)
            logging.info("Found %s plaques" % len(plaques))
            if len(plaques) > num:
                break

        self._write_geo_page(plaques, lat, lng)

class FlushMemcache(webapp2.RequestHandler):
    def get(self):
        memcache.flush_all()
        self.redirect('/')

    def post(self):
        memcache.flush_all()
        self.redirect('/')

class Counts(webapp2.RequestHandler):
    def get(self):
        compact = self.request.get('compact')
        query = Plaque.query()
        num_plaques = query.count()
        num_pending = query.filter(Plaque.approved == False).count()

        if compact:
            tmpl = "{} published, {} pending"
        else:
            tmpl = "<ul> <li>{} published</li> <li>{} pending</li> </ul>"

        msg = tmpl.format(num_plaques - num_pending, num_pending)
        self.response.write(msg)

class DeleteOnePlaque(webapp2.RequestHandler):
    def get(self):
        raise NotImplementedError("no get in DeleteOnePlaque")

    @ndb.transactional
    def post(self):
        """Remove one plaque and its associated GCS image."""
        user = users.get_current_user()
        if not users.is_current_user_admin():
            return "admin only, please log in"
        name = "anon" if user is None else user.nickname()

        plaque_key = self.request.get('plaque_key')
        plaque = ndb.Key(urlsafe=plaque_key).get()

        if name != 'kester':
            email_admin('Delete warning!', '%s tried to delete %s' % (
                name, plaque.title_url))
            raise NotImplementedError("delete is turned off for now")

        try:
            gcs.delete(plaque.pic)

            # Delete search index for this document
            plaque_search_index = search.Index(PLAQUE_SEARCH_INDEX_NAME)
            results = plaque_search_index.search(search_term)
            for result in results:
                plaques = [ndb.Key(urlsafe=r.doc_id).get() for r in results]
                plaque_search_index.delete(result.doc_id)
        except:
            pass

        plaque.key.delete()
        #memcache.flush_all()
        email_admin('%s Deleted plaque %s' % (name, plaque.title_url),
                    '%s Deleted plaque %s' % (name, plaque.title_url))
        self.redirect('/nextpending')

class ViewNextPending(ViewOnePlaqueParent):
    def get(self):
        plaques = Plaque.pending_list(1)
        if plaques:
            plaque = plaques[0]
            logging.info("redirecting to {}".format(plaque.title_page_url))
            self.redirect(plaque.title_page_url)
            return
        else:
            page_text =  self._get_page_from_key(plaque_key=None)
            self.response.write(page_text)

class ViewPending(webapp2.RequestHandler):
    def write_pending(self, plaques):

        user = users.get_current_user()
        name = "anon" if user is None else user.nickname()
        logging.info("User %s is viewing pending plaques %s" % (name, plaques))

        template = JINJA_ENVIRONMENT.get_template('all.html')
        template_values = get_template_values(plaques=plaques, is_pending=True)
        template_text = template.render(template_values)
        self.response.write(template_text)

    def get(self, num=DEF_NUM_PENDING):
        try:
            num = int(num)
        except:
            pass
        plaques = Plaque.pending_list(num)
        self.write_pending(plaques)

class ViewOldPending(ViewPending):
    def get(self, num=DEF_NUM_PENDING):
        try:
            num = int(num)
        except:
            pass
        plaques = Plaque.pending_list(num=num, desc=False)
        self.write_pending(plaques)


class ViewPendingRandom(ViewPending):
    def get(self, num=DEF_NUM_PENDING):
        try:
            num = int(num)
        except:
            pass

        num_to_select_from = 500
        plaques = Plaque.pending_list(num_to_select_from)
        return_plaques = random.sample(plaques, num)

        self.write_pending(return_plaques)

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

class RedoIndex(webapp2.RequestHandler):
    def get(self):
        plaque_search_index = search.Index(PLAQUE_SEARCH_INDEX_NAME)
        ideleted = 0
        # Delete all the search documents
        while True:
            # Get a list of documents populating only the doc_id field and
            # extract the ids.
            document_ids = [
                document.doc_id for document
                    in plaque_search_index.get_range(ids_only=True)]
            ideleted += len(document_ids)
            if not document_ids:
                break
            # Delete the documents for the given ids from the Index.
            plaque_search_index.delete(document_ids)
        logging.debug('deleted %s search index docs' % ideleted)

        # Write all new search docs and put them in the index
        plaques = Plaque.query().fetch()
        docs = []
        igood = 0
        ibad = 0
        for plaque in plaques:
            try:
                docs.append(plaque.to_search_document())
                igood += 1
            except search.Error as err:
                ibad += 1
                logging.error(err)
            #if ip % 100 == 0:
                #logging.debug('in process: wrote %s good docs, %s failed' % (
                              #igood, ibad))
        iput = 0
        for i in range(0, len(docs), 100):
            iput += 100
            plaque_search_index.put(docs[i:i+100])

        self.response.write(
            'deleted %s docs, created %s, failed to create %s, put %s' % (
            ideleted, igood, ibad, iput))

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

        #raise NotImplementedError("Turned off")

        if not users.is_current_user_admin():
            return "admin only, please log in"
        plaques = Plaque.pending_list(num=67)

        user = users.get_current_user()
        name = "anon" if user is None else user.nickname()
        msg = "%s ran ApproveAllPending on %s plaques" % (name, len(plaques))
        email_admin(msg, msg)

        logging.info("Approving %s plaques in ApproveAllPending" % len(plaques))
        for plaque in plaques:
            plaque.approved = True
            plaque.put()
        memcache.flush_all()
        self.redirect('/')

class ApprovePending(webapp2.RequestHandler):
    """Approve a plaque"""
    @ndb.transactional
    def post(self):
        if not users.is_current_user_admin():
            return "admin only, please log in"

        plaque_key = self.request.get('plaque_key')
        plaque = ndb.Key(urlsafe=plaque_key).get()
        title = plaque.title.encode('unicode-escape')
        logging.info("Approving plaque %s" % title)
        plaque.approved = True
        plaque.created_on = datetime.datetime.now()
        plaque.put()

        #user = users.get_current_user()
        #name = "anon" if user is None else user.nickname()
        #msg = "{1} approved plaque {0}".format(title, name)
        #email_admin(msg, msg)

        self.redirect('/nextpending')

class DisapprovePlaque(webapp2.RequestHandler):
    """Disapprove a plaque"""
    @ndb.transactional
    def post(self):
        if not users.is_current_user_admin():
            return "admin only, please log in"

        plaque_key = self.request.get('plaque_key')
        plaque = ndb.Key(urlsafe=plaque_key).get()
        title = plaque.title.encode('unicode-escape')
        logging.info("disapproving plaque {0}".format(title))
        plaque.approved = False
        plaque.put()

        user = users.get_current_user()
        name = "anon" if user is None else user.nickname()
        msg = "{1} disapproved plaque {0}".format(title, name)
        email_admin(msg, msg)

        self.redirect('/')

class Ocr(webapp2.RequestHandler):
    def get(self, img_url=None):
        with open('key_googlevision.txt') as key_fh:
            key = key_fh.read()
        url = "https://vision.googleapis.com/v1/images:annotate?key=" + key
        data = json.dumps({
            "requests": [{
                "image": { "source": { "imageUri": img_url } },
                "features": [ { "type": "TEXT_DETECTION" } ],
            }]
        })
        req = urllib2.Request(
            url,
            data,
            {'Content-Type': 'application/json', 'Content-Length': len(data)})
        f = urllib2.urlopen(req)
        response = f.read()
        f.close()
        report = json.loads(response)

        if 'error' in report['responses'][0]:
            self.response.write("data {}".format(data))
            self.response.write("error {}".format(report))
            return

        description = report['responses'][0]['textAnnotations'][0]['description']
        ocr_text = description.replace('\n', '\n <br/> ')
        self.response.write(ocr_text)

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

