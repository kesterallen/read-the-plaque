"""Import openbenches plaques to RTP"""

import json
import time

import requests

DEBUG = True
URL_PREFIX = 'https://openbenches.org'

def bench_to_plaque(bench):
    """Convert a bench's JSON record to a plaque dict"""

    # If there isn't an image, bail out:
    if bench['properties']['media'] is None:
        return None

    title = bench['properties']['popupContent']
    coords = bench['geometry']['coordinates']
    first_img = bench['properties']['media'][0]

    plaque = {
        'title': title,
        'lng': coords[0],
        'lat': coords[1],
        'plaque_img_url': URL_PREFIX + first_img['URL'],
        'tags': 'openbenches.org',
    }

    # Image metadata: original source, license, user:
    extras = {}
    if 'importURL' in first_img:
        url = first_img['importURL']
        extras['orig'] = 'Original location: <a href="{}">here</a>'.format(url)
    if 'license' in first_img:
        license = first_img['license']
        extras['license'] = 'The image and is licensed {}'.format(license)
    if 'user' in first_img:
        user = first_img['user']
        url = 'https://openbenches.org/user/{}'.format(user)
        extras['user'] = 'Uploader\'s <a href="{}">OpenBenches page</a>.'.format(url)
    desc = """
        {}
        <br/><br/>
        This plaque is originally from 
        <a href="https://openbenches.org">OpenBenches</a> and is imported with
        their permission
        <br/>{}""".format(title, "<br>".join(extras.values()))

    # TODO: slugify title?
    # TODO: Truncate title and add description for long titles

    plaque['description'] = desc
    return plaque

def main():
    """Run the uploader"""
    if DEBUG:
        submit_url = 'http://localhost:8080/add'
    else:
        submit_url = 'https://readtheplaque.com/add'

    with open('openbenches.json') as json_fh:
        data = json.load(json_fh)
        plaques = []
        for bench in data['features']:
            plaque = bench_to_plaque(bench)
            if plaque:
                plaques.append(plaque)

    for i, plaque in enumerate(plaques):
        try:
            if not DEBUG:
                response = requests.post(submit_url, data=plaque)
                response.raise_for_status()
            print("Posted {}/{} {}".format(i+1, len(plaques), plaque))
        except requests.exceptions.HTTPError as err:
            print("post for {} failed, {}".format(plaque, err))
        if not DEBUG:
            time.sleep(10)

if __name__ == '__main__':
    main()
