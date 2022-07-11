
import dateutil.parser
import datetime
import json
import os
import re
import sys

import requests

GEOJSON_URL = "https://readtheplaque.com/geojson"
ALL_PLAQUES_DATE = "2000-01-01 12:34:56.7"

here_path = os.path.dirname(os.path.abspath(__file__))
#json_filename = os.path.join(here_path, "../static/plaques_updated.json")
geojson_file = os.path.join(here_path, "../static/plaques.geojson")

ALL = False
# UTC_OFFSET = 8 # PST
UTC_OFFSET = 7  # PDT
UTC_TIMEDELTA = datetime.timedelta(hours=UTC_OFFSET)


def print_status(tmpl, num_plaques):
    """Print a status message for num_plaques"""
    suffix = "" if num_plaques == 1 else "s"
    print(tmpl.format(num_plaques, suffix))


def offset_time(last_updated_str):
    """
    This shift into UTC time seems to be necessary. The GAE datastore shows
    the times recorded in the Plaque entities are in "PDT". As of this writing,
    it is Daylight Savings Times.

    Unclear to me why this is required. I think that something in the process
    is assuming dates are in UTC, but I don't see where.

    Anyhow:
        INPUTS:
            A string representing a date that the dateutil parser can consume.
        RETURNS:
            A string representing a date UTC_OFFSET later.

    TODO: This'll break every time change.
    """
    last_updated = dateutil.parser.parse(last_updated_str)
    offset_forward = last_updated + UTC_TIMEDELTA
    return offset_forward.strftime("%Y-%m-%d %H:%M:%S.%f")


def _get_plaques_geojson(updated_on, tmpl):
    updated_on = offset_time(updated_on)
    resp = requests.post(GEOJSON_URL, data={"updated_on": updated_on})
    geojson = json.loads(resp.content.decode("utf-8"))
    print_status(tmpl, len(geojson["features"]))

    if len(geojson["features"]) == 0:
        sys.exit(1)

    return geojson


def get_all_plaques():
    # TODO change URL response content to be in geojson
    return _get_plaques_geojson(ALL_PLAQUES_DATE, "Total: {} plaque{}")


def add_new_plaques():
    # Get the plaques that are already in the geojson file, and extract the
    # update timestamp:
    with open(geojson_file) as json_fh:
        existing_geojson = json.load(json_fh)

    # Get plaques from the site that have been added since the late update:
    geojson = _get_plaques_geojson(existing_geojson["updated_on"], "Found {} new plaque{}.")

    print(len(existing_geojson["features"]))
    # Insert the new plaques descending time order, and update the timestamp
    for plaque in reversed(geojson["features"]):
        existing_geojson["features"].insert(0, plaque)
    print(len(existing_geojson["features"]))
    print(len(geojson["features"]))

    return existing_geojson


def main():
    # TODO
    #plaque_urls = [u for u in sys.argv[1:]] if len(sys.argv) > 1 else None
    #print(plaque_urls)

    # Get existing plaques from json file, add new plaques convert to geojson
    # and write that to the .geojson file
    geojson_plaques = get_all_plaques() if ALL else add_new_plaques()
    geojson_plaques["updated_on"] = str(datetime.datetime.now())

    # Update geojson RTP file
    geojson_str = json.dumps(geojson_plaques)
    with open(geojson_file, "w") as json_fh:
        json_fh.write(geojson_str)


if __name__ == "__main__":
    main()
