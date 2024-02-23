"""
Main run script
"""

import base64
import datetime as dt
import os
import re
import random
import urllib

from google.cloud import ndb
from google.cloud import storage

from flask import Flask, render_template, request, redirect

from rtp.models import Plaque, FeaturedPlaque

from google.appengine.api import wrap_wsgi_app, users


# GCS_BUCKET configuration: This appears to work for the bucket named
# 'read-the-plaque.appspot.com', Don't change this to, say, readtheplaque.com.
#
# GCS_BUCKET = "/read-the-plaque.appspot.com"
GCS_BUCKET = "read-the-plaque.appspot.com"

FIRST_YEAR = 2015
FIRST_MONTH = 9
FIRST_DAY = 9

DEF_PLAQUESET_NAME = "public"

DEF_NUM_PENDING = 5
DEF_NUM_RSS = 10
DEF_NUM_PER_PAGE = 25
DEF_RAND_NUM_PER_PAGE = 5


class SubmitError(Exception):
    pass


# SET THIS envar TO GET CREDS:
#
# GOOGLE_APPLICATION_CREDENTIALS=/home/kester/Desktop/gae_tutorial/python-docs-samples/appengine/standard_python3/surlyfritter-python3-2ce73610c763.json # pylint: disable=line-too-long

# [START gae_python38_app]

app = Flask(__name__)
app.wsgi_app = wrap_wsgi_app(app.wsgi_app)

# TODO: get cursor or next button working


def get_key(key_filename="key_googlemaps.txt"):
    """Get the value of the key in the given file"""
    with open(key_filename) as key_fh:
        key = key_fh.read().rstrip()
    return key


# Set a parent key on the Plaque objects to ensure that they are all in the
# same entity group. Queries across the single entity group will be consistent.
# However, the write rate should be limited to ~1/second.
#
def plaqueset_key(plaqueset_name=DEF_PLAQUESET_NAME):
    """
    Constructs a Datastore key for a Plaque entity. Use plaqueset_name as
    the key.
    """
    return ndb.Key("Plaque", plaqueset_name)


def _render_template(template_file: str, plaques: list = None, **kwargs) -> str:
    """A wrapper for flask.render_template that injects some defaults"""
    return render_template(
        template_file,
        plaques=plaques,
        next_cursor_urlsafe="foo",  # TODO
        loginout=_loginout(),
        footer_items=_get_footer_items(),
        **kwargs,
    )


def _render_template_map(
    template_file: str = "all.html",
    plaques: list = None,
    page_title: str = "View Pending Plaques",
    **kwargs,
) -> str:
    return _render_template(
        template_file,
        plaques,
        bounding_box=_get_bounding_box(plaques),
        mapzoom=10,
        maptext="",
        google_maps_api_key=get_key(),
        page_title=page_title,
        **kwargs,
    )


def _get_footer_items():
    """
    Just 5 tags for the footer.
    """
    # TODO: turn this back on when you figure out memcaching
    # random_plaques = [get_random_plaque() for _ in range(5)]
    # tags = get_random_tags()
    random_plaques = []
    tags = []
    footer_items = {
        "tags": tags,
        "new_plaques": random_plaques,
    }
    return footer_items


def _loginout() -> dict:
    is_admin = users.is_current_user_admin()
    if user := users.get_current_user():
        text = f"Log out {user.nickname()}"
        url = users.create_logout_url("/")
    else:
        text = "Admin login"
        url = users.create_login_url("/")

    return dict(
        is_admin=is_admin,
        text=text,
        url=url,
    )


@app.route("/", methods=["GET", "HEAD"])
def many_plaques():
    """View a page of multiple plaques"""
    # Return a lightweight response for a HEAD request
    if request.method == "HEAD":
        return _render_template("head.html")

    # cursor = None # TODO
    per_page = DEF_NUM_PER_PAGE
    # is_random = False # TODO

    with ndb.Client().context() as context:
        plaques, next_cur, more = Plaque.fetch_page(DEF_NUM_PER_PAGE)
        featured_plaque = _get_featured()
        return _render_template("all.html", plaques, featured_plaque=featured_plaque)


@app.route("/pending")
@app.route("/pending/<int:num>")
def pending_plaques(num: int = DEF_NUM_PENDING) -> str:
    """View the most recent pending plaques. Note: admin only"""

    if not users.is_current_user_admin():
        print("redirecting to homepage because user is not admin")
        return redirect("/")

    with ndb.Client().context() as context:
        plaques = Plaque.pending_list(num)
        return _render_template_map(plaques=plaques)


