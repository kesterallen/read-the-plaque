"""
Main run script. This file should only contain the routes, other code is in rtp/utils
"""

import json
import random
from urllib.parse import quote

from google.cloud import ndb
from google.appengine.api import wrap_wsgi_app, users, search, memcache

from flask import Flask, request, redirect

from rtp.models import Plaque
from rtp.utils import (
    SEARCH_INDEX_NAME,
    _add_plaque_get,
    _add_plaque_post,
    _geo_search,
    _get_featured,
    _get_random_plaque,
    _get_random_time,
    _json_for_all,
    _json_for_keys,
    _memcache_get,
    _plaque_for_edit,
    _plaqueset_key,
    _render_template,
    _render_template_map,
    _set_approval,
    _set_featured,
)


NUM_PENDING = 5
NUM_RSS = 10
NUM_PAGE = 10
NUM_NEARBY = 5
RAND_NUM_PER_PAGE = 5

DELETE_PRIVS = ["kester"]


# SET THIS envar TO GET CREDS:
#
# GOOGLE_APPLICATION_CREDENTIALS=/home/kester/Desktop/gae_tutorial/python-docs-samples/appengine/standard_python3/surlyfritter-python3-2ce73610c763.json # pylint: disable=line-too-long

# [START gae_python38_app]

app = Flask(__name__)
app.wsgi_app = wrap_wsgi_app(app.wsgi_app)


@app.route("/", methods=["GET", "HEAD"])
@app.route("/page/<string:cursor>", methods=["GET"])
def many_plaques(cursor: str = None) -> str:
    """View a page of multiple plaques"""
    # Return a lightweight response for a HEAD request
    if request.method == "HEAD":
        with ndb.Client().context() as context:
            return _render_template("head.html")

    if rendered := _memcache_get():
        return rendered
    with ndb.Client().context() as context:
        cursor = ndb.Cursor(urlsafe=cursor) if cursor else None
        plaques, cursor, more = Plaque.fetch_page(NUM_PAGE, cursor)
        cursor = cursor.urlsafe().decode() if cursor is not None else None
        return _render_template(
            "all.html",
            plaques,
            featured_plaque=_get_featured(),
            cursor=cursor,
            more=more,
        )


@app.route("/pending")
@app.route("/pending/<int:num>")
def pending_plaques(num: int = NUM_PENDING) -> str:
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
    num: int = RAND_NUM_PER_PAGE, num_to_select_from: int = 500
) -> str:
    """View a random list of pending plaques. Note: admin only"""

    if not users.is_current_user_admin():
        print("redirecting to homepage because user is not admin")
        return redirect("/")

    with ndb.Client().context() as context:
        plaques = Plaque.pending_list(num_to_select_from)
        rand_plaques = random.sample(plaques, num)
        return _render_template_map(plaques=rand_plaques)


@app.route("/nextpending")
def next_pending_plaque() -> str:
    """View the next pending plaque. Note: admin only"""
    if not users.is_current_user_admin():
        print("redirecting to homepage because user is not admin")
        return redirect("/")

    with ndb.Client().context() as context:
        plaques = Plaque.pending_list(1)
        plaque = plaques[0]
        return redirect(plaque.title_page_url)


@app.route("/plaque/<string:title_url>", methods=["GET", "HEAD"])
def one_plaque(title_url: str) -> str:
    """View one plaque."""
    # Return a lightweight response for a HEAD request
    if request.method == "HEAD":
        return _render_template("head.html")

    with ndb.Client().context() as context:
        # Get plaque if exists, otherwise get earliest
        plaque = Plaque.query().filter(Plaque.title_url == title_url).get()
        if plaque is None:
            plaque = Plaque.query().order(Plaque.created_on).get()

        if rendered := _memcache_get():
            return rendered
        return _render_template_map("one.html", [plaque], plaque.title)


