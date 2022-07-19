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
    email_admin,
    get_random_plaque,
    get_random_plaque_key,
    get_template_values,
    latlng_angles_to_dec,
    loginout,
    PLAQUE_SEARCH_INDEX_NAME,
    SubmitError,
)
from Models import Plaque, FeaturedPlaque

DEF_PLAQUESET_NAME = 'public'

DEF_NUM_PER_PAGE = 25
DEF_NUM_NEARBY = 5
DEF_MAP_ICON_SIZE_PIX = 16

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

def _handle_error(code, request, response, exception, is_email=True):
    error_text = '{} error!\n\n{}\n\n{}\n\n{}'.format(code, request, response, exception)
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
        memcache_name = make_memcache_name('plaque_', plaque_key, is_admin)
        text_ = memcache.get(memcache_name)
        if text_ is not None:
            return text_

        # If page is not memcached, get the plaque from the db:
        plaque = self._get_plaque_from_key(plaque_key)

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
    def head(self, plaque_key=None, ignored_cruft=None):
        self.get(plaque_key=None, ignored_cruft=None)
        self.response.clear()

    def get(self, plaque_key=None, ignored_cruft=None):
        text_ = self._get_page_from_key(plaque_key=plaque_key)
        self.response.write(text_)

class RandomPlaquesPage(ViewPlaquesPage):
    """
    Get a page of random plaques.
    """
    def get(self, per_page=5):
        text_ = self._get_template_text(per_page=per_page, is_random=True, is_featured=False)
        self.response.write(text_)

class RandomPlaque(ViewOnePlaqueParent):
    """
    Get a single random plaque.
    """
    def get(self):
        plaque = get_random_plaque()
        self.redirect(plaque.title_page_url)

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

        if not plaques:
            json_output = ''
        else:
            json_output = self._plaques_to_json(plaques, summary)

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
            logging.info("plaque_keys_str is not None")
            json_output = self._json_for_keys(plaque_keys_str, summary)
        else:
            logging.info("plaque_keys_str is None")
            json_output = self._json_for_all(summary)
        self.response.write(json_output)

    def post(self):
        """Returns the JSON for plaques with updated_on after the specified date."""
        updated_on_str = self.request.get('updated_on')
        plaques = Plaque.created_after(updated_on_str)
        json_output = self._plaques_to_json(plaques, summary)

        self.response.write(json_output)

class GeoJson(ViewOnePlaqueParent):

    def get(self, plaque_key=None):
        """ Get one plaque's geoJSON """
        plaque = self._get_plaque_from_key(plaque_key)
        self.response.write(plaque.geojson)

    def post(self):
        """Returnes the JSON for plaques with updated_on after the specified date."""
        updated_on_str = self.request.get('updated_on')
        plaques_geojson = Plaque.created_after_geojson(updated_on_str)
        self.response.write(json.dumps(plaques_geojson))

class JsonAllPlaquesFull(JsonAllPlaques):
    """
    Dump the full json.

    Expensive, don't use this more often than necessary..
    """
    def get(self):
        json_output = self._json_for_all(summary=False)
        self.response.write(json_output)

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

class SearchPlaques(webapp2.RequestHandler):
    """Run a search in the title and description."""
    def post(self):
        search_term = self.request.get('search_term')
        self.redirect('/search/{}'.format(search_term))

    def _search_plaques(self, search_term):
        search_term = '"{}"'.format(search_term.replace('"', '')) #search_term.encode('unicode-escape')
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

        template_values = get_template_values(plaques=plaques)
        self.response.write(_render_template("all.html", template_values))

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

        template_values = get_template_values(plaques=plaques)
        self.response.write(_render_template("all.html", template_values))

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

        template_values = get_template_values(maptext=maptext, step1text=step1text)
        self.response.write(_render_template("geosearch.html", template_values))

    def _write_geo_page(self, geo_plaques_approved, lat, lng):
        template_values = get_template_values(
            plaques=geo_plaques_approved,
            mapcenter={'lat': lat, 'lng': lng}
        )
        self.response.write(_render_template("all.html", template_values))

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

class Counts(webapp2.RequestHandler):
    def get(self):
        verbose = self.request.get('verbose')
        query = Plaque.query()
        num_plaques = query.count()
        num_pending = query.filter(Plaque.approved == False).count()
        num_published = num_plaques - num_pending


        if verbose:
            tmpl = "<ul> <li>{} published</li> <li>{} pending</li> </ul>"
        else:
            tmpl = "{} published, {} pending\n"

        msg = tmpl.format(num_published, num_pending)
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
            text_ =  self._get_page_from_key(plaque_key=None)
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

# Disabled
class ApproveAllPending(webapp2.RequestHandler):
    """Approve all pending plaques"""
    def get(self):
        raise NotImplementedError("Turned off")

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
    @classmethod
    def toggle_approval(cls, plaque_key, approval=True):
        plaque = ndb.Key(urlsafe=plaque_key).get()

        plaque.approved = approval
        if plaque.approved:
            plaque.created_on = datetime.datetime.now()
            plaque.updated_on = datetime.datetime.now()
        plaque.put()

    """Approve a plaque"""
    @ndb.transactional
    def post(self):
        if not users.is_current_user_admin():
            return "admin only, please log in"

        plaque_key = self.request.get('plaque_key')
        ApprovePending.toggle_approval(plaque_key)
        self.redirect('/nextpending')

class DisapprovePlaque(ApprovePending):
    """Disapprove a plaque"""
    @ndb.transactional
    def post(self):
        if not users.is_current_user_admin():
            return "admin only, please log in"

        plaque_key = self.request.get('plaque_key')
        self.toggle_approval(plaque_key, approval=False)
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