@app.route("/randpending")
@app.route("/randpending/<int:num>")
def rand_pending_plaques(
    num: int = DEF_NUM_PENDING, num_to_select_from: int = 500
) -> str:
    """View a random list of pending plaques. Note: admin only"""

    if not users.is_current_user_admin():
        print("redirecting to homepage because user is not admin")
        return redirect("/")

    with ndb.Client().context() as context:
        plaques = Plaque.pending_list(num_to_select_from)
        rand_plaques = random.sample(plaques, num)
        return _render_template_map(plaques=rand_plaques)


@app.route("/plaque/<string:title_url>", methods=["GET", "HEAD"])
def one_plaque(title_url: str) -> str:
    """View one plaque."""
    # Return a lightweight response for a HEAD request
    if request.method == "HEAD":
        return _render_template("head.html")

    # TODO: add other search terms possibilities (key, old ID, etc)

    with ndb.Client().context() as context:
        # Get plaque if exists, otherwise get earliest
        plaque = Plaque.query().filter(Plaque.title_url == title_url).get()
        if plaque is None:
            plaque = Plaque.query().order(Plaque.created_on).get()

        return _render_template_map("one.html", [plaque], plaque.title)


def _get_bounding_box(plaques: list[Plaque]) -> list[float]:
    """Calculate the bounding box corners for the coordinates of a list of plaques"""
    if plaques:
        lats = [p.location.latitude for p in plaques]
        lngs = [p.location.longitude for p in plaques]
        bounding_box = [[min(lngs), min(lats)], [max(lngs), max(lats)]]
    else:
        bounding_box = None
    return bounding_box


def _get_img_from_request():
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
    if request.form["plaque_image_url"]:
        img_url = request.form["plaque_image_url"]
        img_name = os.path.basename(img_url)
        img_fh = urllib.request.urlopen(img_url)
        return img_name, img_fh

    # Otherwise return None, None
    return None, None


def _latlng_get_angles(coords_tags):
    """
    Convert GPS exif tag format to hours/degrees/minutes triplet
    """
    hours = float(coords_tags[0][0]) / float(coords_tags[0][1])
    degrees = float(coords_tags[1][0]) / float(coords_tags[1][1])
    minutes = float(coords_tags[2][0]) / float(coords_tags[2][1])
    return (hours, degrees, minutes)


def _latlng_angles_to_dec(ref, latlng_angles):
    """Convert a degrees, hours, minutes tuple to decimal degrees."""
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


def _get_location():
    """Convert form input into a GeoPt location"""
    lat = float(request.form["lat"])
    lng = float(request.form["lng"])
    return ndb.GeoPt(lat, lng)


def _get_tags():
    """Get and tokenize tags"""
    tags_str = request.form["tags"]
    tags_split = tags_str.split(",")
    tags = [re.sub(r"\s+", " ", t.strip().lower()) for t in tags_split]
    tags = [t for t in tags if t]  # Remove empties
    return tags


# TODO: remove img_name from signature?
def _upload_image(img_name, img_fh, plaque):
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

    img_fh.seek(0)  # reset file handle
    base64_img_bytes = img_fh.read()
    blob.upload_from_string(base64_img_bytes)
    make_public_url = blob.make_public()

    #    # Kill old image and URL, if they exist. If they don't, ignore any errors:
    #    #
    #    if plaque.pic is not None:
    #        try:
    #            storage.delete(plaque.pic)
    #        except:
    #            pass
    #    if plaque.img_url is not None:
    #        try:
    #            images.delete_serving_url(plaque.img_url)
    #        except:
    #            pass

    # print("make public URL", make_public_url)
    # print("public URL", blob.public_url)
    # print("media link", blob.media_link)
    plaque.img_url = blob.media_link


def _plaque_for_insert() -> Plaque:
    """
    Make a new Plaque object for insert
    """

    ### plaque_search_index = search.Index(PLAQUE_SEARCH_INDEX_NAME) # TODO figure out search in new GCP
    ### plaque_search_index.put(plaque.to_search_document()) # TODO figure out search in new GCP

    plaque = Plaque(parent=plaqueset_key())

    plaque.set_title_and_title_url(request.form["title"], plaqueset_key())
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
    img_name, img_fh = _get_img_from_request()
    _upload_image(img_name, img_fh, plaque)
    return plaque


def _add_plaque_post() -> str:
    """Do the POST request for /add"""
    with ndb.Client().context() as context:
        plaque = _plaque_for_insert()
        plaque.put()  # ? TODO
        return _render_template_map("add.html", [plaque])
        #return _render_template(
            #"add.html",
            #[plaque],
            #bounding_box=_get_bounding_box([plaque]),
        #)


