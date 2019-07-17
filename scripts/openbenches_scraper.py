"""Import openbenches plaques to RTP"""

import json
import random
import string
import time

from attrdict import AttrDict
import requests

DEBUG = False

MAX_CHAR_LENGTH = 80
URL_PREFIX = 'https://openbenches.org'
CACHE_URL = 'https://arhklxrfen.cloudimg.io/width/1024/webp/openbenches.org/image/{}'
DEF_LICENSE = 'https://creativecommons.org/licenses/by-sa/4.0/'
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
    if len(title) > max_len:
        words = title.split()
        out = ''
        for word in words:
            if len(out) >= max_len:
                break
            out += " " + word
        title = out

    # Remove unicode, etc:
    printable = set(string.printable)
    title = "".join(filter(lambda x: x in printable, title)).strip()

    return title

def _get_title(bench):
    """Exgtract titletitle shorter if it's too long"""
    full_title = bench['properties']['popupContent']
    title = full_title.replace('\r\n', ' ')

    lines = [l for l in title.splitlines() if l]
    if not lines:
        # No description, use a default:
        title = "OpenBenches Plaque"
    elif lines[0].lower() in COMMON_FIRST_LINES:
        # The first line is "In memory of" or something else common, so grab
        # the first two lines:
        title = " ".join(lines[:2])
    else:
        # Uncommon description, use the first line:
        title = lines[0]

    title = _shorten_title_if_needed(title, MAX_CHAR_LENGTH)
    return title, full_title

def bench_to_plaque(bench, user_names):
    """Convert a bench's JSON record to a plaque dict"""

    def _get_desc():
        # Build description, including image metadata: original source,
        # license, and user:
        desc = [
            """ {0.full_title} <br/><br/> This plaque is originally from
            <a href="https://openbenches.org/bench/{0.id}">OpenBenches</a> and
            is imported with their permission <br/> """.format(plaque)
        ]
        if 'importURL' in first_img:
            url = first_img['importURL']
            if url.startswith('https://readtheplaque.com'):
                raise SkipBenchException("Skipping for RTP")
            desc.append('Original location: <a href="{}">here</a>'.format(url))

        # Default license per Terence Eden DM 2019-07-16 to @readtheplaque
        img_license = ' under <a href="{}">CC by SA 4.0</a>'.format(DEF_LICENSE)
        # N.B. British spelling of key
        if 'licence' in first_img:
            img_license = first_img['licence']
        desc.append('The image and text is licensed {}'.format(img_license))

        if 'user' in first_img:
            user_id = first_img['user']
            if user_id in user_names:
                url = 'https://openbenches.org/user/{}'.format(user_id)
                name = user_names[user_id]
                desc.append('<p>Uploaded by <a href="{}">{}</a>'.format(
                    url, name))

        return "<br>".join(desc)

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
        'tags': 'openbenches.org',

        'has_lic': False,
        'has_user': False,
        'has_origin': False,
    })

    plaque.description = _get_desc()
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

def cache_url(img_url):
    """Get the image from the cheaper-bandwidth cache"""
    fname = img_url.split('/')[-1]
    return CACHE_URL.format(fname)

def main():
    """Run the uploader"""
    plaques = load_benches('openbenches.json', 'openbenches.users.json')
    #plaques = random.sample(plaques, 5) # for testing

    for i, plaque in enumerate(plaques):
        try:
            plaque['plaque_image_url'] = cache_url(plaque['plaque_image_url'])
            if not DEBUG:
                submit_url = 'https://readtheplaque.com/add'
                response = requests.post(submit_url, data=plaque)
                response.raise_for_status()

            msg = "Posted {}/{} {}".format(i+1, len(plaques), plaque.title)
            print(msg)
        except requests.exceptions.HTTPError as err:
            print("post for \n{}\n failed,\n {}\n".format(plaque, err))

        if not DEBUG:
            time.sleep(10)

if __name__ == '__main__':
    main()
