
from collections import defaultdict
import logging
import re

from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.api import search

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
        plaques_list = cls.approved_list()
        if plaques_list:
            return len(plaques_list)
        else:
            return 0

    @classmethod
    def approved_list(cls):
        plaques = memcache.get('approved')
        if plaques is None:
            plaques = Plaque.query().filter(Plaque.approved == True
                                   ).order(-Plaque.created_on
                                   ).fetch()
            memcache_status = memcache.set('approved', plaques)
            if not memcache_status:
                logging.debug("memcaching for Plaque.approved() failed")
        else:
            logging.debug("memcache.get worked for Plaque.approved()")
        return plaques

    @classmethod
    def num_pending(cls):
        plaques_list = cls.pending_list()
        if plaques_list:
            return len(plaques_list)
        else:
            return 0

    @classmethod
    def pending_list(cls):
        """A separate method from approved() so that it will
        never be memcached."""
        plaques = Plaque.query().filter(Plaque.approved != True
                               ).order(-Plaque.approved
                               ).order(-Plaque.created_on
                               ).fetch()
        return plaques

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
    def title_page_url(self):
        """This plaque's key-based page URL."""
        url = '/plaque/%s' % self.title_url
        return url

    def page_url(self):
        """This plaque's key-based page URL."""
        url = '/plaque/%s' % self.key.urlsafe()
        return url

    def set_title_url(self, ancestor_key, is_edit=False):
        """
        Set the title_url. For new plaques, if the title_url already exists on
        another plaque, add a suffix to make it unique. Keep plaques which are 
        being edited by an admin the same.
        """
        if is_edit:
            return

        if self.title:
            title_url = re.sub('[^\w]+', '-', self.title.strip()).lower()
        else:
            title_url = ''

        orig_title_url = title_url

        count = 1
        n_matches= Plaque.num_same_title_urls(title_url, ancestor_key)
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

    def to_dict(self):
        return {
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
            #'created_on': str(self.created_on),
            #'created_by': self.created_by,
            #'updated_on': str(self.updated_on),
            #'updated_by': self.updated_by,
            'old_site_id': self.old_site_id,
        }