def _add_plaque_get() -> str:
    """Render the page for the GET request to /add"""
    maptext = (
        "Click the plaque's location on the map, or search "
        "for it, or enter its lat/lng location"
    )
    return _render_template_map("add.html", None, maptext=maptext, page_title="Add Plaque")


@app.route("/add", methods=["GET", "POST"])
@app.route("/submit", methods=["GET", "POST"])
@app.route("/submit-your-own", methods=["GET", "POST"])
def add_plaque() -> str:
    """Add a new plaque"""
    if request.method == "POST":
        return _add_plaque_post()
    elif request.method == "GET":
        return _add_plaque_get()
    else:
        return redirect("/")


def _plaque_for_edit(plaque: Plaque) -> Plaque:
    """
    Update the plaque with edits
    """

    ### plaque_search_index = search.Index(PLAQUE_SEARCH_INDEX_NAME) # TODO figure out search in new GCP
    ### plaque_search_index.put(plaque.to_search_document()) # TODO figure out search in new GCP

    plaque.set_title_and_title_url(request.form["title"], plaqueset_key())

    plaque.description = request.form["description"]
    plaque.location = _get_location()
    plaque.tags = _get_tags()
    # skip approval for edit pages
    plaque.updated_on = dt.datetime.now()
    plaque.updated_by = None
    # image if included:
    img_name, img_fh = _get_img_from_request()
    if img_name is not None and img_fh is not None:
        _upload_image(img_name, img_fh, plaque)
    plaque.img_rot = int(request.form["img_rot"])
    plaque.put()
    return plaque


@app.route("/edit", methods=["POST"])
@app.route("/edit/<string:plaque_key>", methods=["GET"])
def edit_plaque(plaque_key: str = None) -> str:
    """Edit an existing plaque. Note: admin only"""

    if not users.is_current_user_admin():
        print("redirecting to homepage because user is not admin")
        return redirect("/")

    if request.method == "POST":
        plaque_key = request.form["plaque_key"]
        if plaque_key is None:
            return redirect("/")

        with ndb.Client().context() as context:
            plaque = ndb.Key(urlsafe=plaque_key).get()
            plaque = _plaque_for_edit(plaque)
            return redirect(plaque.title_page_url)

    if request.method == "GET":
        with ndb.Client().context() as context:
            plaque = ndb.Key(urlsafe=plaque_key).get()
            return _render_template(
                "edit.html", [plaque], page_title="Edit Plaque", message="Editing Plaque"
            )

    print("request method not valid", request.method)
    return redirect("/")


def _set_approval(plaque_key, approval=True):
    """Set the approval of a plaque"""
    with ndb.Client().context() as context:
        plaque = ndb.Key(urlsafe=plaque_key).get()
        plaque.approved = approval
        if plaque.approved:
            plaque.created_on = datetime.datetime.now()
            plaque.updated_on = datetime.datetime.now()
        plaque.put()


@app.route("/approve/<string:plaque_key>", methods=["POST"])
def approve_plaque(plaque_key: str, approval: bool = True) -> str:
    """Turn on the approval of an existing plaque. Note: admin only"""

    if not users.is_current_user_admin():
        print("redirecting to homepage because user is not admin")
        return redirect("/")

    _set_approval(plaque_key, approval)
    return redirect("/")


@app.route("/disapprove/<string:plaque_key>", methods=["POST"])
def disapprove_plaque(plaque_key: str = None) -> str:
    """Turn off the approval of an existing plaque. Note: admin only"""
    return approve_plaque(plaque_key, False)


@app.route("/random")
@app.route("/random/<int:num_plaques>")
@app.route("/randompage")
@app.route("/randompage/<int:num_plaques>")
def random_plaques(num_plaques: int = 5) -> str:
    """View a random group of plaques."""

    def _random_time(year=FIRST_YEAR, month=FIRST_MONTH, day=FIRST_DAY) -> dt.datetime:
        """
        Utilize the fact that the first plaque submission was 2015-09-09 to
        generate a random time between then and now.
        """
        first = dt.datetime(year, month, day)
        now = dt.datetime.now()
        rand_seconds = random.randint(0, int((now - first).total_seconds()))
        return first + dt.timedelta(seconds=rand_seconds)

    plaques = []
    with ndb.Client().context() as context:
        for _ in range(num_plaques):
            plaque = (
                Plaque.query()
                .filter(Plaque.approved == True)
                .filter(Plaque.created_on > _random_time())
                .get()
            )
            plaques.append(plaque)
        return _render_template("all.html", plaques)

# TODO: def _get_rand_featured():

