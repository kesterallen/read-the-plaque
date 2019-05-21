
import datetime

import json
import os
import re
import requests
import sys
from pprint import pprint


input_json_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)),
    '../static/plaques_updated.json')
output_json_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)),
    '../static/plaques.geojson')

def make_geojson_feature(plaque):
    geojson_feature = {
        "type": "Feature", 
        "geometry": {
            "type": "Point", 
            "coordinates": [float(plaque['lng']), float(plaque['lat'])], # N.B. lng, then lat
        },
        "properties": {
            "img_url_tiny": plaque["img_url_tiny"],
            "title_page_url": plaque["title_page_url"],
            "title": plaque["title"],
        },
    }
    return geojson_feature

def main():

    with open(input_json_filename) as fh:
        json_data = json.load(fh)

    output = {
        "type": "FeatureCollection",
        "features": [],
    }

    for i, plaque in enumerate(json_data['plaques']):
        geojson_feature = make_geojson_feature(plaque)
        if i < 25:
            geojson_feature["fp"] = True
        output['features'].append(geojson_feature)

    json_str = json.dumps(output)

    with open(output_json_filename, 'w') as fh:
        fh.write(json_str)

if __name__ == '__main__':
    main()
