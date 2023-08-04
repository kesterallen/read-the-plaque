# -*- coding: utf-8 -*-

#TODO: New uploader for Openbenches (auto approve)
#TODO: new class to lazyload the openbenches images
#           * might need new column in Plaque to indicate if a given row has been loaded or not

import jinja2
import json
import logging
import os
import random
import urllib2

import webapp2
from google.appengine.api import memcache
from google.appengine.api import search
from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.ext.ndb.google_imports import ProtocolBuffer
import lib.cloudstorage as gcs

from utils import (
    DEF_NUM_PENDING,
    PLAQUE_SEARCH_INDEX_NAME,
    SubmitError,
    email_admin,
    get_key,
    get_random_plaque,
    get_random_plaque_key,
    get_template_values,
)
from Models import Plaque, FeaturedPlaque

DEF_PLAQUESET_NAME = 'public'
DEF_NUM_PER_PAGE = 25
DEF_RAND_NUM_PER_PAGE = 5

# Load templates from the /templates dir
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__), 'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=False, # turn off autoescape to allow html descriptions
)
def _render_template(filename, template_args):
    """Render template_args into filename"""
    template = JINJA_ENVIRONMENT.get_template(filename)
    return template.render(template_args)

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

def _handle_error(code, request, response, exception, is_email=True):
    error_text = '{}\n{}\n{}\n{}'.format(code, request, response, exception)
    logging.error(error_text)
    if is_email:
        email_admin("error in RTP", error_text)
    text_ = _render_template("error.html", {'code': code, 'error_text': error_text})
    response.write(text_)
    response.set_status(code)

def handle_404(request, response, exception):
    _handle_error(404, request, response, exception)

def handle_500(request, response, exception):
    _handle_error(500, request, response, exception, is_email=False)

