"""
Main run script
"""

from google.cloud import ndb
from flask import Flask, render_template

from rtp.models import Plaque, FeaturedPlaque


#SET THIS envar TO GET CREDS:
#
#GOOGLE_APPLICATION_CREDENTIALS=/home/kester/Desktop/gae_tutorial/python-docs-samples/appengine/standard_python3/surlyfritter-python3-2ce73610c763.json # pylint: disable=line-too-long

# [START gae_python38_app]

app = Flask(__name__)

@app.route("/")
def display():
    return("hello")

@app.route("/abc")
def display_abc():
    return("hello abc")

@app.route("/abc_about")
def about_get():
    """ templates """
    template_text = render_template("about.html")
    return template_text

@app.route("/plaque/add")
def plaque_add():
    featured = FeaturedPlaque()
    print(featured)
    client = ndb.Client()
    with client.context() as context:
        featured.put()
    print(dir(featured))
    return("featured")

@app.route("/plaque")
def plaque_get():
    print("a")
    client = ndb.Client()
    print("b")
    with client.context() as context:
        print("c")
        plaques = Plaque.query().fetch(5)

        for plaque in plaques:
            print(plaque)
        #print("d")
        #plaque = Plaque.query().filter(Plaque.key == featured.plaque).get()
        print("e")
        #print(plaque)
    return "foo"

@app.route("/counts")
def counts():
    print("a")
    client = ndb.Client()
    print("b")
    with client.context() as context:
        query = Plaque.query()
        num_plaques = query.count()
        num_pending = query.filter(Plaque.approved == False).count()
        return f"{num_plaques} plaques, {num_pending} pending"


if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END gae_python38_app]
