
import datetime
import json
import os
import re
import sys

import requests

URL_TMPL = "https://readtheplaque.com/{}"
URL_ALL = URL_TMPL.format("alljp")
URL_UPDATE = URL_TMPL.format("updatejp")

here_path = os.path.dirname(os.path.abspath(__file__))
json_filename = os.path.join(here_path, "../static/plaques_updated.json")
json_out = os.path.join(here_path, "../static/plaques.geojson")

ALL = False
#UTC_OFFSET = 8 # PST
UTC_OFFSET = 7 # PDT

def offset_time(last_updated_str):
    """
    This shift into UTC time seems to be necessary. The GAE datastore shows
    the times recorded in the Plaque entities are in "PDT". As of this writing,
    it is Daylight Savings Times.

    Unclear to me why this is required. I think that something in the process
    is assuming dates are in UTC, but I don't see where.

    Anyhow:
        INPUTS:
            A string representing a date, prefereably in %Y-%m-%d %H:%M:%S.%f
            format, but any string that the datetime constructor will consume
            after being split on hyphen/space/colon/period will work.
        RETURNS:
            A string representing a date UTC_OFFSET later.

    TODO: This'll break every time change.
    """
    last_updated_parts = [int(i) for i in re.split("[- :.]", last_updated_str)]
    last_updated = datetime.datetime(*last_updated_parts)
    timedelta = datetime.timedelta(hours=UTC_OFFSET)
    offset_forward = last_updated + timedelta
    offset_forward_str = offset_forward.strftime("%Y-%m-%d %H:%M:%S.%f")
    return offset_forward_str

def plaque_to_geojson_feature(plaque):
    """ Convert RTP's plaque representation to geojson """
    geojson_feature = {
        "type": "Feature",
        "geometry": dict(
            type="Point",
            coordinates=[float(plaque["lng"]), float(plaque["lat"])]),
        "properties": dict(
            img_url_tiny=plaque["img_url_tiny"],
            title_page_url=plaque["title_page_url"],
            title=plaque["title"]),
    }
    return geojson_feature

def main():
    now = str(datetime.datetime.now())

    if ALL:
        resp = requests.get(URL_ALL)
        all_plaques = json.loads(resp.content)
        num_plaques = len(all_plaques)
        suffix = "" if num_plaques == 1 else "s"
        print("Total: {} plaque{}".format(num_plaques, suffix))

        json_data = dict(plaques=all_plaques, updated_on= now)
    else:
        with open(json_filename) as json_fh:
            json_data = json.load(json_fh)

        updated_on = offset_time(json_data["updated_on"])

        resp = requests.post(URL_UPDATE, data=dict(updated_on=updated_on))

        new_plaques = json.loads(resp.content.decode("utf-8"))
        num_plaques = len(new_plaques)
        suffix = "" if num_plaques == 1 else "s"
        print("Found {} new plaque{}.".format(num_plaques, suffix))
        if len(new_plaques) == 0:
            sys.exit(1)

        # Insert in descending time sort, and update the timestamp
        for plaque in reversed(new_plaques):
            json_data["plaques"].insert(0, plaque)
        json_data["updated_on"] = now

    # Write RTP representation to file
    with open(json_filename, "w") as json_fh:
        json_str = json.dumps(json_data)
        json_fh.write(json_str)

    # Convert to geojson and write that to file
    features = [plaque_to_geojson_feature(p) for p in json_data["plaques"]]
    geojson = dict(type="FeatureCollection", features=features)
    with open(json_out, "w") as json_fh:
        json_str = json.dumps(geojson)
        json_fh.write(json_str)

if __name__ == "__main__":
    main()
