# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import re
import requests
import urllib
from pprint import pprint
import tempfile
import os
import time
import sys

site_url = 'http://readtheplaque.com'
post_url = site_url + '/add'
flush_url = site_url + '/flush'


is_ontario = True 
if is_ontario:
    NAME = 'Ontario Plaques'
    BASE_URL = 'http://www.ontarioplaques.com/'
    TAGS =  'ontario, alan brown',
    DESCRIPTION_TAG = 'text_navy1_16a'
    img_plaque_re = re.compile('photo')
else:
    NAME = 'Toronto Plaques'
    BASE_URL = 'http://www.torontoplaques.com/'
    TAGS =  'toronto, ontario, alan brown',
    DESCRIPTION_TAG = 'plaquetext'
    img_plaque_re = re.compile('plaque')

name = {
    'ontario': 'Ontario Plaques',
    'toronto': 'Toronto Plaques',
}
description_tag = {
    'ontario': 'text_navy1_16a',
    'toronto': 'plaquetext',
}
tags = {
    'ontario': 'ontario, alan brown',
    'toronto': 'toronto, ontario, alan brown',
}
img_plaque_re = {
    'ontario': img_plaque_re = re.compile('photo'),
    'toronto': img_plaque_re = re.compile('plaque'),
}

def get_index_pages(base_url=BASE_URL):
    """
    Get the URLS to the A, B, C, etc. pages that list the plaques
    alphabetically.
    """
    index_url = "{0}Index_Small/".format(base_url)
    get_resp = requests.get(index_url)
    soup = BeautifulSoup(get_resp.text, 'html.parser')
    page_urls_rel = [link.get('href') for link in soup.find_all('a')][5:]
    page_urls = ["%sIndex_Small/%s" % (base_url, url) for url in page_urls_rel]
    return page_urls

def get_plaque_urls(index_page_url, base_url=BASE_URL):
    get_resp = requests.get(index_page_url)
    soup = BeautifulSoup(get_resp.text, 'html.parser')
    links = soup.find('table').find_all('a')
    page_urls_rel = [link.get('href')[3:] for link in links]
    page_urls = {"{0}{1}".format(base_url, u) for u in page_urls_rel}
    return list(page_urls)

def get_plaque_data(plaque_url, base_url=BASE_URL):
    get_resp = requests.get(plaque_url)
    soup = BeautifulSoup(get_resp.text, 'html.parser')

    coords_tag = soup.find('p', {'class': 'plaquecoordinates'})
    text_tag = soup.find('p', {'class': DESCRIPTION_TAG}) 

    title = soup.find('h1').get_text()
    coords_text = coords_tag.get_text().split(' ')
    if is_ontario:
        lat = float(coords_text[2]) + float(coords_text[3]) / 60.0
        lng = -1.0 * (float(coords_text[5]) + float(coords_text[6]) / 60.0)
    else:
        lat = float(coords_text[1])
        lng = float(coords_text[3])

    description = '''{0}<br>Plaque via Alan L. Brown's site 
        <a href="{1}">{3}</a>. 
        Full page <a href="{2}">here</a>.'''.format(
            text_tag, base_url, plaque_url, NAME)

    img_tags = soup.find_all('img', {'class': img_plaque_re})
    img_tag = img_tags[0]
    img_url = os.path.join(base_url, img_tag.get('src')[3:])

    plaque_data = {
        'lat': lat,
        'lng': lng,
        'plaque_image_url': img_url,
        'plaque_image_file': '',
        'title': title,
        'tags': 'toronto, ontario, alan brown',
        'description': description,
    }
    pprint(plaque_data)
    return plaque_data

def main():
    ip = 0
    index_page_urls = get_index_pages(base_url=BASE_URL)
    for index_page_url in index_page_urls:
        time.sleep(0.5)
        for plaque_url in get_plaque_urls(index_page_url):
            print plaque_url
            #ip += 1
            #plaque_data = get_plaque_data(plaque_url)
            #if ip % 10 == 0:
                #import ipdb; ipdb.set_trace()


    #        post_resp = requests.post(post_url, data=plaque_data)
    #        if post_resp.status_code != 200:
    #            print "FAIL FAIL FAIL",
    #            print plaque_data
    #            print post_resp
    #
    #flush_resp = requests.get(flush_url)
    #print 'Flush:', flush_resp

if __name__ == '__main__':
    main()
