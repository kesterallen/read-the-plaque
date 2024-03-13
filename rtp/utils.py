"""
Utilities for Read the Plaque
"""

import datetime as dt
import json
import math
import os
import random
import re
import urllib

from flask import render_template, request

from google.cloud import ndb, storage
from google.appengine.api import users, search, memcache

from .models import Plaque, FeaturedPlaque

# GCS_BUCKET configuration: This appears to work for the bucket named
# 'read-the-plaque.appspot.com', Don't change this to, say, readtheplaque.com.
#
# GCS_BUCKET = "/read-the-plaque.appspot.com"
GCS_BUCKET = "read-the-plaque.appspot.com"

PLAQUESET_NAME = "public"
SEARCH_INDEX_NAME = "plaque_index"

FIRST_YEAR = 2015
FIRST_MONTH = 9
FIRST_DAY = 9


class SubmitError(Exception):
    """Catchall error class for submitting plaques"""


def _get_key(key_filename="key_googlemaps.txt") -> str:
    """Get the value of the key in the given file"""
    with open(key_filename) as key_fh:
        key = key_fh.read().rstrip()
    return key


# Set a parent key on the Plaque objects to ensure that they are all in the
# same entity group. Queries across the single entity group will be consistent.
# However, the write rate should be limited to ~1/second.
#
def _plaqueset_key(plaqueset_name=PLAQUESET_NAME) -> ndb.Key:
    """
    Constructs a Datastore key for a Plaque entity. Use plaqueset_name as
    the key.
    """
    return ndb.Key("Plaque", plaqueset_name)


def _loginout() -> dict:
    """Helper function to get the login/logout details in one place"""
    is_admin = users.is_current_user_admin()
    if user := users.get_current_user():
        text = f"Log out {user.nickname()}"
        url = users.create_logout_url("/")
    else:
        text = "Admin login"
        url = users.create_login_url("/")
    return {"is_admin": is_admin, "text": text, "url": url}


def _get_bounding_box(plaques: list[Plaque]) -> list[float]:
    """
    Calculate the bounding box corners for the coordinates of a list of plaques
    """
    if plaques is not None:
        plaques = [p for p in plaques if p is not None]
    if plaques:
        lats = [p.location.latitude for p in plaques]
        lngs = [p.location.longitude for p in plaques]
        bounding_box = [[min(lngs), min(lats)], [max(lngs), max(lats)]]
    else:
        bounding_box = None
    return bounding_box


def _render_template(template_file: str, plaques: list = None, **kwargs) -> str:
    """
    A wrapper for flask.render_template that injects some defaults, filter out
    None plaques
    """
    if plaques is not None:
        plaques = [p for p in plaques if p is not None]
    rendered = render_template(
        template_file,
        plaques=plaques,
        loginout=_loginout(),
        footer_items=_get_footer_items(),
        **kwargs,
    )
    _memcache_set(rendered)
    return rendered


def _render_template_map(
    template_file: str = "all.html",
    plaques: list = None,
    page_title: str = "View Pending Plaques",
    mapzoom: int = 10,  # float?
    **kwargs,
) -> str:
    return _render_template(
        template_file,
        plaques,
        bounding_box=_get_bounding_box(plaques),
        mapzoom=mapzoom,
        google_maps_api_key=_get_key(),
        page_title=page_title,
        **kwargs,
    )


def _get_random_time(year=FIRST_YEAR, month=FIRST_MONTH, day=FIRST_DAY) -> dt.datetime:
    """
    Utilize the fact that the first plaque submission was 2015-09-09 to
    generate a random time between then and now.
    """
    first = dt.datetime(year, month, day)
    now = dt.datetime.now()
    rand_seconds = random.randint(0, int((now - first).total_seconds()))
    return first + dt.timedelta(seconds=rand_seconds)


def _get_footer_items(num: int = 5) -> dict:
    """
    A list of tag items for the page footer.
    """
    rand_plaques = [_get_random_plaque() for _ in range(num)]
    tags = _get_random_tags(num)
    footer_items = {
        "tags": tags,
        "new_plaques": rand_plaques,
    }
    return footer_items


