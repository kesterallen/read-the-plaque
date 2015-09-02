
from collections import defaultdict

from google.appengine.api import memcache
from google.appengine.ext import ndb

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
    THUMBNAIL_SIZE_PX = 300
    DISPLAY_SIZE_PX = 1024

    title = ndb.StringProperty(required=True) # StringProperty: 1500 char limit
    description = ndb.TextProperty(required=True) # no limit on TextProperty
    location = ndb.GeoPtProperty(required=True)
    pic = ndb.StringProperty()
    pic_url = ndb.StringProperty()
    tags = ndb.StringProperty(repeated=True)
    comments = ndb.KeyProperty(repeated=True, kind=Comment)
    approved = ndb.BooleanProperty(default=False)
    created_on = ndb.DateTimeProperty(auto_now_add=True)
    created_by = ndb.UserProperty()

    @classmethod
    def all_approved(cls):
        all_plaques = memcache.get('all_approved')
        if all_plaques is None:
            all_plaques = Plaque.query().filter(Plaque.approved == True
                                       ).order(-Plaque.created_on
                                       ).fetch()
        else:
            logging.debug("memcache.get worked for all_approved")
        return all_plaques

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
    def thumbnail_url(self):
        """A URL for a square, THUMBNAIL_SIZE_PX wide image for thumbnails."""
        return '%s=s%s-c' % (self.pic_url, self.THUMBNAIL_SIZE_PX)

    @property
    def display_url(self):
        """A URL for a display-size image for display."""
        return '%s=s%s' % (self.pic_url, self.THUMBNAIL_SIZE_PX)
