
import os
import random
import requests
import string
import time

TAGS = 'KSHS, Kansas'

site_url = 'http://readtheplaque.com'
#site_url = 'http://localhost:8080'
post_url = site_url + '/add'

kshs_url = 'https://www.kshs.org'
html_file = 'scripts/kshs_page.html'


class Plaque(object):
    def __init__(self, title, img_url, loc, desc):
        self.title = title
        self.image_url = "%s%s" % (kshs_url, img_url)
        self.lat = loc.split(',')[0]
        self.lng = loc.split(',')[1]
        self.description = desc + '<p>Plaque via <a href="http://www.kshs.org/">Kansas Historical Society</a>, and is used with their permission. <a href="https://www.kshs.org/p/kansas-historical-markers/14999">Full page</a>'

    @property
    def data(self):
        plaque_data = {
            'lat': self.lat,
            'lng': self.lng,
            'plaque_image_url': self.image_url,
            'plaque_image_file': '',
            'title': self.title,
            'tags': TAGS,
            'description': self.description,
        }
        return plaque_data


def main():
    with open(html_file) as fh:
        html_text = fh.read()

    raw_plaques = html_text.split('PLAQUE')
    
    incs = set(string.ascii_uppercase)
    for i in range(10):
        incs.add(str(i))
    incs.add(' ')
    incs.add('-')

    plaques = []
    for raw_plaque in raw_plaques:
        rows = [r for r in raw_plaque.split('\n') if r]
        title_row = rows.pop(0)
        title = "".join([c for c in title_row if c in incs]).strip()
        img_url = rows.pop(0)
        loc = rows.pop()
        rows.insert(0, title)
        rows.insert(0, '<br/>')
        desc = " ".join(rows)

        plaque = Plaque(title, img_url, loc, desc)
        plaques.append(plaque)

    for i, plaque in enumerate(plaques[61:]):
        post_resp = requests.post(post_url, data=plaque.data)
        print "uploading %s %s" % (i, plaque.title)
        time.sleep(10)

if __name__ == '__main__':
    main()
