"""
Main run script
"""

import datetime as dt
from google.cloud import ndb
from flask import Flask, render_template
import random

from rtp.models import Plaque, FeaturedPlaque

FIRST_YEAR = 2015
FIRST_MONTH = 9
FIRST_DAY = 9

DEF_NUM_PER_PAGE = 25
DEF_RAND_NUM_PER_PAGE = 5

# SET THIS envar TO GET CREDS:
#
# GOOGLE_APPLICATION_CREDENTIALS=/home/kester/Desktop/gae_tutorial/python-docs-samples/appengine/standard_python3/surlyfritter-python3-2ce73610c763.json # pylint: disable=line-too-long

# [START gae_python38_app]

app = Flask(__name__)


# TODO: get users accounts working
def _loginout() -> dict:
    return dict(isadmin=False, url=None, text=None)


@app.route("/")
def all_plaques():
    # cursor = None # TODO
    per_page = DEF_NUM_PER_PAGE
    # is_random = False # TODO
    # is_featured = True # TODO

    client = ndb.Client()
    with client.context() as context:
        plaques = (
            Plaque.query()
            .filter(Plaque.approved == True)
            .order(-Plaque.created_on)
            .fetch(limit=per_page)
        )

        return render_template(
            "all.html",
            plaques=plaques,
            next_cursor_urlsafe="foo",  # TODO
            loginout=_loginout(),
        )


@app.route("/plaque/<string:search_term>/")
def one_plaque(search_term: str) -> str:
    # TODO: add other search terms possibilities (key, old ID, etc)
    client = ndb.Client()
    with client.context() as context:
        one_plaque = Plaque.query().filter(Plaque.title_url == search_term).get()
        return render_template("one.html", plaques=[one_plaque], loginout=_loginout())


def _random_time(year=FIRST_YEAR, month=FIRST_MONTH, day=FIRST_DAY) -> dt.datetime:
    """
    Utilize the fact that the first plaque submission was 2015-09-09 to
    generate a random time between then and now.
    """
    first = dt.datetime(year, month, day)
    now = dt.datetime.now()
    rand_seconds = random.randint(0, int((now - first).total_seconds()))
    return first + dt.timedelta(seconds=rand_seconds)


@app.route("/random")
@app.route("/random/<int:num_plaques>")
@app.route("/randompage")
@app.route("/randompage/<int:num_plaques>")
def random_plaques(num_plaques: int = 1) -> str:
    plaques = []
    client = ndb.Client()
    with client.context() as context:
        for _ in range(num_plaques):
            plaque = (
                Plaque.query()
                .filter(Plaque.approved == True)
                .filter(Plaque.created_on > _random_time())
                .get()
            )
            plaques.append(plaque)
        return render_template("all.html", plaques=plaque, loginout=_loginout())


@app.route("/counts")
def counts() -> str:
    client = ndb.Client()
    with client.context() as context:
        query = Plaque.query()
        num_plaques = query.count()
        num_pending = query.filter(Plaque.approved == False).count()
        return f"{num_plaques} plaques, {num_pending} pending"


if __name__ == "__main__":
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host="127.0.0.1", port=8080, debug=True)
# [END gae_python38_app]