@app.route("/add", methods=["GET", "POST"])
@app.route("/submit", methods=["GET", "POST"])
@app.route("/submit-your-own", methods=["GET", "POST"])
def add_plaque() -> str:
    """Add a new plaque"""
    if request.method == "POST":
        return _add_plaque_post()
    if request.method == "GET":
        return _add_plaque_get()
    return redirect("/")


@app.route("/edit", methods=["POST"])
@app.route("/edit/<string:plaque_key>", methods=["GET"])
def edit_plaque(plaque_key: str = None) -> str:
    """Edit an existing plaque. Note: admin only"""

    if not users.is_current_user_admin():
        print("redirecting to homepage because user is not admin")
        return redirect("/")

    if request.method == "POST":
        plaque_key = request.form.get("plaque_key", None)
        if plaque_key is None:
            return redirect("/")

        with ndb.Client().context() as context:
            plaque = ndb.Key(urlsafe=plaque_key).get()
            plaque = _plaque_for_edit(plaque)
            return redirect(plaque.title_page_url)

    if request.method == "GET":
        with ndb.Client().context() as context:
            plaque = ndb.Key(urlsafe=plaque_key).get()
            return _render_template_map(
                "edit.html",
                [plaque],
                page_title="Edit Plaque",
                message="Editing Plaque",
            )

    print("request method not valid", request.method)
    return redirect("/")


@app.route("/approve", methods=["POST"])
@app.route("/approve/<string:plaque_key>", methods=["GET"])
def approve_plaque(plaque_key: str = None, approval: bool = True) -> str:
    """Turn on the approval of an existing plaque. Note: admin only"""

    if not users.is_current_user_admin():
        print("redirecting to homepage because user is not admin")
        return redirect("/")

    if plaque_key is None:
        plaque_key = request.form.get("plaque_key", None)

    if plaque_key:
        _set_approval(plaque_key, approval)
    else:
        print("no plaque key")

    return redirect("/nextpending")


@app.route("/disapprove", methods=["POST"])
@app.route("/disapprove/<string:plaque_key>", methods=["GET"])
def disapprove_plaque(plaque_key: str = None, approval: bool = False) -> str:
    """Turn off the approval for a plaque (unpublish it)"""
    return approve_plaque(plaque_key, approval)


@app.route("/random")
@app.route("/random/<int:num_plaques>")
@app.route("/randompage")
@app.route("/randompage/<int:num_plaques>")
def random_plaques(num_plaques: int = RAND_NUM_PER_PAGE) -> str:
    """View a random group of plaques."""

    plaques = []
    with ndb.Client().context() as context:
        for _ in range(num_plaques):
            plaque = (
                Plaque.query()
                .filter(Plaque.approved == True)
                .filter(Plaque.created_on > _get_random_time())
                .get()
            )
            plaques.append(plaque)
        return _render_template("all.html", plaques)


@app.route("/setfeatured/<string:plaque_key>", methods=["GET"])
def set_featured(plaque_key: str) -> str:
    """Set a given plaque to be the featured one. Note: admin only"""

    if not users.is_current_user_admin():
        print("redirecting to homepage because user is not admin")
        return redirect("/")

    with ndb.Client().context() as context:
        plaque = ndb.Key(urlsafe=plaque_key).get()
        _set_featured(plaque)
        return redirect("/flush")


@app.route("/featured", methods=["GET"])
def get_featured() -> str:
    """Show the featured plaque"""
    with ndb.Client().context() as context:
        plaque = _get_featured()
        return _render_template("one.html", [plaque])


@app.route("/featured/geojson", methods=["GET"])
@app.route("/tweet", methods=["GET"])
def get_featured_geojson() -> str:
    """Display the GeoJSON for the featured plaque"""
    with ndb.Client().context() as context:
        plaque = _get_featured()
        return plaque.json_for_tweet if plaque else "No featured plaque"


