# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import re
import requests
import urllib
import tempfile
import os
import time
import sys

site_url = 'http://readtheplaque.com'
post_url = site_url + '/add'
flush_url = site_url + '/flush'


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
    'ontario': re.compile('photo'),
    'toronto': re.compile('plaque'),
}

def get_plaque_data(plaque_url):

    location = 'ontario' if plaque_url.startswith(
                   'http://www.ontarioplaques') else 'toronto'
    base_url = plaque_url[:30]

    get_resp = requests.get(plaque_url)
    soup = BeautifulSoup(get_resp.text, 'html.parser')

    coords_tag = soup.find('p', {'class': 'plaquecoordinates'})
    if coords_tag is None:
        raise ValueError('no coords for %s' % plaque_url)

    text_tag = soup.find('p', {'class': description_tag[location]})

    title = soup.find('h1').get_text()
    coords_text = coords_tag.get_text().split()
    if location == 'ontario':
        lat = float(coords_text[2]) + float(coords_text[3]) / 60.0
        lng = -1.0 * (float(coords_text[5]) + float(coords_text[6]) / 60.0)
    else:
        lat = float(coords_text[1].replace(',', ''))
        lng = float(coords_text[2].replace(',', ''))

    description = '''{0}<br>Plaque via Alan L. Brown's site 
        <a href="{1}">{3}</a>.  Full page <a href="{2}">here</a>.'''.format(
            text_tag, base_url, plaque_url, name[location])

    img_tags = soup.find_all('img', {'class': img_plaque_re[location]})
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
    return plaque_data

def main():
    with open('alan_brown_urls.txt') as fh:
        plaque_urls = [p.strip() for p in fh.readlines()]

    for ip, plaque_url in enumerate(plaque_urls):
        try:
            plaque_data = get_plaque_data(plaque_url)
            post_resp = requests.post(post_url, data=plaque_data)
            if post_resp.status_code != 200:
                print "FAIL FAIL FAIL %s %s" % (ip, plaque_url)
            else:
                print ip, plaque_url
        except ValueError as ve: 
            print "error %s: cant get %s" % (ve, plaque_url)
        except Exception as err:
            print "error (unexpected) %s: cant get %s" % (err, plaque_url)
        time.sleep(120)

if __name__ == '__main__':
    main()
