"""
Main run script
"""

from google.cloud import ndb
from flask import Flask, render_template

from rtp.models import Plaque, FeaturedPlaque

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
    # cursor = None
    per_page = DEF_NUM_PER_PAGE
    # is_random = False
    # is_featured = True

    client = ndb.Client()
    with client.context() as context:
        plaques = (
            Plaque.query()
            .filter(Plaque.approved == True)
            .order(-Plaque.created_on)
            .fetch(limit=per_page)
        )
        for plaque in plaques:
            print(plaques)


@app.route("/plaque/<string:search_term>/")
def one_plaque(search_term: str) -> str:
    # TODO: add other search terms possibilities (key, old ID, etc)
    print(search_term)
    client = ndb.Client()
    with client.context() as context:
        one_plaque = Plaque.query().filter(Plaque.title_url == search_term).fetch(1)
        return render_template("one.html", plaques=one_plaque, loginout=_loginout())


@app.route("/plaque")
def plaque_get() -> str:
    client = ndb.Client()
    with client.context() as context:
        plaques = Plaque.query().fetch(1)
        for plaque in plaques:
            print(plaque)
            print(plaque.location)
            print(dir(plaque.location))

        return render_template("one.html", plaques=[plaque], loginout=loginout())


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