@app.route("/geojson/<string:title_url>", methods=["GET"])
@app.route("/geojson/", methods=["POST"])
def get_geojson(title_url: str = None) -> str:
    """
    GET: Display the GeoJSON for the given plaque
    POST: Returns the JSON for plaques with updated_on after the specified date.
    """
    if request.method == "POST":
        with ndb.Client().context() as context:
            updated_on_str = request.form.get("updated_on")
            geojson = Plaque.created_after_geojson(updated_on_str)
        return json.dumps(geojson)

    if request.method == "GET":
        with ndb.Client().context() as context:
            plaque = Plaque.query().filter(Plaque.title_url == title_url).get()
            return plaque.json_for_tweet if plaque else f"No plaque for {title_url}"

    return f"Method {request.method} not supported in /geojson"


@app.route("/featured/random", methods=["GET"])
def set_featured_random() -> str:
    """
    Set a random plaque to be the featured one and respond with the tweet JSON
    """
    with ndb.Client().context() as context:
        plaque = _get_random_plaque()
        _set_featured(plaque)
        return plaque.json_for_tweet


@app.route("/tag/<string:tag>")
@app.route("/tag/<string:tag>/<int:num>")
def tagged_plaques(tag: str, num: int = NUM_PAGE) -> str:
    """View a group of plaques with a given tag."""
    with ndb.Client().context() as context:
        plaques = (
            Plaque.query()
            .filter(Plaque.approved == True)
            .filter(Plaque.tags == tag)
            .order(-Plaque.created_on)
            .fetch(limit=num)
        )
        return _render_template("all.html", plaques)


@app.route("/map")
@app.route("/map/<string:lat>/<string:lng>")
@app.route("/map/<string:lat>/<string:lng>/<string:zoom>")
def map_plaques(lat: str = None, lng: str = None, zoom: str = None) -> str:
    """View the big map page with optional center/zoom"""
    with ndb.Client().context() as context:
        num_plaques = Plaque.query().filter(Plaque.approved == True).count()
        template_values = {
            "counts": num_plaques,
            "bigmap": True,
            # specify mapzoom?
        }
        if lat is not None and lng is not None:
            template_values["bigmap_center"] = True
            template_values["bigmap_lat"] = float(lat)
            template_values["bigmap_lng"] = float(lng)

            if zoom is not None:
                template_values["bigmap_zoom"] = float(zoom)

        return _render_template_map("bigmap.html", [], "Big Map", **template_values)


@app.route("/counts")
def counts() -> str:
    """View the counts"""
    with ndb.Client().context() as context:
        query = Plaque.query()
        num_plaques = query.count()
        num_pending = query.filter(Plaque.approved == False).count()
        return f"<ul><li>{num_plaques} plaques</li><li>{num_pending} pending</li></ul>"


@app.route("/rss")
def rss_feed() -> str:
    """RSS feed for newly-added plaques"""
    with ndb.Client().context() as context:
        plaques, _, _ = Plaque.fetch_page(NUM_RSS)
        return _render_template("feed.xml", plaques=plaques)


@app.route("/about")
def about() -> str:
    """The "about" page"""
    with ndb.Client().context() as context:
        return _render_template("about.html")


@app.route(
    "/geo/<float(signed=True):lat>/<float(signed=True):lng>/<float(signed=True):search_radius_meters>"
)
def geo_plaques(lat: float, lng: float, search_radius_meters: float) -> str:
    """
    Return plaques within search_radius_meters of lat/lng, sorted by distance
    from lat/lng.
    """
    with ndb.Client().context() as context:
        plaques = _geo_search(lat, lng, search_radius_meters)
        return _render_template_map(plaques=plaques, page_title="Geo Search")


@app.route("/search", methods=["POST"])
def search_plaques_form() -> str:
    """A POST redirect for search"""
    if search_term := request.form.get("search_term", None):
        return redirect(f"/search/{search_term}")
    return redirect("/")


