
import datetime
import logging
import os
import json
import re
import urllib

import webapp2
from google.appengine.api import memcache, users, images, search
from google.appengine.ext import blobstore, ndb
from google.appengine.ext.db import BadValueError
import lib.cloudstorage as gcs

from Models import Plaque

from Handlers import (
    DEF_PLAQUESET_NAME,
    JINJA_ENVIRONMENT,
    _render_template,
    set_featured,
)

from utils import (
    DELETE_PRIVS,
    PLAQUE_SEARCH_INDEX_NAME,
    SubmitError,
    email_admin,
    get_template_values,
    latlng_get_angles,
    latlng_angles_to_dec,
    loginout,
)

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

# Set a parent key on the Plaque objects to ensure that they are all in the
# same entity group. Queries across the single entity group will be consistent.
# However, the write rate should be limited to ~1/second.
#
def get_plaqueset_key(plaqueset_name=DEF_PLAQUESET_NAME):
    """
    Constructs a Datastore key for a Plaque entity. Use plaqueset_name as
    the key.
    """
    return ndb.Key('Plaque', plaqueset_name)

class FormArgs(object):
    """ Data class for AddPlaque """
    def __init__(
        self, location, created_by, title, description, img_name, img_fh, tags
    ):
        self.location = location
        self.created_by = created_by
        self.title = title
        self.description = description
        self.img_name = img_name
        self.img_fh = img_fh
        self.tags = tags

class AdminLogin(webapp2.RequestHandler):
    def get(self):
        url = users.create_login_url('/')
        self.response.write("<a href='{}'>Login</a>".format(url))

class Counts(webapp2.RequestHandler):
    """ Display the plaque counts """
    def get(self):
        query = Plaque.query()
        num_plaques = query.count()
        num_pending = query.filter(Plaque.approved == False).count()

        verbose = self.request.get('verbose')
        if verbose:
            tmpl = "<ul> <li>{} published</li> <li>{} pending</li> </ul>"
        else:
            tmpl = "{} published, {} pending\n"
        msg = tmpl.format(num_plaques - num_pending, num_pending)
        self.response.write(msg)

