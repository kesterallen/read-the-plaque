# -*- coding: utf-8 -*-

import logging
import webapp2

from google.appengine.api import search
from google.appengine.api import users
from google.appengine.ext import ndb

from Handlers import _render_template

from utils import (
    PLAQUE_SEARCH_INDEX_NAME,
    SubmitError,
    get_template_values,
)

DEF_NUM_NEARBY = 5

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
        # Unpublished plaques matching the search term:
        plaques = self._search_plaques(search_term)
        plaques = [p for p in plaques if not p.approved]

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
