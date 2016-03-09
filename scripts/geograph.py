# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import re
import requests
import urllib
import tempfile
import os
import logging
import time
import sys


IS_GG = False

#site_url = 'http://readtheplaque.com'
site_url = 'http://10.10.40.65:8080'
post_url = site_url + '/add'
flush_url = site_url + '/flush'

if IS_GG:
    BASE_URL = 'http://www.geograph.org.gg'
else:
    BASE_URL = 'http://www.geograph.org.uk'

def get_copyright_text(soup):
    cc_msg = soup.find('div', {'class': 'ccmessage'})
    copyright_text = " ".join(
        [c.encode('utf-8').strip() for c in cc_msg.contents])
    copyright_text = copyright_text.replace('="/', '="%s/' % BASE_URL)
    copyright_text = copyright_text.decode('utf-8')
    return copyright_text

def get_plaque_data(plaque_url):
    get_resp = requests.get(plaque_url)
    soup = BeautifulSoup(get_resp.text, 'html.parser')

    # Check that there is a result:
    #
    maincontent = soup.find('div', {'id': 'maincontent'})
    if "is not available" in maincontent.text:
        return None

    img_url = soup.find('div', {'id': 'mainphoto'}).find('img').get('src')

    if IS_GG:
        captions = soup.find_all('div', {'class': 'caption'})
        try:
            title = captions[0].text
        except:
            title = 'Geograph.org.gg Plaque'

        try:
            description = captions[1].text
        except:
            description = ''
    else:
        try:
            title = soup.find('div', {'itemprop': 'name'}).text
        except:
            title = 'Geograph Plaque'
        try:
            description = soup.find('div', {'itemprop': 'description'}).text
        except:
            description = ''

    copyright_text = get_copyright_text(soup)

    description = u'''<p>{0}</p> <p>{1}</p> <p>Submitted via <a href="{2}">Geograph</a></p>'''.format(description, copyright_text, unicode(plaque_url))

    lat = soup.find('abbr', {'class': 'latitude'}).get('title')
    lng = soup.find('abbr', {'class': 'longitude'}).get('title')

    tags = {t.text.lower() for t in soup.find_all('a', {'class': 'taglink'})}
    tags.add('geograph')
    if 'plaque' in tags:
        tags.remove('plaque')
    tags_str = ", ".join(list(tags))

    plaque_data = {
        'lat': lat,
        'lng': lng,
        'plaque_image_url': img_url,
        'plaque_image_file': '',
        'title': title,
        'tags': tags_str,
        'description': description,
    }
    return plaque_data


def main():
    log = logging.getLogger()
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.INFO)
    ch = logging.StreamHandler(sys.stdout)
    fh = logging.FileHandler('geograph.log')
    log.addHandler(ch)
    log.addHandler(fh)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    if IS_GG:
        filename = 'geograph_gg_ids.txt'
    else:
        filename = 'geograph_ids.txt'

    with open(filename) as fh:
        plaque_ids = [l.strip() for l in fh.readlines()]
    plaque_ids.reverse()

    for plaque_id in plaque_ids[:100]:
        plaque_url = "%s/photo/%s" % (BASE_URL, plaque_id)
        plaque_data = get_plaque_data(plaque_url)
        if plaque_data is None:
            logging.info("skipping %s -- data is None" % plaque_url)
            continue

        try:
            post_resp = requests.post(post_url, data=plaque_data)
            if post_resp.status_code != 200 or 'resubmit.' in post_resp.text:
                logging.info("FAILED %s" % plaque_url)
            else:
                logging.info("successfully copied %s" % plaque_url)
        except Exception as err:
            logging.info("error (unexpected) %s: cant get %s" % (err, plaque_url))

        #time.sleep(1)

if __name__ == '__main__':
    main()