def make_memcache_name(*args):
    return "_".join([str(x) for x in args])

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

    def get(self, cursor=None):
        template_text = self._get_template_text(cursor, is_random=False, is_featured=True)
        self.response.write(template_text)

    def _get_template_text(
        self,
        cursor=None,
        per_page=DEF_NUM_PER_PAGE,
        is_random=False,
        is_featured=True,
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

        memcache_name = make_memcache_name("plaques", per_page, cursor, is_admin)
        text_ = None if is_random else memcache.get(memcache_name)

        if text_ is None:
            values = self._get_template_values(per_page, cursor, is_random, is_featured)
            text_ = _render_template("all.html", values)
            if not is_random:
                memcache_status = memcache.set(memcache_name, text_)

        return text_

    def _get_template_values(self, per_page, cursor, is_random, is_featured):
        if is_random:
            plaques = [get_random_plaque() for _ in range(per_page)]
            cursor = None
            more = False
        else:
            plaques, next_cursor, more = Plaque.fetch_page(
                per_page, startcur=cursor, urlsafe=True)
            cursor = '' if next_cursor is None else next_cursor.urlsafe()

        template_values = get_template_values(
            plaques=plaques, next_cursor_urlsafe=cursor, more=more)
        if is_featured:
            featured = get_featured()
            template_values['featured_plaque'] = featured
            fake = FakePlaqueForRootUrlPreviews()
            template_values['fake_plaque_for_root_url_previews'] = fake

        return template_values

class ViewOnePlaqueParent(webapp2.RequestHandler):
    def get(self):
        raise NotImplementedError("Don't call ViewOnePlaqueParent.get directly")

    def _get_plaque_from_title_url_or_key(self, url_or_key=None):
        """ 
        Get a plaque by its title_url, its key, or return None 
        """
        plaque = None
        if url_or_key is not None:
            # Get by title, allowing only admins to see unapproved ones:
            query = Plaque.query().filter(Plaque.title_url == url_or_key)
            if not users.is_current_user_admin():
                query = query.filter(Plaque.approved == True)
            plaque = query.get()

            if plaque is None:
                try:
                    plaque = ndb.Key(urlsafe=url_or_key).get()
                except:
                    pass
        return plaque

    def _get_page_from_url_or_key(self, search_term=None):
        """
        Put the single plaque into a list for rendering so that the common map
        functionality can be used unchanged. Attempt to serve a valid plaque,
        but if the inputs are completely messed up, serve the oldest plaque.
        """

        # If it's memecached, use that:
        is_admin = users.is_current_user_admin()
        memcache_name = make_memcache_name('plaque_', search_term, is_admin)
        text_ = memcache.get(memcache_name)
        if text_ is not None:
            return text_

        # If page is not memcached, get the plaque from the db:
        plaque = self._get_plaque_from_title_url_or_key(search_term)

        # If that didn't find anything, serve the default couldn't-find-it
        # plaque (currently hacked in as the earliest plaque):
        if plaque is None:
            earliest_plaque = Plaque.query(
                Plaque.approved == True).order(Plaque.created_on).get()
            self.redirect(earliest_plaque.title_page_url)
            return

        text_ = _render_template("one.html", get_template_values(plaques=[plaque]))
        return text_

class ViewOnePlaque(ViewOnePlaqueParent):
    """
    Render the single-plaque page from a plaque key, or get a random plaque.
    """
    def head(self, search_term=None, ignored_cruft=None):
        self.get(search_term=None, ignored_cruft=None)
        self.response.clear()

    def get(self, search_term=None, ignored_cruft=None):
        text_ = self._get_page_from_url_or_key(search_term=search_term)
        self.response.write(text_)

class ViewFeatured(ViewOnePlaqueParent):
    def get(self):
        plaque = get_featured()
        text_ = self._get_page_from_url_or_key(search_term=plaque.title_url)
        self.response.write(text_)

class GeoJsonFeatured(ViewFeatured):
    def get(self):
        """ Get featured plaque's geoJSON """
        plaque = get_featured()
        if plaque:
            self.response.write(plaque.json_for_tweet)
        else:
            self.response.write("the featured plaque is not found")

class ViewNextPending(ViewOnePlaqueParent):
    def get(self):
        plaques = Plaque.pending_list(1)
        if plaques:
            plaque = plaques[0]
            logging.info("redirecting to {}".format(plaque.title_page_url))
            self.redirect(plaque.title_page_url)
            return
        else:
            text_ =  self._get_page_from_url_or_key(search_term=None)
            self.response.write(text_)

class ViewPending(webapp2.RequestHandler):
    def write_pending(self, plaques):

        user = users.get_current_user()
        name = "anon" if user is None else user.nickname()
        logging.info("User %s is viewing pending plaques %s" % (name, plaques))

        template_values = get_template_values(plaques=plaques, is_pending=True)
        text_ = _render_template("all.html", template_values)
        self.response.write(text_)

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

class RandomPlaquesPage(ViewPlaquesPage):
    """
    Get a page of random plaques.
    """
    def get(self, per_page=DEF_RAND_NUM_PER_PAGE):
        text_ = self._get_template_text(per_page=per_page, is_random=True, is_featured=False)
        self.response.write(text_)

class RandomPlaque(ViewOnePlaqueParent):
    """
    Get a single random plaque.
    """
    def get(self):
        plaque = get_random_plaque()
        self.redirect(plaque.title_page_url)

class SetFeaturedRandom(ViewOnePlaqueParent):
    """
    Get a random plaque and set it to be the featured plaque.
    """
    def get(self):
        plaque_key = get_random_plaque_key()
        plaque = ndb.Key(urlsafe=plaque_key).get()
        set_featured(plaque)
        memcache.flush_all()
        self.response.write(plaque.json_for_tweet)

class JsonAllPlaques(webapp2.RequestHandler):
    """ Get the JSON representation for a group of plaques """

    def _plaques_to_json(self, plaques, summary=True):
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

        if plaques:
            json_output = self._plaques_to_json(plaques, summary)
        else:
            json_output = ''

        return json_output

    def _json_for_all(self, summary=True):
        plaques_all = []
        num = 1000
        more = True
        cursor = None
        while more:
            plaques, cursor, more = Plaque.fetch_page(
                num=num, startcur=cursor, urlsafe=False)
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
            json_output = self._json_for_keys(plaque_keys_str, summary)
        else:
            json_output = self._json_for_all(summary)
        self.response.write(json_output)

    def post(self):
        """Returns the JSON for plaques with updated_on after the specified date."""
        updated_on_str = self.request.get('updated_on')
        plaques = Plaque.created_after(updated_on_str)
        json_output = self._plaques_to_json(plaques, summary)
        self.response.write(json_output)

class JsonAllPlaquesFull(JsonAllPlaques):
    """
    Dump the full json.

    Expensive, don't use this more often than necessary..
    """
    def get(self):
        json_output = self._json_for_all(summary=False)
        self.response.write(json_output)

class GeoJson(ViewOnePlaqueParent):
    def get(self, search_term=None):
        """ Get one plaque's geoJSON """
        plaque = self._get_plaque_from_title_url_or_key(search_term)
        if plaque is None:
            self.response.write("plaque {} not found".format(search_term))
        else:
            self.response.write(plaque.geojson)

    def post(self):
        """Returns the JSON for plaques with updated_on after the specified date."""
        updated_on_str = self.request.get('updated_on')
        plaques_geojson = Plaque.created_after_geojson(updated_on_str)
        self.response.write(json.dumps(plaques_geojson))

class ViewTag(webapp2.RequestHandler):
    def get(self, tag, view_all=False):
        """
        View plaques with a given tag on a grid.
        """
        memcache_name = make_memcache_name('plaques_tag_', tag)
        text_ = memcache.get(memcache_name)

        if text_ is None:
            query = Plaque.query()
            if not view_all:
                query = query.filter(Plaque.approved == True)

            # TODO: NDB cursor pagination?
            plaques = query.filter(Plaque.tags == tag
                           ).order(-Plaque.created_on
                           ).fetch(limit=DEF_NUM_PER_PAGE)

            text_ = _render_template("all.html", get_template_values(plaques=plaques))

        self.response.write(text_)

class About(webapp2.RequestHandler):
    def get(self):
        """
        Render the About page from the common template.
        """
        text = _render_template("about.html", get_template_values())
        self.response.write(text)
class BigMap(ViewPlaquesPage):
    @property
    def template_file(self):
        return "bigmap.html"

    def get(self, lat=None, lng=None, zoom=None):

        template_values = get_template_values(bigmap=True)
        num_plaques = Plaque.query().filter(Plaque.approved == True).count()
        template_values['counts'] = num_plaques

        if lat is not None and lng is not None:
            template_values['bigmap_center'] = True
            template_values['bigmap_lat'] = lat
            template_values['bigmap_lng'] = lng

            if zoom is not None:
                template_values['bigmap_zoom'] = zoom

        text_ = _render_template(self.template_file, template_values)
        self.response.write(text_)

class ExifText(BigMap):
    @property
    def template_file(self):
        return "exif.html"

    def get(self):
        text_ = _render_template(self.template_file, get_template_values())
        self.response.write(text_)

class Ocr(webapp2.RequestHandler):
    def get(self, img_url=None):
        key = get_key("key_googlevision.txt")
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
        resp = urllib2.urlopen(req)
        response = resp.read()
        resp.close()
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
        self.response.write(_render_template("feed.xml", {'plaques': plaques}))