class FlushMemcache(webapp2.RequestHandler):
    def get(self):
        memcache.flush_all()
        self.redirect('/')

    def post(self):
        memcache.flush_all()
        self.redirect('/')

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

                    message = (
                        'Thanks, admin! <a id="thanks_admin" style="float: right"'
                        'href="{}">{}</a>'.format(url, title)
                    )
                else:
                    message = (
                        "Hooray! And thank you. We'll review your plaque and "
                        "you'll see it on the map soon."
                    )
            elif state == ADD_STATE_ERROR:
                message = (
                    "Sorry, your plaque submission had this error: "
                    '<font color="red">"{}"</font>'.format(message)
                )
        return message

    def get(self, message=None):
        maptext = (
            "Click the plaque's location on the map, or search "
            "for it, or enter its lat/lng location"
        )
        template_values = get_template_values(maptext=maptext, mapzoom=10, page_title="Add Plaque")
        message = self._get_message(message)
        if message is not None:
            template_values['message'] = message

        text_ = _render_template("add.html", template_values)
        self.response.write(text_)


    @ndb.transactional
    def post(self, is_edit=False):
        """
        We set the same parent key on the 'Plaque' to ensure each Plauqe is in
        the same entity group. Queries across the single entity group will be
        consistent. However, the write rate to a single entity group should be
        limited to ~1/second.
        """

        try:
            plaqueset_name = self.request.get('plaqueset_name', DEF_PLAQUESET_NAME)
            plaqueset_key = get_plaqueset_key(plaqueset_name)
            plaque = self._create_or_update_plaque(is_edit, plaqueset_key)

            # Make the plaque searchable:
            #
            try:
                plaque_search_index = search.Index(PLAQUE_SEARCH_INDEX_NAME)
                plaque_search_index.put(plaque.to_search_document())
            except search.Error as err:
                raise err

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

        args = self._get_form_args()

        plaque.location = args.location
        if args.title != plaque.title:
            plaque.title = args.title
            plaque.set_title_url(plaqueset_key)

        plaque.description = args.description
        plaque.tags = args.tags
        if not is_edit:
            plaque.approved = False
        plaque.updated_on = datetime.datetime.now()

        # Upload the image for a new plaque, or update the an editted plaque's image
        is_upload_pic = (is_edit and args.img_name is not None) or (not is_edit)
        if is_upload_pic:
            self._upload_image(args.img_name, args.img_fh, plaque)

        # Write to the updated_* fields if this is an edit:
        #
        if is_edit:
            plaque.updated_by = users.get_current_user()
            plaque.updated_on = datetime.datetime.now()
            img_rot = self.request.get('img_rot')
            if img_rot is not None and img_rot != 0:
                plaque.img_rot = int(img_rot)
        else:
            plaque.created_by = args.created_by
            plaque.updated_by = None

        old_site_id = self.request.get('old_site_id', None)
        if old_site_id is not None:
            try:
                plaque.old_site_id = int(old_site_id)
            except ValueError as err:
                logging.info('Eating bad ValueError for old_site_id in AddPlaque')
        plaque.put()
        return plaque

    def _get_latlng_exif(self, img_fh):
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS

        # Get GPS data out of image:
        #
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
            lat_ref = gps_data['GPSLatitudeRef'] # N/S
            lat_angles = latlng_get_angles(gps_data['GPSLatitude'])

            lng_ref = gps_data['GPSLongitudeRef'] # E/W
            lng_angles = latlng_get_angles(gps_data['GPSLongitude'])

            lat = latlng_angles_to_dec(lat_ref, lat_angles)
            lng = latlng_angles_to_dec(lng_ref, lng_angles)
        except KeyError:
            pass # TODO: is this right?

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
            except Exception as err:
                logging.error(err)
                err = SubmitError(
                    "The plaque location wasn't specified. Please click the "
                    "back button, select a location, and click 'Add your "
                    "Plaque' again. Error ({})".format(err))
                raise err

        return location

    def _get_img(self):
        """
        Prefer the file to the URL, if both are given.
        """

        img_file = self.request.POST.get('plaque_image_file')
        img_url = self.request.POST.get('plaque_image_url')

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

    def _get_tags(self):
        # Get and tokenize tags
        tags_str = self.request.get('tags')
        tags_split = tags_str.split(',')
        tags = [re.sub(r'\s+', ' ', t.strip().lower()) for t in tags_split]
        tags = [t for t in tags if t] # Remove empties
        return tags

    def _get_form_args(self):
        """Get the arguments from the form and return them."""
        created_by = users.get_current_user()
        title = self.request.get('title')[:1499] # limit to 1500 char
        description = self.request.get('description')
        img_name, img_fh = self._get_img()
        location = self._get_location(img_fh)
        tags = self._get_tags()

        return FormArgs(
            created_by=created_by,
            title=title,
            description=description,
            img_name=img_name,
            img_fh=img_fh,
            location=location,
            tags=tags,
        )

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

        # Kill old image and URL, if they exist. Tolerate failure in case
        # this is a redo:
        if plaque.pic is not None:
            try:
                gcs.delete(plaque.pic)
            except:
                pass
        if plaque.img_url is not None:
            try:
                images.delete_serving_url(plaque.img_url)
            except:
                pass

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
        template_values = get_template_values(
            maptext="",
            mapzoom=9,
            page_title="Edit Plaque",
            plaque=plaque,
            loginout=loginout(),
        )
        if message is not None:
            template_values['message'] = message

        _text = _render_template("edit.html", template_values)
        self.response.write(_text)

    def post(self):
        if users.is_current_user_admin():
            super(EditPlaque, self).post(is_edit=True)

class SetFeatured(webapp2.RequestHandler):
    def get(self, plaque_key):
        if users.is_current_user_admin():
            plaque = ndb.Key(urlsafe=plaque_key).get()
            set_featured(plaque)
            memcache.flush_all()
            self.redirect('/')

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
    """Approve a plaque"""
    @classmethod
    def set_approval(cls, plaque_key, approval=True):
        plaque = ndb.Key(urlsafe=plaque_key).get()

        plaque.approved = approval
        if plaque.approved:
            plaque.created_on = datetime.datetime.now()
            plaque.updated_on = datetime.datetime.now()
        plaque.put()

    @ndb.transactional
    def post(self):
        if not users.is_current_user_admin():
            return "admin only, please log in"

        plaque_key = self.request.get('plaque_key')
        ApprovePending.set_approval(plaque_key)
        self.redirect('/nextpending')

class DisapprovePlaque(ApprovePending):
    """Disapprove a plaque"""
    @ndb.transactional
    def post(self):
        if not users.is_current_user_admin():
            return "admin only, please log in"

        plaque_key = self.request.get('plaque_key')
        self.set_approval(plaque_key, approval=False)
        self.redirect('/')

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

        if name not in DELETE_PRIVS:
            email_admin('Warning!', '{} tried to delete {}'.format(
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
        text_ = '{} Deleted plaque {}'.format(name, plaque.title_url)
        email_admin(text_, text_)
        self.redirect('/nextpending')

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
            logging.debug('SearchIndex: %s good docs, %s failed' % (igood, ibad))
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