def _get_random_tags(num: int) -> list:
    """
    Get a list of random tags. Limit to total number of runs to 100 to prevent
    infinite loop if there are no plaques or tags.
    """
    tags = set()
    bailout = 0
    try:
        while len(tags) < num and bailout < 100:
            bailout += 1
            plaque = _get_random_plaque()
            if plaque is None:
                continue
            if plaque.tags:
                tag = random.choice(plaque.tags)
                tags.add(tag)
    except ValueError:
        print("no plaques in get_random_tags")

    outtags = list(tags)
    outtags = outtags[:num]
    return outtags


def _get_random_plaque() -> Plaque:
    """Get a random plaque from the database"""
    plaque_key = _get_random_plaque_key()
    if plaque_key is None:
        return None
    plaque = ndb.Key(urlsafe=plaque_key).get()
    return plaque


# TODO: return type
def _get_random_plaque_key(method="time"):
    """
    Get a random plaque key.  Limit to total number of runs to 100 to prevent
    infinite loop if there are no plaques.

    There are at least three strategies to get a random plaque:

        1. Perform a Plaque.query().count(), get a random int in the [0,count)
           range, and get the plaque at that offset using
           Plaque.query.get(offset=foo).

           This technique favors large submissions of plaques that were
           imported automatically (e.g. North Carolina, Geographs,
           Toronto/Ontario), and using large offsets is expensive in the NDB
           system.

        2. "time": Pick a random time since the start of the site, and find a
           plaque that has a created_by value close to that time.

           This technique favors plaques which were submitted by users who have
           submitted many plaques over a long period of time, and will be
           unlikely to pick a plaque which would be picked by technique #1.

        3. "geo": Pick a random geographical spot on the globe, and get the
           plaque closest to that.

           This will favor plaques that are further away from other plaques.

    """
    plaque_key = None
    bailout = 0
    plaque_search_index = search.Index(SEARCH_INDEX_NAME)
    while plaque_key is None and bailout < 100:
        bailout += 1
        if method == "geo":
            # Math from http://mathworld.wolfram.com/SpherePointPicking.html
            rand_u = random.random()
            rand_v = random.random()
            lng = ((2.0 * rand_u) - 1.0) * 180.0  # Range: [-180.0, 180.0)
            lat = math.acos(2.0 * rand_v - 1) * 180.0 / math.pi - 90.0
            search_radius_meters = 100000  # 100 km

            query_string = (
                f"distance(location, geopoint({lat}, {lng})) < {search_radius_meters}"
            )
            query = search.Query(query_string)
            results = plaque_search_index.search(query)
            if results.number_found > 0:
                doc_id = results[0].doc_id
                plaque_key = ndb.Key(doc_id).get()
        else:  # method == "time"
            random_time = _get_random_time()
            if random_time is not None:
                plaque_key = (
                    Plaque.query()
                    .filter(Plaque.approved == True)
                    .filter(Plaque.created_on > random_time)
                    .get(keys_only=True)
                )
    if plaque_key is None:
        return None

    return plaque_key.urlsafe()


def _memcache_name() -> str:
    """Define the memcache key: method_RequestPath_AdminStatus"""
    return f"{request.method}_{request.path}_{users.is_current_user_admin()}"


def _memcache_get() -> str:
    """Return the memcache for a given request"""
    return memcache.get(_memcache_name())


# TODO: return type
def _memcache_set(text):
    """Set the memcache for a given request"""
    return memcache.set(_memcache_name(), text)


def _get_img_from_request() -> tuple:
    """
    Get an image, either an uploaded file (prefered if both are specified), or
    from a URL pointing to a file .
    """
    # If there is a valid file, use it:
    img_fh = request.files["plaque_image_file"]
    img_name = img_fh.filename
    if img_name:
        return img_name, img_fh

    # If no file was uploaded, use plaque_img_url if it has a value:
    if img_url := request.form.get("plaque_image_url", None):
        img_name = os.path.basename(img_url)
        img_fh = urllib.request.urlopen(img_url)
        return img_name, img_fh

    # Otherwise return None, None
    return None, None