def _get_featured():
    """Get the most recent FeaturedPlaque"""
    featured = FeaturedPlaque.query().order(-Plaque.created_on).get()
    if featured is not None:
        plaque = Plaque.query().filter(Plaque.key == featured.plaque).get()
    else:
        plaque = None
    return plaque

def _set_featured(plaque):
    """Set a given plaque to be a FeaturedPlaque"""
    featured = FeaturedPlaque()
    featured.plaque = plaque.key
    featured.put()

@app.route("/setfeatured/<string:plaque_key>", methods=["GET"])
def set_featured(plaque_key : str) -> str:
    """Set a given plaque to be the featured one. Note: admin only"""

    if not users.is_current_user_admin():
        print("redirecting to homepage because user is not admin")
        return redirect("/")

    with ndb.Client().context() as context:
        plaque = ndb.Key(urlsafe=plaque_key).get()
        _set_featured(plaque)
        redirect('/')

@app.route("/featured", methods=["GET"])
def get_featured() -> str:
    """Show the featured plaque"""
    with ndb.Client().context() as context:
        plaque = _get_featured()
        return _render_template("one.html", [plaque])

@app.route("/featured/geojson", methods=["GET"])
@app.route("/tweet", methods=["GET"])
def get_featured_geojson():
    """Display the GeoJSON for the featured plaque"""
    with ndb.Client().context() as context:
        plaque = _get_featured()
        return plaque.json_for_tweet if plaque else "No featured plaque"

@app.route("/geojson/<string:title_url>", methods=["GET"])
def get_geojson(title_url: str) -> str:
    """Display the GeoJSON for the given plaque"""
    with ndb.Client().context() as context:
        plaque = Plaque.query().filter(Plaque.title_url == title_url).get()
        return plaque.json_for_tweet if plaque else f"No plaque for {title_url}"
        
# TODO when get_random_plaque is done
#@app.route('/featured/random',methods=["GET"])
#    with ndb.Client().context() as context:

# TODO: add argument for number of plaques
@app.route("/tag/<string:tag>")
def tagged_plaques(tag: str, only_approved: bool = True) -> str:
    """View a group of plaques with a given tag."""
    with ndb.Client().context() as context:
        query = Plaque.query()
        if only_approved:
            query = query.filter(Plaque.approved == True)
        plaques = (
            query.filter(Plaque.tags == tag)
            .order(-Plaque.created_on)
            .fetch(limit=DEF_NUM_PER_PAGE)
        )
        return _render_template("all.html", plaques)


@app.route("/map")
@app.route("/map/<string:lat>/<string:lng>")
@app.route("/map/<string:lat>/<string:lng>/<string:zoom>")
def map(lat: str = None, lng: str = None, zoom: str = None) -> str:
    """View the big map page with optional center/zoom"""
    with ndb.Client().context() as context:
        num_plaques = Plaque.query().filter(Plaque.approved == True).count()
        template_values = {
            "google_maps_api_key": get_key(),
            "counts": num_plaques,
            "bigmap": True,
        }
        if lat is not None and lng is not None:
            template_values["bigmap_center"] = True
            template_values["bigmap_lat"] = float(lat)
            template_values["bigmap_lng"] = float(lng)

            if zoom is not None:
                template_values["bigmap_zoom"] = float(zoom)

        # TODO: switch this to _render_template_map? unclear if that's useful
        return _render_template("bigmap.html", [], **template_values)


@app.route("/counts")
def counts() -> str:
    """View the counts"""

    verbose = request.args.get("verbose", default=False, type=bool)

    with ndb.Client().context() as context:
        query = Plaque.query()
        num_plaques = query.count()
        num_pending = query.filter(Plaque.approved == False).count()

        return (
            f"<ul><li>{num_plaques} plaques</li><li>{num_pending} pending</li></ul>"
            if verbose
            else f"{num_plaques} plaques, {num_pending} pending"
        )


@app.route("/rss")
def rss_feed() -> str:
    """RSS feed for newly-added plaques"""
    with ndb.Client().context() as context:
        plaques, next_cur, more = Plaque.fetch_page(DEF_NUM_RSS)
        return _render_template("feed.xml", plaques=plaques)


@app.route("/about")
def about() -> str:
    """Read the about page. This could be a static page"""
    return _render_template("about.html")


# TODO
# /flush
# /nearby # TODO new API for search?
# /geo
# /alljp /updatejp /fulljp

# Clean up app.yaml
# Point app.yaml stuff to static pages where appropriate


if __name__ == "__main__":
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host="127.0.0.1", port=8080, debug=True)
# [END gae_python38_app]
