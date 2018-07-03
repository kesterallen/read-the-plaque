
from collections import defaultdict
import json
import logging
import re

FETCH_LIMIT_PLAQUES = 500

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
        tokenized_title = re.sub('[^\w]+', '-', title.strip()).lower()
        return tokenized_title

    @classmethod
    def fetch_page(cls, num, start_cursor=None, urlsafe=True):
        if urlsafe:
            start_cursor_urlsafe = start_cursor
        else:
            if start_cursor:
                start_cursor_urlsafe = start_cursor.urlsafe()
            else:
                start_cursor_urlsafe = None

        memcache_names = [
            'fetch_page_%s_%s' % (num, start_cursor_urlsafe),
            'page_start_cursor_urlsafe_%s_%s' % (num, start_cursor_urlsafe),
            'page_more_%s_%s' % (num, start_cursor_urlsafe),
        ]

        memcache_out =  memcache.get_multi(memcache_names)
        memcache_worked = len(memcache_out.keys()) == len(memcache_names)
        if memcache_worked:
            logging.debug("memcache.get_multi worked for Plaque.fetch_page()")
            plaques = memcache_out[memcache_names[0]]
            next_cursor = memcache_out[memcache_names[1]]
            more = memcache_out[memcache_names[2]]
        else:
            query = Plaque.query(
                ).filter(Plaque.approved == True).order(-Plaque.created_on)

            # Protect agains bad values of start_cursor_urlsafe, like the old
            # type of request to /page/3.
            if start_cursor_urlsafe:
                try:
                    start_cursor = Cursor(urlsafe=start_cursor_urlsafe)
                except BadValueError:
                    start_cursor = None
            else:
                start_cursor = None

            if start_cursor:
                plaques, next_cursor, more = query.fetch_page(num, start_cursor=start_cursor)
                logging.info('in fetch_page if block, len(plaques)=%s, start_cursor=%s, next_cursor=%s, more=%s' % (len(plaques), start_cursor, next_cursor, more))
            else:
                plaques, next_cursor, more = query.fetch_page(num)
                logging.info('in fetch_page else block, len(plaques)=%s, next_cursor=%s, more=%s' % (len(plaques), next_cursor, more))

            memcache_status = memcache.set_multi({
                memcache_names[0]: plaques,
                memcache_names[1]: start_cursor,
                memcache_names[2]: more,
            })
            if memcache_status:
                logging.debug("""memcache.set in Plaque.plaque_pages() failed: 
                    %s were not set""" % memcache_status)

        logging.info("In Plaque.page_url: %s plaques %s %s" % (len(plaques), next_cursor, more))
        return plaques, next_cursor, more

    @classmethod
    def num_pending(cls, num=20): # num is the max to return
        count = Plaque.query().filter(Plaque.approved != True).count(limit=num)
        return count

    @classmethod
    def pending_list(cls, num=25, desc=True):
        """A separate method from approved() so that it will
        never be memcached."""
        query = Plaque.query().filter(Plaque.approved != True
                             ).order(Plaque.approved)
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

    @property
    def img_url_tiny(self):
        """A URL for a square, tiny image for infowindow popups."""
        url = '%s=s%s-c' % (self.img_url, self.TINY_SIZE_PX)
        if self.img_rot in Plaque.ALLOWED_ROTATIONS:
            url = "%s-r%s" % (url, self.img_rot)
        return url

    @property
    def img_url_thumbnail(self):
        """A URL for a square, THUMBNAIL_SIZE_PX wide image for thumbnails."""
        url = '%s=s%s-c' % (self.img_url, self.THUMBNAIL_SIZE_PX)
        if self.img_rot in Plaque.ALLOWED_ROTATIONS:
            url = "%s-r%s" % (url, self.img_rot)
        return url

    @property
    def img_url_display(self):
        """A URL for a display-size image for display."""
        url = '%s=s%s' % (self.img_url, self.DISPLAY_SIZE_PX)
        if self.img_rot in Plaque.ALLOWED_ROTATIONS:
            url = "%s-r%s" % (url, self.img_rot)
        return url

    @property
    def img_url_big(self):
        """A URL for a big rotated image."""
        url = '%s=s%s' % (self.img_url, self.BIG_SIZE_PX)
        if self.img_rot in Plaque.ALLOWED_ROTATIONS:
            url = "%s-r%s" % (url, self.img_rot)
        return url

    @property
    def title_page_url(self):
        """This plaque's key-based page URL."""
        url = '/plaque/%s' % self.title_url
        return url

    def page_url(self):
        """This plaque's key-based page URL."""
        url = '/plaque/%s' % self.key.urlsafe()
        return url

    def set_title_url(self, ancestor_key):
        """
        Set the title_url. For new plaques, if the title_url already exists on
        another plaque, add a suffix to make it unique. Keep plaques which are 
        being edited the same.
        """
        if self.title:
            title_url = Plaque.tokenize_title(self.title)
        else:
            title_url = 'change-me'

        if title_url[0] == '-':
            title_url = title_url[1:]
        if title_url[-1] == '-':
            title_url = title_url[:-1]


        orig_title_url = title_url

        count = 1
        n_matches = Plaque.num_same_title_urls(title_url, ancestor_key)
        while n_matches > 0:
            count += 1
            title_url = "%s%s" % (orig_title_url, count)
            n_matches = Plaque.num_same_title_urls(title_url, ancestor_key)

        self.title_url = title_url

    @classmethod
    def num_same_title_urls(cls, title_url, ancestor_key):
        query = Plaque.query(ancestor=ancestor_key
                     ).filter(Plaque.title_url == title_url)
        num_plaques = query.count()
        return num_plaques

    @classmethod
    def num_same_title_urls_published(cls, title_url, ancestor_key):
        num_plaques = Plaque.query(ancestor=ancestor_key
            ).filter(Plaque.title_url == title_url
            ).filter(Plaque.approved == True).count()
        return num_plaques

    def to_search_document(self):
        doc = search.Document(
            doc_id = self.key.urlsafe(),
            fields=[
                search.TextField(name='tags', value=" ".join(self.tags)),
                search.TextField(name='title', value=self.title),
                search.HtmlField(name='description', value=self.description),
                search.GeoField(name='location',
                                value=search.GeoPoint(self.location.lat,
                                                      self.location.lon)),
            ],
        )
        return doc

    def to_geojson(self, summary=True):
        if not summary:
            raise ArgumentError("summary = False isn't implemented yet")

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
        return json.dumps(data)

    def to_dict(self, summary=False):
        if summary:
            plaque_dict = {
                'title': self.title,
                'title_page_url': self.title_page_url,
                'lat': str(self.location.lat),
                'lng': str(self.location.lon), # N.B.: 'lng' --> 'lon'
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
    def json_for_tweet(self):
        plaque_dict = self.to_dict(summary=True)
        tmpl = "'%s' Always #readtheplaque https://readtheplaque.com%s"
        plaque_dict['tweet'] = tmpl % (self.title, self.title_page_url),
        return json.dumps(plaque_dict)

class FeaturedPlaque(ndb.Model):
    created_on = ndb.DateTimeProperty(auto_now_add=True)
    plaque = ndb.KeyProperty(repeated=False, kind=Plaque)

