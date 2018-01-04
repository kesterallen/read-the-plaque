# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import re
import requests
import sys

#site_url = 'http://readtheplaque.com'
site_url = 'http://lt-allen-devvm:8080'
post_url = site_url + '/add'
flush_url = site_url + '/flush'

def get_plaque_data(img_url, title):
    plaque_data = {
        'lat': 44.0,
        'lng': 46.0,
        'plaque_image_url': img_url,
        'plaque_image_file': '',
        'title': title,
        'tags': '',
        'description': '',
    }
    return plaque_data


def main():
    plaque_url =  sys.argv[1]
    title =  " ".join(sys.argv[2:])

    plaque_data = get_plaque_data(plaque_url, title)
    print plaque_data

    try:
        post_resp = requests.post(post_url, data=plaque_data)
        if post_resp.status_code != 200 or 'resubmit.' in post_resp.text:
            print "FAILED %s" % plaque_url
        else:
            print "successfully copied %s" % plaque_url
    except Exception as err:
        print "error (unexpected) %s: cant get %s" % (err, plaque_url)

if __name__ == '__main__':
    main()