def _latlng_get_angles(coords_tags: list) -> tuple:
    """
    DEPRECATED: this isn't used anymore
    Convert GPS exif tag format to hours/degrees/minutes triplet
    """
    hours = float(coords_tags[0][0]) / float(coords_tags[0][1])
    degrees = float(coords_tags[1][0]) / float(coords_tags[1][1])
    minutes = float(coords_tags[2][0]) / float(coords_tags[2][1])
    return (hours, degrees, minutes)


def _latlng_angles_to_dec(ref: str, latlng_angles: list) -> float:
    """
    DEPRECATED: this isn't used anymore
    Convert a degrees, hours, minutes tuple to decimal degrees.
    """
    latlng = (
        float(latlng_angles[0])
        + float(latlng_angles[1]) / 60.0
        + float(latlng_angles[2]) / 3600.0
    )
    if ref not in ["N", "E", "S", "W"]:
        raise SubmitError(f"reference '{ref}' needs to be either N, S, E, or W")
    if ref in ["S", "W"]:
        latlng *= -1.0
    return latlng


def _get_location() -> ndb.GeoPt:
    """Convert form input into a GeoPt location"""
    lat = float(request.form["lat"])
    lng = float(request.form["lng"])
    return ndb.GeoPt(lat, lng)


def _get_tags() -> list:
    """Get and tokenize tags"""
    tags_str = request.form["tags"]
    tags_split = tags_str.split(",")
    tags = [re.sub(r"\s+", " ", t.strip().lower()) for t in tags_split]
    tags = [t for t in tags if t]  # Remove empties
    return tags


def _upload_image(img_fh, plaque) -> None:
    """
    Upload pic into GCS

    The blobstore.create_gs_key and images.get_serving_url calls are
    outside of the with block; I think this is correct. The
    blobstore.create_gs_key call was erroring out on production when it was
    inside the with block.

    If gcs_fn is specified, overwrite that gcs filename. This is used
    for updating the picture.
    """

    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET)
    gcs_filename = dt.datetime.now().strftime("%Y%m%d/%H%M%S")
    blob = bucket.blob(gcs_filename)

    plaque.pic = gcs_filename

    #img_fh.seek(0)  # reset file handle
    base64_img_bytes = img_fh.read()
    blob.upload_from_string(base64_img_bytes)
    blob.make_public()  # TODO might be a better img url for this

    # Kill old image and URL, if they exist. If they don't, ignore any errors:
    #
    if plaque.pic is not None:
        try:
            storage.delete(plaque.pic)
        except:
            pass
    if plaque.img_url is not None:
        try:
            images.delete_serving_url(plaque.img_url)  # TODO
        except:
            pass

    # print("make public URL", make_public_url)
    # print("public URL", blob.public_url)
    # print("media link", blob.media_link)
    plaque.img_url = blob.media_link


def _plaque_for_insert() -> Plaque:
    """
    Make a new Plaque object for insert
    """

    plaque = Plaque(parent=_plaqueset_key())

    plaque.set_title_and_title_url(request.form["title"], _plaqueset_key())
    plaque.description = request.form["description"]
    plaque.location = _get_location()
    plaque.tags = _get_tags()
    plaque.approved = False
    plaque.created_on = dt.datetime.now()
    if user := users.get_current_user():
        plaque.created_by = user
    else:
        plaque.created_by = None
    plaque.updated_on = dt.datetime.now()
    plaque.updated_by = None

    # Upload the image for a new plaque
    (img_name, img_fh) = _get_img_from_request()
    _upload_image(img_fh, plaque)
    # TODO: do we need need to add img_name back to _upload_image?

    # Search index the plaque text
    search.Index(SEARCH_INDEX_NAME).put(plaque.to_search_document())
    plaque.put()
    return plaque


