"""Import openbenches plaques to RTP"""

import json
import random
import string
import time

from attrdict import AttrDict
import requests

DEBUG = True
MAX_CHAR_LENGTH = 60
URL_PREFIX = 'https://openbenches.org'
COMMON_FIRST_LINES = set([
    'donated by',
    'donated in loving memory of',
    'in loving memory',
    'in loving memory of',
    'in memoriam',
    'in memory',
    'in memory of',
    'in remembrance of',
    'loving memory of',
    'presented by',
    'presented to',
    'to the memory of',
])


class NoImageException(Exception):
    """Exception to throw for no-image benches"""

class SkipBenchException(Exception):
    """Exception to throw for benches to skip (e.g. ReadThePlaque)"""


def _shorten_title_if_needed(title, max_len):
    """Make title shorter if it's too long"""
    if len(title) < max_len:
        out = title
    else:
        words = title.split()
        out = ''
        for word in words:
            out += " " + word
            if len(out) >= max_len:
                break
    return out

def _get_title(bench):
    """Exgtract titletitle shorter if it's too long"""
    full_title = bench['properties']['popupContent']
    title = full_title.replace('\r\n', ' ')

    lines = [l for l in title.splitlines() if l]
    if not lines:
        # No description
        title = "OpenBenches Plaque"
    elif len(title) < MAX_CHAR_LENGTH:
        # Short description, use entire title
        pass
    elif lines[0].lower() in COMMON_FIRST_LINES:
        # Long description, but the first line is "In memory of" or
        # something else common, so append the second line to it
        title = " ".join(lines[:2])
    else:
        # Long, uncommon description, grab the first line, shorten if
        # necessary:
        title = _shorten_title_if_needed(lines[0], MAX_CHAR_LENGTH)

    # Clean title of unicode, etc
    printable = set(string.printable)
    title = "".join(filter(lambda x: x in printable, title)).strip()
    return title, full_title

def bench_to_plaque(bench, user_names):
    """Convert a bench's JSON record to a plaque dict"""

    title, full_title = _get_title(bench)
    # If there isn't an image, bail out:
    if bench['properties']['media'] is None:
        raise NoImageException("bench {} has no image".format(title))

    coords = bench['geometry']['coordinates']
    first_img = bench['properties']['media'][0]
    plaque = AttrDict({
        'id': bench['id'],
        'title': title,
        'full_title': full_title,
        'lng': coords[0],
        'lat': coords[1],
        'plaque_image_url': URL_PREFIX + first_img['URL'],
        #('http://lh3.googleusercontent.com/5tJoII-uCRkJJAdh7fKeGw6Z_RGT78PGCrxauOlnWxCnD37XLiLAtbnblQdSMC5ZTVOhRmr0B7VNbJbMlilHxs4npuMX9Q=s4096'),
        'tags': 'openbenches.org',
    })

    # Image metadata: original source, license, user:
    desc = [
        """
        {0.full_title}
        <br/><br/>
        This plaque is originally from
        <a href="https://openbenches.org/bench/{0.id}">OpenBenches</a> and is
        imported with their permission
        <br/>
        """.format(plaque)
    ]
    if 'importURL' in first_img:
        url = first_img['importURL']
        if url.startswith('https://readtheplaque.com'):
            raise SkipBenchException("Skipping for RTP")
        desc.append('Original location: <a href="{}">here</a>'.format(url))
    if 'license' in first_img:
        img_license = first_img['license']
        desc.append('The image and is licensed {}'.format(img_license))
        #TODO: default license?
    if 'user' in first_img:
        user_id = first_img['user']
        if user_id in user_names:
            url = 'https://openbenches.org/user/{}'.format(user_id)
            name = user_names[user_id]
            desc.append('<p>Uploaded by <a href="{}">{}</a>'.format(url, name))

    plaque.description = "<br>".join(desc)
    return plaque

def load_benches(fname, users_fname):
    """Convert bench data to a list of plaques"""

    # Load user ID -> name dictionary:
    user_names = {}
    with open(users_fname) as users_fh:
        data = json.load(users_fh)
        for user_id, user_data in data.items():
            name = user_data['name']
            if name:
                user_names[int(user_id)] = name

    # Load bench data, add user name:
    with open(fname) as json_fh:
        data = json.load(json_fh)
        plaques = []
        for bench in data['features']:
            try:
                plaque = bench_to_plaque(bench, user_names)
                if plaque:
                    plaques.append(plaque)
            except (SkipBenchException, NoImageException):
                pass

    return plaques

def main():
    """Run the uploader"""
    host = 'http://localhost:8080' if DEBUG else 'https://readtheplaque.com'
    submit_url = '{}/add'.format(host)

    plaques = load_benches('openbenches.json', 'openbenches.users.json')
    if DEBUG:
        plaques = [random.choice(plaques) for i in range(5)]

    for i, plaque in enumerate(plaques):
        try:
            response = requests.post(submit_url, data=plaque)
            response.raise_for_status()
            msg = "Posted {}/{} {}".format(i+1, len(plaques), plaque.title)
            print(msg)
        except requests.exceptions.HTTPError as err:
            print("post for {} failed, {}".format(plaque, err))
        time.sleep(10)

if __name__ == '__main__':
    main()
