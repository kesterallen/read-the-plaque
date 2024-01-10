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

@app.route("/plaque")
def plaque_get():
    client = ndb.Client()
    with client.context() as context:
        plaques = Plaque.query().fetch(1)
        for plaque in plaques:
            print(plaque)
    return str(plaque)

@app.route("/counts")
def counts():
    client = ndb.Client()
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