def _add_plaque_post() -> str:
    """Do the POST request for /add"""
    with ndb.Client().context() as context:
        plaque = _plaque_for_insert()
        return _render_template_map("add.html", [plaque], maptext="hello", page_title="added!")


def _add_plaque_get() -> str:
    """Render the page for the GET request to /add"""
    maptext = (
        "Click the plaque's location on the map, or search "
        "for it, or enter its lat/lng location"
    )
    with ndb.Client().context() as context:
        return _render_template_map(
            "add.html", None, maptext=maptext, page_title="Add Plaque"
        )


def _plaque_for_edit(plaque: Plaque) -> Plaque:
    """
    Update the plaque with edits
    """
    search.Index(SEARCH_INDEX_NAME).put(plaque.to_search_document())

    plaque.set_title_and_title_url(request.form["title"], _plaqueset_key())

    plaque.description = request.form["description"]
    plaque.location = _get_location()
    plaque.tags = _get_tags()
    # skip approval for edit pages
    plaque.updated_on = dt.datetime.now()
    plaque.updated_by = None
    # image if included:
    img_name, img_fh = _get_img_from_request()
    if img_name is not None and img_fh is not None:
        _upload_image(img_fh, plaque)
    plaque.img_rot = int(request.form["img_rot"])
    plaque.put()
    return plaque


def _set_approval(plaque_key, approval=True) -> None:
    """Set the approval of a plaque"""
    with ndb.Client().context() as context:
        plaque = ndb.Key(urlsafe=plaque_key).get()
        plaque.approved = approval
        if plaque.approved:
            plaque.created_on = dt.datetime.now()
            plaque.updated_on = dt.datetime.now()
        plaque.put()


def _get_featured() -> Plaque:
    """Get the most recent FeaturedPlaque"""
    featured = FeaturedPlaque.query().order(-Plaque.created_on).get()
    if featured is not None:
        plaque = Plaque.query().filter(Plaque.key == featured.plaque).get()
    else:
        plaque = None
    return plaque


def _set_featured(plaque) -> None:
    """Set a given plaque to be a FeaturedPlaque"""
    featured = FeaturedPlaque()
    featured.plaque = plaque.key
    featured.put()


def _geo_search(lat: float, lng: float, search_radius_meters: int = 5000) -> list:
    """
    Return the plaques within a radius around lat/lng.
    Context is provided by caller.
    """
    search_radius_meters = int(search_radius_meters)
    loc_expr = f"distance(location, geopoint({lat}, {lng}))"
    query = f"{loc_expr} < {search_radius_meters}"

    sortexpr = search.SortExpression(
        expression=loc_expr,
        direction=search.SortExpression.ASCENDING,
        default_value=search_radius_meters,
    )

    search_query = search.Query(
        query_string=query,
        options=search.QueryOptions(
            sort_options=search.SortOptions(expressions=[sortexpr])
        ),
    )

    results = search.Index(SEARCH_INDEX_NAME).search(search_query)
    keys = [ndb.Key(urlsafe=r.doc_id) for r in results]
    plaques = ndb.get_multi(keys)
    return plaques


def _json_for_all(summary: bool = True) -> str:
    """Get the JSON representation of all plaques"""
    plaques_all = []
    num = 1000
    more = True
    cursor = None
    while more:
        plaques, cursor, more = Plaque.fetch_page(num, cursor, urlsafe=False)
        plaques_all.extend(plaques)

    plaque_dicts = [p.to_dict(summary=summary) for p in plaques if p]
    return json.dumps(plaque_dicts)


def _json_for_keys(plaque_keys_str: str, summary: bool = True) -> str:
    """Get the JSON representation of the given plaques"""
    plaque_keys = plaque_keys_str.split("&")

    plaques = []
    with ndb.Client().context() as context:
        for plaque_key in plaque_keys:
            try:
                plaque = ndb.Key(urlsafe=plaque_key).get()
                if plaque:
                    plaques.append(plaque)
            except:
                pass

    if not plaques:
        return ""

    plaque_dicts = [p.to_dict(summary=summary) for p in plaques]
    return json.dumps(plaque_dicts)
