"""
Main run script
"""

import datetime as dt
from google.cloud import ndb
from flask import Flask, render_template, request
import random

from rtp.models import Plaque, FeaturedPlaque

FIRST_YEAR = 2015
FIRST_MONTH = 9
FIRST_DAY = 9

DEF_NUM_PENDING = 5
DEF_NUM_RSS = 10
DEF_NUM_PER_PAGE = 25
DEF_RAND_NUM_PER_PAGE = 5

# SET THIS envar TO GET CREDS:
#
# GOOGLE_APPLICATION_CREDENTIALS=/home/kester/Desktop/gae_tutorial/python-docs-samples/appengine/standard_python3/surlyfritter-python3-2ce73610c763.json # pylint: disable=line-too-long

# [START gae_python38_app]

app = Flask(__name__)

# TODO: get cursor or next button working


def get_key(key_filename="key_googlemaps.txt"):
    """Get the value of the key in the given file"""
    with open(key_filename) as key_fh:
        key = key_fh.read().rstrip()
    return key


# TODO: get users accounts working
def _loginout() -> dict:
    return dict(isadmin=False, url=None, text=None)


@app.route("/", methods=["GET", "HEAD"])
def many_plaques():
    """View a page of multiple plauqes"""
    # Return a lightweight response for a HEAD request
    if request.method == "HEAD":
        return render_template("head.html")

    # cursor = None # TODO
    per_page = DEF_NUM_PER_PAGE
    # is_random = False # TODO
    # is_featured = True # TODO

    with ndb.Client().context() as context:
        plaques, next_cur, more = Plaque.fetch_page(DEF_NUM_PER_PAGE)
        return render_template(
            "all.html",
            plaques=plaques,
            next_cursor_urlsafe="foo",  # TODO
            loginout=_loginout(),
        )


@app.route("/pending")
@app.route("/pending/<int:num>")
def pending_plaques(num: int = DEF_NUM_PENDING) -> str:
    """View the most recent pending plaques."""
    with ndb.Client().context() as context:
        plaques = Plaque.pending_list(num)
        return render_template(
            "all.html",
            plaques=plaques,
            next_cursor_urlsafe="foo",  # TODO
            loginout=_loginout(),
        )


@app.route("/plaque/<string:search_term>/", methods=["GET", "HEAD"])
def one_plaque(search_term: str) -> str:
    """View one plaque."""
    # Return a lightweight response for a HEAD request
    if request.method == "HEAD":
        return render_template("head.html")

    # TODO: add other search terms possibilities (key, old ID, etc)
    with ndb.Client().context() as context:
        plaque = Plaque.query().filter(Plaque.title_url == search_term).get()
        return render_template("one.html", plaques=[plaque], loginout=_loginout())


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
        return render_template("all.html", plaques=plaques, loginout=_loginout())


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
        return render_template("all.html", plaques=plaques, loginout=_loginout())


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

        return render_template("bigmap.html", **template_values)


@app.route("/counts")
def counts() -> str:
    """View the counts"""
    # TODO: add verbose flag
    with ndb.Client().context() as context:
        query = Plaque.query()
        num_plaques = query.count()
        num_pending = query.filter(Plaque.approved == False).count()
        return f"{num_plaques} plaques, {num_pending} pending"


@app.route("/rss")
def rss_feed() -> str:
    """RSS feed for newly-added plaques"""
    with ndb.Client().context() as context:
        plaques, next_cur, more = Plaque.fetch_page(DEF_NUM_RSS)
        return render_template("feed.xml", plaques=plaques)


@app.route("/about")
def about() -> str:
    """Read the about page. This could be a static page"""
    return render_template("about.html")


# TODO
# /add /submit /submit-your-own
# /edit
# /randpending
# /flush
# /nearby # TODO new API for search?
# /geo
# /featured /setfeatured /featured/random /featured/geojson
# /geojson
# /tweet
# /alljp /updatejp /fulljp


if __name__ == "__main__":
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host="127.0.0.1", port=8080, debug=True)
# [END gae_python38_app]
