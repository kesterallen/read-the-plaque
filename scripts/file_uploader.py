"""Script to upload exif-tagged images as Read the Plaque plaques."""

import sys
import time
import requests

from PIL import Image

DEBUG = False

# Values in these constants was extracted from:
# from PIL.ExifTags import TAGS, GPSTAGS
GPS_INFO_TAG = 34853 # "GPSInfo"
LAT_REF = 1 # e.g. "N"
LAT = 2 # e.g. ((37, 1), (50, 1), (2381, 100))
LNG_REF = 3 # e.g. W
LNG = 4 # e.g. ((122, 1), (17, 1), (2834, 100))

class Plaque:
    """
    Class to encapsulate the image/location of the plaque, and provide a method
    to submit the object to Read the Plaque.
    """
    DEFAULT_LAT = 44.0
    DEFAULT_LNG = 46.0

    if DEBUG:
        submit_url = 'http://localhost:8080/add'
    else:
        submit_url = 'https://readtheplaque.com/add'

    def __init__(self, fname, title='', description=''):
        """Lat/Lng is extracted from the exif tags of the image file."""
        self.fname = fname
        self.title = title
        self.description = description
        self._set_exif_lat_lng()

    def submit(self):
        """Submit the plaque with a POST request to Read The Plaque"""
        with open(self.fname, 'rb') as plaque_image_fh:
            files = {'plaque_image_file': plaque_image_fh}
            data = {
                'lat': self.lat,
                'lng': self.lng,
                'title': self.title,
                'description': self.description,
                #'tags': 'bench',
            }
            response = requests.post(Plaque.submit_url, files=files, data=data)
            response.raise_for_status()

    def _set_exif_lat_lng(self):
        """Extract the location info from the image tags, using exiftool"""

        def _degs_min_secs_from_exif(exif):
            degs, mins, secs_times_100 = [float(exif[i][0]) for i in range(3)]
            secs = secs_times_100 / 100.0 # ??? not sure where this comes from
            return degs, mins, secs

        def _decimal_pos_from_exif(exif, ref):
            degs, mins, secs = _degs_min_secs_from_exif(exif)
            decimal = degs + mins / 60.0 + secs / 3600.0
            if ref in ('S', 'W'):
                decimal *= -1
            return decimal

        try:
            with Image.open(self.fname) as img:
                exif = img._getexif()
                info = exif[GPS_INFO_TAG]
                self.lat = _decimal_pos_from_exif(info[LAT], info[LAT_REF])
                self.lng = _decimal_pos_from_exif(info[LNG], info[LNG_REF])
        except TypeError as err:
            print("typeerr", err)
            self.lat = self.DEFAULT_LAT
            self.lng = self.DEFAULT_LNG

    def __repr__(self):
        return "{0.fname} ({0.lat}, {0.lng})".format(self)

def main(img_fnames):
    """
    For a given list of images, make plaque instances and submit them to Read
    The Plaque.
    """
    plaques = []
    print("Loading {} images".format(len(img_fnames)))
    for fname in img_fnames:
        plaque = Plaque(fname)
        plaques.append(plaque)
    print("Loading complete")

    for i, plaque in enumerate(plaques):
        try:
            if not DEBUG:
                plaque.submit()
            print("Posted {}/{} {}".format(i+1, len(plaques), plaque))
        except requests.exceptions.HTTPError as err:
            print("post for {} failed, {}".format(plaque, err))
        if not DEBUG:
            time.sleep(10)

if __name__ == '__main__':
    main(sys.argv[1:])