@app.route("/search/<string:search_term>", methods=["GET"])
def search_plaques(search_term: str) -> str:
    """
    Display a search results page after sanitizing the user-supplied search
    term with the urllib.parse.quote method.
    """
    with ndb.Client().context() as context:
        results = search.Index(SEARCH_INDEX_NAME).search(quote(search_term))

        # Get plaques from search results, hiding unpublished plaques from
        # non-admins. The try/catch loop is to avoid a bug reported by Alan
        # Reno on 4-April-2024 that search was broken for his name, I think it
        # was because approval wasn't set on newly-submitted plaques yet, but
        # not sure.
        plaques = []
        for result in results:
            try:
                plaque = ndb.Key(urlsafe=result.doc_id).get()
                if plaque.approved or users.is_current_user_admin():
                    plaques.append(plaque)
            except Exception as err:
                print(f"error parsing results in /search/{search_term}: \n\n{err}")

        return _render_template_map(plaques=plaques, page_title="Search")


@app.route("/nearby/<float(signed=True):lat>/<float(signed=True):lng>", methods=["GET"])
@app.route(
    "/nearby/<float(signed=True):lat>/<float(signed=True):lng>/<int:num>",
    methods=["GET"],
)
def nearby_plaques(lat: float, lng: float, num: int = NUM_NEARBY) -> str:
    """Get a page of nearby plaques"""
    num = min(num, 20)

    with ndb.Client().context() as context:
        # Reduce search billing cost by making nearby search less granular:
        # 500 m, 50 km, 500 km
        search_radii_meters = [5 * 10**i for i in [2, 4, 6]]
        for i, search_radius_meters in enumerate(search_radii_meters):
            plaques = _geo_search(lat, lng, search_radius_meters)
            if len(plaques) > num:
                break
        return _render_template_map(plaques=plaques, page_title="Nearby Plaques")


@app.route("/updatejp", methods=["GET"])  # delete?
@app.route("/fulljp", methods=["GET"])  # delete?
@app.route("/alljp", methods=["GET"])
@app.route("/alljp/<string:plaque_keys_str>", methods=["GET"])
def json_plaques(plaque_keys_str: str = None, summary: bool = True):
    """
    JSON summary for the plaques specified; if no plaques are specified,
    do all plaques.
    """
    if plaque_keys_str is None:
        json_output = _json_for_all(summary)
    else:
        json_output = _json_for_keys(plaque_keys_str, summary)
    return json_output


@app.route("/delete", methods=["POST"])
def delete_plaque() -> str:
    """Remove one plaque and its associated GCS image."""
    if not users.is_current_user_admin():
        return "admin only, please log in"

    user = users.get_current_user()
    name = "anon" if user is None else user.nickname()
    if name not in DELETE_PRIVS:
        return f"delete is not enabled for user '{name}'"

    with ndb.Client().context() as context:
        if plaque_key := request.form.get("plaque_key", None):
            plaque = ndb.Key(urlsafe=plaque_key).get()
        else:
            return f"no plaque for key {_plaqueset_key}"

        try:
            gcs.delete(plaque.pic)  # TODO # blob.delete?

            #  TODO Delete search index for this document
            # plaque_search_index = search.Index(SEARCH_INDEX_NAME)
            # results = plaque_search_index.search(search_term)
            # for result in results:
            #      TODO ? plaques = [ndb.Key(urlsafe=r.doc_id).get() for r in results]
            #     plaque_search_index.delete(result.doc_id)
        except:
            pass

        plaque.key.delete()
    return redirect("/nextpending")


@app.route("/flush/silent")
@app.route("/flush")
def flush_memcache() -> str:
    """Flush the memcache and go to the homepage"""
    memcache.flush_all()
    return redirect("/") if request.path == "/flush" else ""


# TODO
@app.errorhandler(404)
def not_found(err):
    return f"404 error {err}"
    # return render_template("404.html")


# TODO
@app.errorhandler(500)
def server_error(err):
    return f"500 error {err}"
    # return render_template("500.html")


if __name__ == "__main__":
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host="127.0.0.1", port=8080, debug=True)
# [END gae_python38_app]
