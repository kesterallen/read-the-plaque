"""ORM classes for Read the Plaque"""

import datetime
import json
import re

from google.cloud import ndb
from google.appengine.api import search

class Comment(ndb.Model):
    """
    DEPRECATED, TO BE REMOVED

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
        """How many plaques are approved"""
        count = Plaque.query().filter(Plaque.approved == True).count()
        return count

    @classmethod
    def tokenize_title(cls, title):
        """ Make a URL title """
        title = title.strip().lower()
        # replace one or more non-word chars with a single dash, and remove
        # leaving/trailing dashes
        title = re.sub(r'[^\w]+', '-', title)
        title = re.sub(r'^-+|-+$', '', title)
        return title

    @classmethod
    def fetch_page(cls, num, start_cursor=None, urlsafe=True):
        """
        The "start_cursor" and "next_cursor" variables refer to the pagination start
        and next cursors.
        """
        if not urlsafe:
            start_cursor = start_cursor.urlsafe() if start_cursor else None

        query = Plaque.query().filter(Plaque.approved == True).order(-Plaque.created_on)
        plaques, next_cursor, more = query.fetch_page(num, start_cursor=start_cursor)

        return plaques, next_cursor, more

    @classmethod
    def num_pending(cls, num=20): # num is the max to return
        """ How many pending plaques are there? """
        count = Plaque.query().filter(Plaque.approved != True).count(limit=num)
        return count

    @classmethod
    def pending_list(cls, num=25, desc=True):
        """The newest {num} pending plaques."""
        query = Plaque.query().filter(Plaque.approved != True).order(Plaque.approved)
        if desc:
            query = query.order(-Plaque.created_on)
        else:
            query = query.order(Plaque.created_on)

        plaques = query.fetch(limit=num)
        return plaques


    def img_url_base(self, size, crop=False):
        """Base method for  image URLs"""

        # TODO: Trying this with media_link for img_url in blob creation (in main.py)
        # TODO: evaluate if this is the right way to do things and delete the
        #       other code for img_url_* if so

        url = self.img_url
        #url = '{}=s{}'.format(self.img_url, size)
        #if crop:
        #    url += '-c'
        #if self.img_rot in Plaque.ALLOWED_ROTATIONS:
        #    url = "{}-r{}".format(url, self.img_rot)
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
        return f"/plaque/{self.title_url}"

    @property
    def fully_qualified_title_page_url(self):
        """This plaque's page's fully-qualified URL."""
        return f"https://readtheplaque.com{self.title_page_url}"

    def page_url(self):
        """This plaque's key-based page URL."""
        return f"/plaque/{self.key.urlsafe()}"

    def set_title_and_title_url(self, title, ancestor_key):
        """Update title if necessary and set the URL"""
        title = title[:1499] # limit to 1500 char
        if title != self.title:
            self.title = title
            self.set_title_url(ancestor_key)

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
            title_url = f"{orig_title_url}{count}"
            n_matches = Plaque.num_same_title_urls(title_url, ancestor_key)

        self.title_url = title_url

    @classmethod
    def num_same_title_urls(cls, title_url, ancestor_key):
        """How many plaques have this title_url?"""
        num_same_title= (
            Plaque.query(ancestor=ancestor_key)
            .filter(Plaque.title_url == title_url)
            .count()
        )
        return num_same_title

    @classmethod
    def num_same_title_urls_published(cls, title_url, ancestor_key):
        """How many pubished plaques have this title_url?"""
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
        """Generate a search document for this plaque"""
        location = search.GeoPoint(self.location.latitude, self.location.longitude)
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
        """Generate the geojson for this plaque (property)"""
        return self.to_geojson()

    def to_geojson(self, summary=False, jsonify=True):
        """Generate the geojson for this plaque"""

        data = {
            "geometry": {
                "type": "Point",
                "coordinates": [self.location.longitude, self.location.latitude]
            },
            "type": "Feature",
            "properties": {
                "img_url_tiny": self.img_url_tiny,
                "title_page_url": self.title_page_url,
                "title": self.title
            }
        }
        if not summary:
            data["properties"]["key"] = self.key.urlsafe().decode()
            data["properties"]["description"] = self.description
            data["properties"]["img_url"] = self.img_url
            data["properties"]["tags"] = self.tags

        return json.dumps(data) if jsonify else data

    def to_dict(self, summary=False):
        """
        Generate the non-geojson dict for this plaque; used for updating the
        static big map page
        """
        if summary:
            plaque_dict = {
                'title': self.title,
                'title_page_url': self.title_page_url,
                'lat': str(self.location.latitude),
                'lng': str(self.location.longitude),
                'img_url_tiny': self.img_url_tiny,
            }
        else:
            plaque_dict = {
                'plaque_key': self.key.urlsafe().decode(),
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
    def tweet_text(self):
        """ The text for a tweet about this plaque """
        return f"'{self.title}' Always #readtheplaque {self.fully_qualified_title_page_url}"

    @property
    def tweet_to_plaque_submitter(self):
        """ Congratulations text for the submitter of this plaque """
        submitter_regex = r"Submitted by.*(twitter.com/|@)(\w+)\b"
        submitter_match_index = 2
        match = re.search(submitter_regex, self.description, re.DOTALL)
        if match:
            submitter = match.group(submitter_match_index).strip()
            submitter_tweet = (
                f"@{submitter} Your plaque has been selected by the random plaque "
                "generator! Thanks again! #readtheplaque"
                f"{self.fully_qualified_title_page_url}"
            )
        else:
            submitter_tweet = None
        return submitter_tweet

    @property
    def json_for_tweet(self):
        """
        Separate non-geoJSON JSON representation. Use for updating the
        static map file
        """
        plaque_dict = self.to_dict(summary=True)
        plaque_dict["tweet"] = self.tweet_text
        plaque_dict["submitter_tweet"] = self.tweet_to_plaque_submitter
        return json.dumps(plaque_dict)

    @property
    def gmaps_url(self):
        """ URL for google maps at this plaque's location """
        return (
            "http://maps.google.com/maps?&z=21&t=m&q=loc:"
            f"{self.location.latitude:.8f}+{self.location.longitude:.8f}"
        )

class FeaturedPlaque(ndb.Model):
    """ Class to keep track of which plaque is the fetured one """
    created_on = ndb.DateTimeProperty(auto_now_add=True)
    plaque = ndb.KeyProperty(repeated=False, kind=Plaque)
