# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import re
import requests
import urllib
from pprint import pprint
import tempfile
import os
import logging
import time
import sys

site_url = 'http://readtheplaque.com'#10.10.40.65:8080'#readtheplaque.com'
post_url = site_url + '/add'
flush_url = site_url + '/flush'


NAME = 'Dedicated NYC'
BASE_URL = 'http://www.dedicatednyc.com'
TAGS =  ['nyc', 'jack curry']

def get_plaque_data(plaque_url, base_url=BASE_URL):
    get_resp = requests.get(plaque_url)
    soup = BeautifulSoup(get_resp.text, 'html.parser')

    tags_div = soup.find('div', {'class': 'tags'})
    if tags_div:
        tags = [a.text[1:] for a in tags_div.find_all('a')]
        tags.extend(TAGS)
        tags_str = ", ".join(tags)
    else:
        tag_str = TAGS

    img = soup.find('img')
    img_url = img.get('src')

    alt_text = img.get('alt')
    if '(' in alt_text:
        title, location = alt_text.split('(', 1)
        location = location[:-1]
    else:
        title = 'Dedicated NYC Plaque'
        location = alt_text
    title = title.encode('utf-8').strip()
    location = "%s, NYC" % location.encode('utf-8').strip()

    description = '''Plaque via <a href="{3}">Jack Curry's</a> site 
        <a href="{0}">{1}</a>.  Original page <a href="{2}">here</a>.'''.format(
        BASE_URL, NAME, plaque_url, 'http://www.heytheremynameisjack.com/')

    plaque_data = {
        'searchfield': location,
        'plaque_image_url': img_url,
        'plaque_image_file': '',
        'title': title,
        'tags': tags_str,
        'description': description,
    }
    return plaque_data


def 
    log = logging.getLogger()
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    log.addHandler(ch)

    with open('dedicated_nyc.urls') as fh:
        plaque_urls = [p.strip() for p in fh.readlines()]

    #logging.info("urls from file: %s" % plaque_urls)
    logging.info("begin")


    for plaque_url in plaque_urls:
        #print plaque_url
        logging.info(plaque_url)
        plaque_data = get_plaque_data(plaque_url)
        #print plaque_data
        logging.info(plaque_data)

        try:
            post_resp = requests.post(post_url, data=plaque_data)
            if post_resp.status_code != 200 or 'resubmit.' in post_resp.text:
                #print "FAILED %s" % plaque_url
                logging.info("FAILED %s" % plaque_url)
                import ipdb; ipdb.set_trace()
        except Exception as err:
            #print "error (unexpected) %s: cant get %s" % (err, plaque_url)
            logging.info("error (unexpected) %s: cant get %s" % (err, plaque_url))


if __name__ == '__main__':
    main()
