# -*- coding: utf-8 -*-

from attrdict import AttrDict
from collections import defaultdict
import json
from pprint import pprint
import random
import re
import requests
import time
import xml.etree.ElementTree

DEBUG = False

site_url = 'http://localhost:8080' if DEBUG else 'http://readtheplaque.com' 
post_url = site_url + '/add'

def get_metadata(filename):
    """ 
    Get the license from WMFLabs, and the location if it's included in the file.
    """
    if DEBUG:
        return 'Fake License', None, None

    # Licencing API:
    lic_url = "https://tools.wmflabs.org/magnus-toolserver/" + \
        "commonsapi.php?image={}&meta".format(filename)
    response = requests.get(lic_url)

    et = xml.etree.ElementTree.fromstring(response.text.encode('utf8'))

    # Get license from XML tree
    try: 
        #license = [n for n in et.findall('licenses')[0].iter('name')][0].text
        license = et.findall('licenses')[0].iter('name').next().text
    except Exception as err:
        print "no license for", filename, err
        import ipdb; ipdb.set_trace()
        license = None

    # Get lat/lng, if included in image metadata
    try:
        lat = None
        lng = None
        metas = et.find('meta').getchildren()
        for meta in metas:
            if meta.attrib['name'] == 'GPSLatitude':
                lat = meta.text
            if meta.attrib['name'] == 'GPSLongitude':
                lng = meta.text
    except Exception as err:
        print "metas error", err
        import ipdb; ipdb.set_trace()
        print "error", err

    return license, lat, lng

def make_description(inscription, fn, license):
    rights_url = "https://commons.wikimedia.org/wiki/File:{}".format(fn)
    description = """
       <br/>{0} 
       <br/>
       <br/>
           Content courtesy of 
           <a href="https://wmph.github.io/eph-historical-markers-map/">
           Encyclopedia of Philippine Heritage</a>, which is an ongoing program
           of the Wiki Society of the Philippines.
       <br/>
       Wikimedia image page <a href="{1}">here</a>, image license is {2}.
    """.format(inscription.encode('utf8'), rights_url, license)
    # TODO: remove \n characters from this string?
    return description

def plaque_record(plaque):
    return (plaque.markerLabel, plaque.coord)

def main():
    with open ('/media/sf_downloads/query.json') as fh:
        plaques = json.load(fh)

    num_good = 0
    lic_types = defaultdict(int)
    unique_plaques = {} 

    for plaque in plaques:

        plaque = AttrDict(plaque)
        if not DEBUG:
            time.sleep(1)

        is_good = u'coord' in plaque and u'image' in plaque
        if not is_good:
            continue

        # Determine if a plaque is unique it's markerLabel/coord pair, if it
        # isn't, skip it.
        pr = plaque_record(plaque)
        if pr in unique_plaques:
            continue

        try:
            # Get location, description, and image URL from the query output
            # json:
            #
            lng, lat= re.split('\(| |\)', plaque.coord)[1:3]
            inscription = plaque.inscription if 'inscription' in plaque else ''

            image_url = plaque.image
            fn = image_url.split('/')[-1]

            # TODO: Check that this page exists

            (license, lat_meta, lng_meta) = get_metadata(fn)
            if lat_meta:
                lat = lat_meta
            if lng_meta:
                lng = lng_meta

            num_good += 1
        except Exception as err:
            print "meta main error", err

        lic_types[license] += 1
        description = make_description(inscription, fn, license)

        plaque_data = {
            'title': plaque.markerLabel,
            'plaque_image_url': image_url,
            'lat': lat,
            'lng': lng,
            'tags': "philippines, Encyclopedia of Philippine Heritage",
            'description': description,
            'plaque_image_file': '', # skip
        }
        unique_plaques[pr] = plaque_data

    i = 0
    for pr, plaque_data in unique_plaques.items():
        i += 1
        time.sleep(1)
        try:
            if not DEBUG:
                post_resp = requests.post(post_url, data=plaque_data)

                status = "SUCCESS" if post_resp.status_code == 200 else "FAIL"
                print "%s: %5d / %s %s" % (
                    status, i, len(unique_plaques), pr[0])
        except requests.exceptions.ChunkedEncodingError as cee:
            print "CEE error, skipping"
        except Exception as err:
            print "final error", err

    

if __name__ == '__main__':
    main()

