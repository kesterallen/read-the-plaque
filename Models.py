
from collections import defaultdict
import datetime
import json
import logging
import re

from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.api import search
from google.appengine.datastore.datastore_query import Cursor
from google.appengine.ext.db import BadValueError

class Comment(ndb.Model):
    """
    A class to model a user comment about a particular plaque.

    Linked to a single Plaque object via the .plaque KeyProperty/FK.
    """
    text = ndb.TextProperty()
    created_on = ndb.DateTimeProperty(auto_now_add=True)
    created_by = ndb.UserProperty()
    approved = ndb.BooleanProperty(default=False)

class Plaque(ndb.Model):
    """
    A class to model a plaque with:
        * (Required) lat/lon location
        * (Required) Text description
        * Image of the plaque or area around the plaque:
            - the image's GCS filename
            - the image's serving URL (much faster to serve from this, so worth
              recording it at instance creation time)
        * Zero or more text tags
        * Approved flag (default False)
        * Created-on date
        * Created-by name

    User comments about the Plaque are located in the .comments attr, which is a
    KeyProperty/FK to Comment. Not sure if this is better than having a
    comment.plaque KeyProperty/FK in the other direction.
    """
    TINY_SIZE_PX = 100
    THUMBNAIL_SIZE_PX = 300
    DISPLAY_SIZE_PX = 1024
    BIG_SIZE_PX = 4096
    ALLOWED_ROTATIONS = [90, 180, 270]

    title = ndb.StringProperty(required=True) # StringProperty: 1500 char limit
    title_url = ndb.StringProperty(required=True)
    description = ndb.TextProperty(required=True) # no limit on TextProperty
    location = ndb.GeoPtProperty(required=True)
    pic = ndb.StringProperty()
    img_url = ndb.StringProperty()
    img_rot = ndb.IntegerProperty(default=0)
    tags = ndb.StringProperty(repeated=True)
    comments = ndb.KeyProperty(repeated=True, kind=Comment)
    approved = ndb.BooleanProperty(default=False)
    created_on = ndb.DateTimeProperty(auto_now_add=True)
    created_by = ndb.UserProperty()
    updated_on = ndb.DateTimeProperty(auto_now_add=True)
    updated_by = ndb.UserProperty()
    old_site_id = ndb.IntegerProperty()

    @classmethod
    def num_approved(cls):
        count = Plaque.query().filter(Plaque.approved == True).count()
        return count

    @classmethod
    def tokenize_title(cls, title):
        title = title.strip().lower()
        title = re.sub('[^\w]+', '-', title) # replace one or more non-word chars with a single dash
        title = re.sub('^-+|-+$', '', title) # remove leading or trailing dashes
        return title

    @classmethod
    def fetch_page(cls, num, startcur=None, urlsafe=True):
        """
        The "startcur" and "nextcur" variables refer to the start cursor and
        next cursors for this pagination.
        """
        if not urlsafe:
            startcur = startcur.urlsafe() if startcur else None

        # Make the memcache name keys:
        def _make_mn(mn_prefix):
            return "_".join([mn_prefix, str(num), str(startcur)])
        mn_prefixes = ['fetch_page', 'page_start_cursor_urlsafe', 'page_more']
        memcache_names = [_make_mn(mn_prefix) for mn_prefix in mn_prefixes]

        # Get the cached page, if it exists, otherwise make a page and cache it:
        memcache_result=  memcache.get_multi(memcache_names)
        memcache_worked = len(memcache_result.keys()) == len(memcache_names)
        if memcache_worked:
            # Return cached plaques, nextcur, more
            plaques = memcache_result[memcache_names[0]]
            nextcur = memcache_result[memcache_names[1]]
            more = memcache_result[memcache_names[2]]
        else:
            # Protect against bad values of startcur, like the old /page/3.
            try:
                startcur = Cursor(urlsafe=startcur) if startcur else None
            except BadValueError:
                startcur = None

            query = Plaque.query().filter(Plaque.approved == True).order(-Plaque.created_on)
            plaques, nextcur, more = query.fetch_page(num, start_cursor=startcur)

            memcache_status = memcache.set_multi({
                memcache_names[0]: plaques,
                memcache_names[1]: startcur,
                memcache_names[2]: more,
            })

        return plaques, nextcur, more

    @classmethod
    def num_pending(cls, num=20): # num is the max to return
        count = Plaque.query().filter(Plaque.approved != True).count(limit=num)
        return count

    @classmethod
    def pending_list(cls, num=25, desc=True):
        """A separate method from approved() so that it will
        never be memcached."""
        query = Plaque.query().filter(Plaque.approved != True).order(Plaque.approved)
        if desc:
            query = query.order(-Plaque.created_on)
        else:
            query = query.order(Plaque.created_on)

        plaques = query.fetch(limit=num)
        return plaques

    # Turning off because this doesn't scale.
    # TODO: add table UniqueTags
    @classmethod
    def all_tags_sized(cls):
        """
        Return a dict of the tags and their display-layer font sizes. Done
        here to speed rendering and to make the whole thing memcacheable.
        """
        tag_counts = memcache.get('all_tags_sized')
        if tag_counts is None:
            tag_counts = defaultdict(int)

            plaques = Plaque.query().filter(Plaque.approved == True).fetch()
            for plaque in plaques:
                for t in plaque.tags:
                    tag_counts[t] += 1

            tag_fontsize = {}
            for tag, count in tag_counts.items():
                if count < 5:
                    tag_fontsize[tag] = 10
                elif count < 10:
                    tag_fontsize[tag] = 13
                elif count < 20:
                    tag_fontsize[tag] = 16
                elif count < 40:
                    tag_fontsize[tag] = 19
                elif count < 120:
                    tag_fontsize[tag] = 22
                else:
                    tag_fontsize[tag] = 25
            memcache_status = memcache.set('all_tags_sized', tag_fontsize)
            if not memcache_status:
                logging.debug("memcaching for all_tags_sized failed")
        else:
            logging.debug("memcache.get worked for all_tags_sized")

        return tag_counts

    def img_url_base(self, size, crop=False):
        """Base method for  image URLs"""
        url = '{}=s{}'.format(self.img_url, size)
        if crop:
            url += '-c'
        if self.img_rot in Plaque.ALLOWED_ROTATIONS:
            url = "{}-r{}".format(url, self.img_rot)
        return url

    @property
    def img_url_tiny(self):
        """A URL for a tiny image for infowindow popups."""
        return self.img_url_base(self.TINY_SIZE_PX, crop=True)

    @property
    def img_url_thumbnail(self):
        """A URL for a THUMBNAIL_SIZE_PX wide image for thumbnails."""
        return self.img_url_base(self.THUMBNAIL_SIZE_PX, crop=True)

    @property
    def img_url_display(self):
        """A URL for a display-size image for display."""
        return self.img_url_base(self.DISPLAY_SIZE_PX)

    @property
    def img_url_big(self):
        """A URL for a big rotated image."""
        return self.img_url_base(self.BIG_SIZE_PX)

    @property
    def title_page_url(self):
        """This plaque's key-based page URL."""
        url = '/plaque/{}'.format(self.title_url)
        return url

    @property
    def fully_qualified_title_page_url(self):
        return "https://readtheplaque.com{0.title_page_url}".format(self)

    def page_url(self):
        """This plaque's key-based page URL."""
        url = '/plaque/{}'.format(self.key.urlsafe())
        return url

    def set_title_url(self, ancestor_key):
        """
        Set the title_url. For new plaques, if the title_url already exists on
        another plaque, add a suffix to make it unique. Keep plaques which are
        being edited the same.
        """
        title_url = Plaque.tokenize_title(self.title) if self.title else 'change-me'
        orig_title_url = title_url
        count = 1
        n_matches = Plaque.num_same_title_urls(title_url, ancestor_key)
        while n_matches > 0:
            count += n_matches
            title_url = "{}{}".format(orig_title_url, count)
            n_matches = Plaque.num_same_title_urls(title_url, ancestor_key)

        self.title_url = title_url

    @classmethod
    def num_same_title_urls(cls, title_url, ancestor_key):
        num_same_title= (
            Plaque.query(ancestor=ancestor_key)
            .filter(Plaque.title_url == title_url)
            .count()
        )
        return num_same_title

    @classmethod
    def num_same_title_urls_published(cls, title_url, ancestor_key):
        num_same_title = (
            Plaque.query(ancestor=ancestor_key)
            .filter(Plaque.title_url == title_url)
            .filter(Plaque.approved == True)
            .count()
        )
        return num_same_title

    @classmethod
    def created_after(cls, updated_on_str):
        """
        List of Plaque objects with created_on > updated_on_str.
        """
        date_fmt =  "%Y-%m-%d %H:%M:%S.%f"
        updated_on = datetime.datetime.strptime(updated_on_str, date_fmt)

        plaques = (
            Plaque.query()
            .filter(Plaque.approved == True)
            .filter(Plaque.created_on > updated_on)
            .order(-Plaque.created_on)
            .fetch()
        )
        return plaques

    @classmethod
    def created_after_geojson(cls, updated_on_str):
        """
        Geojson FeatureCollection of Plaque objects with created_on > updated_on_str.
        """
        plaques = Plaque.created_after(updated_on_str)
        features = [p.to_geojson(jsonify=False)for p in plaques if p] # Remove empties
        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "updated_on": str(datetime.datetime.now()),
        }
        return geojson

    def to_search_document(self):
        location = search.GeoPoint(self.location.lat, self.location.lon)
        doc = search.Document(
            doc_id = self.key.urlsafe(),
            fields=[
                search.TextField(name='tags', value=" ".join(self.tags)),
                search.TextField(name='title', value=self.title),
                search.HtmlField(name='description', value=self.description),
                search.GeoField(name='location', value=location),
            ],
        )
        return doc

    @property
    def geojson(self):
        return self.to_geojson()

    def to_geojson(self, summary=False, jsonify=True):

        data = {
            "geometry": {
                "type": "Point",
                "coordinates": [self.location.lon, self.location.lat]
            },
            "type": "Feature",
            "properties": {
                "img_url_tiny": self.img_url_tiny,
                "title_page_url": self.title_page_url,
                "title": self.title
            }
        }
        if not summary:
            data["properties"]["key"] = self.key.urlsafe()
            data["properties"]["description"] = self.description
            data["properties"]["img_url"] = self.img_url
            data["properties"]["tags"] = self.tags

        return json.dumps(data) if jsonify else data

    def to_dict(self, summary=False):
        if summary:
            plaque_dict = {
                'title': self.title,
                'title_page_url': self.title_page_url,
                'lat': str(self.location.lat),
                'lng': str(self.location.lon), # note spelling difference "lng" vs "lon"
                'img_url_tiny': self.img_url_tiny,
            }
        else:
            plaque_dict = {
                'plaque_key': self.key.urlsafe(),
                'title': self.title,
                'title_url': self.title_url,
                'description': self.description,
                'location': str(self.location),
                'pic': self.pic,
                'img_url': self.img_url,
                'img_rot': self.img_rot,
                'tags': self.tags,
                'comments': self.comments,
                'approved': self.approved,
                'old_site_id': self.old_site_id,
            }
        return plaque_dict

    @property
    def tweet_text (self):
        return "'{0.title}' Always #readtheplaque {0.fully_qualified_title_page_url}".format(self)

    @property
    def tweet_to_plaque_submitter(self):
        #submitter_regex = r"Submitted by.*(twitter.com/\w+|@\w+)\b"
        #submitter_match_index = 1
        submitter_regex = r"Submitted by.*(twitter.com/|@)(\w+)\b"
        submitter_match_index = 2
        match = re.search(submitter_regex, self.description, re.DOTALL)
        if match:
            submitter = match.group(submitter_match_index).strip()
            submitter_tweet = (
                "@{0} Your plaque has been selected by the random plaque "
                "generator! Thanks again! #readtheplaque {1}".format(
                    submitter, self.fully_qualified_title_page_url)
            )
        else:
            submitter_tweet = None
        return submitter_tweet

    @property
    def json_for_tweet(self):
        plaque_dict = self.to_dict(summary=True)
        plaque_dict["tweet"] = self.tweet_text
        plaque_dict["submitter_tweet"] = self.tweet_to_plaque_submitter
        return json.dumps(plaque_dict)

    @property
    def gmaps_url(self):
        return (
            "http://maps.google.com/maps?&z=21&t=m&q="
            "loc:{0.lat:.8f}+{0.lon:.8f}".format(self.location)
        )

class FeaturedPlaque(ndb.Model):
    created_on = ndb.DateTimeProperty(auto_now_add=True)
    plaque = ndb.KeyProperty(repeated=False, kind=Plaque)

