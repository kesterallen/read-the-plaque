# Read the Plaque

Read the Plaque is an application showing basic usage of Google App Engine.
Entities are stored in App Engine (NoSQL) High Replication Datastore (HRD) and
retrieved using a strongly consistent (ancestor) query.

## Products
- [App Engine][1]
## Language
- [Python][2]

## APIs
- [NDB Datastore API][3]
- [Users API][4]

## Dependencies
- [webapp2][5]
- [jinja2][6]
- [Twitter Bootstrap][7]

[1]: https://developers.google.com/appengine
[2]: https://python.org
[3]: https://developers.google.com/appengine/docs/python/ndb/
[4]: https://developers.google.com/appengine/docs/python/users/
[5]: http://webapp-improved.appspot.com/
[6]: http://jinja.pocoo.org/docs/
[7]: http://twitter.github.com/bootstrap/

Update:
    # For python 2.7 -> 3 developement, maintaining two versions:
    #gcloud app deploy --quiet --project=read-the-plaque --version=20240111t092053 && gcloud app services --quiet --project=read-the-plaque set-traffic --splits=20240111t092357=1

     [ $(git branch --show) == "main" ] &&
        ~/.virtualenv/twitter/bin/python scripts/update_geojson_map_file.py &&
        gcloud app deploy --quiet --project=read-the-plaque &&
        echo "" && curl -s https://readtheplaque.com/{flush/silent,counts} && printf "\n\n"
