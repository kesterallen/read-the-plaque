
from attrdict import AttrDict
import csv
from pprint import pprint
import os
import random
import requests
import string
import time

TAGS = 'Michigan, Michigan History Center'

site_url = 'http://readtheplaque.com'
post_url = site_url + '/add'

img_url_base = 'https://www.midnr.com/publications/pdfs/arcgisonline/storymaps/mhc_historical_markers/images/'
csv_file = '/media/sf_downloads/Michigan_Historical_Markers.csv'


class Plaque(object):
    def __init__(self, title, img_url, lat, lng, desc):
        self.title = title
        self.image_url = "%s%s" % (img_url_base, img_url)
        self.lat = lat
        self.lng = lng
        self.description = desc + '<p>Plaque via <a href="http://www.michigan.gov/mhc/">Michigan History Center</a>'

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
    plaques = []
    with open(csv_file) as csvfh:
        reader = csv.DictReader(csvfh)
        for marker in reader:
            marker = AttrDict(marker)
            if marker.Photo_Name:

                desc = marker.Marker_Desc_Front + marker.Marker_Desc_Back
                if int(marker.Photo_Count) > 1:
                    photos = marker.Photo_Name.split(";")
                    photo = photos[0]
                    for p in photos[1:]:
                        desc += '<img class="img-responsive" src="{}{}"/>'.format(img_url_base, p)
                else:
                    photo = marker.Photo_Name

                plaque = Plaque(
                    marker.Marker_Name,
                    photo,
                    marker.Latitude,
                    marker.Longitude,
                    desc)
                plaques.append(plaque)
        
    for i, plaque in enumerate(plaques):
        #post_resp = requests.post(post_url, data=plaque.data)
        print "uploading %s %s" % (i+1, plaque.title)
        time.sleep(10)

if __name__ == '__main__':
    main()
