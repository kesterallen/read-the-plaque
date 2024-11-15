"""Update the Big Map geojson file"""

import datetime
import json
import os
import sys

import dateutil.parser
from pytz import timezone
import requests

GEOJSON_URL = "https://readtheplaque.com/geojson"
ALL_PLAQUES_DATE = "2000-01-01 12:34:56.7"  # way before the first plaque was added

HERE_PATH = os.path.dirname(os.path.abspath(__file__))
GEOJSON_FILE = os.path.join(HERE_PATH, "../static/plaques.geojson")

ALL = False


def print_status(tmpl, num_plaques, date):
    """Print a status message for num_plaques"""
    suffix = "" if num_plaques == 1 else "s"

    update_count = len(sys.argv) - 1
    suffix2 = "" if update_count == 1 else "s"
    txt = f"Updated {update_count} location{suffix2} in plaques.geojson."


    date = datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S.%f").strftime("%d-%b %H:%M")
    print(tmpl.format(num_plaques, suffix, date), txt)


def time_to_utc(last_updated_str):
    """
    This shift into UTC time seems to be necessary. The GAE datastore shows
    (https://console.cloud.google.com/datastore/entities;kind=Plaque;ns=__$DEFAULT$__/query/kind?project=read-the-plaque)
    the times recorded in the Plaque entities are either PST or PDT.

    The Plaque.created_after method in Models.py (line 284) that GEOJSON_URL
    exercises must be assumning incoming dates are in is assuming dates are in
    UTC, but I'm not sure why.

    INPUTS:
        A string representing a date that the dateutil parser can consume.
    RETURNS:
        A string representing a date utc_offset later than the input.

    Ref: https://stackoverflow.com/questions/17173298/is-a-specific-timezone-using-dst-right-now
    """
    zone = "America/Los_Angeles"
    is_dst = datetime.datetime.now(tz=timezone(zone)).dst()
    utc_offset = 7 if is_dst else 8  # PST vs PDT

    last_updated = dateutil.parser.parse(last_updated_str)
    utc_time = last_updated + datetime.timedelta(hours=utc_offset)
    return utc_time.strftime("%Y-%m-%d %H:%M:%S.%f")


def _get_plaques_geojson(updated_on, tmpl):
    """
    Get the geojson representation of plaques published since updated_on.
    """
    updated_on_utc = time_to_utc(updated_on)
    resp = requests.post(GEOJSON_URL, data={"updated_on": updated_on_utc})
    geojson = json.loads(resp.content.decode("utf-8"))

    print_status(tmpl, len(geojson["features"]), updated_on)
    if len(geojson["features"]) == 0:
        sys.exit(1)

    return geojson


def get_all_plaques():
    """
    Get every published plaque from the site to make a new GEOJSON file.
    """
    return _get_plaques_geojson(ALL_PLAQUES_DATE, "Total: {} plaque{} since {}.")


def add_new_plaques():
    """
    Add new plaques (published since updated_on) to the GEOJSON file.
    """

    # Get the plaques that are already in the geojson file, and extract the
    # update timestamp:
    with open(GEOJSON_FILE, encoding="utf8") as json_fh:
        existing_geojson = json.load(json_fh)

    # Get plaques from the site that have been added since the last update:
    updated_on = existing_geojson["updated_on"]
    geojson = _get_plaques_geojson(updated_on, "Found {} new plaque{} since {}.")

    # Insert the new plaques descending time order, and update the timestamp
    for plaque in reversed(geojson["features"]):
        existing_geojson["features"].insert(0, plaque)

    return existing_geojson


def fix_json_location(url_suffix):
    """
    Update the Big Map entry for a plaque in the static/plaques.geojson file
    with the location data from the website.
    """
    url = f"{GEOJSON_URL}/{url_suffix}"
    resp = requests.get(url)
    if resp.status_code != 200:
        raise requests.exceptions.RequestException(f"no plaque at {url}")

    geojson = resp.json()
    lng, lat = geojson["geometry"]["coordinates"]

    with open(GEOJSON_FILE, encoding="utf8") as json_fh:
        existing_geojson = json.load(json_fh)

    for plaque in existing_geojson["features"]:
        if f"/plaque/{url}" == plaque["properties"]["title_page_url"]:
            old = plaque["geometry"]["coordinates"]
            plaque["geometry"]["coordinates"] = [lng, lat]
            print(f"updated {url} to from {old} to {lng}, {lat}")

    geojson_str = json.dumps(existing_geojson)
    with open(GEOJSON_FILE, "w", encoding="utf8") as json_fh:
        json_fh.write(geojson_str)


def main():
    """Update the Big Map geojson file"""

    # Update a plaques entry in the Big Map static/plaques.geojson file for one
    # or more plaques, given as URLs (e.g. four-citizens-killed-by-british-soldiers
    # for the plaque at readtheplaque.com/plaque/four-citizens-killed-by-british-soldiers),
    # if any URLs are specified on the command line.
    #
    # If not URLs are specified on the command line, skip this.
    #
    if len(sys.argv) > 1:
        for fix_json_location_url in sys.argv[1:]:
            try:
                fix_json_location(fix_json_location_url)
            except requests.exceptions.RequestException as err:
                print(err)

    # Get the list of existing plaques from json file, and add new plaques:
    geojson_plaques = get_all_plaques() if ALL else add_new_plaques()

    # Write out the updated geojson file with a new timestamp:
    geojson_plaques["updated_on"] = str(datetime.datetime.now())
    geojson_str = json.dumps(geojson_plaques)
    with open(GEOJSON_FILE, "w", encoding="utf8") as json_fh:
        json_fh.write(geojson_str)


if __name__ == "__main__":
    main()
