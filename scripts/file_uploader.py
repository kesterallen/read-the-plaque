"""Script to upload exif-tagged images as Read the Plaque plaques."""

import sys
import time

from attrdict import AttrDict
from PIL import Image
import requests

DEBUG = False

# Values in these constants was extracted from:
# from PIL.ExifTags import TAGS, GPSTAGS
# img.getexif().get_ifd(GPS_INFO_TAG)
# >>> {1: 'N', 2: (37.0, 47.0, 12.85), 3: 'W', 4: (122.0, 15.0, 19.94), 5: b'\x00', 6: 4.120659187112152, 12: 'K', 13: 0.0, 16: 'T', 17: 320.42755102040815, 23: 'T', 24: 320.42755102040815, 29: '2022:01:03', 31: 4.999077948790695}

GPS_INFO_TAG = 34853 # "GPSInfo"
LAT_REF = 1 # e.g. "N"
LAT = 2 # e.g.  (37.0, 47.0, 12.85)
LNG_REF = 3 # e.g. W
LNG = 4 # e.g. (122.0, 15.0, 19.94)

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
        """Extract the location from the image tags, using exiftool"""

        def _decimal_pos_from_exif(exif, ref):
            degs, mins, secs = [float(exif[i]) for i in range(3)]
            decimal = degs + mins / 60.0 + secs / 3600.0
            if ref in ('S', 'W'):
                decimal *= -1
            return decimal

        try:
            with Image.open(self.fname) as img:
                gps = img.getexif().get_ifd(GPS_INFO_TAG)
                self.lat = _decimal_pos_from_exif(gps[LAT], gps[LAT_REF])
                self.lng = _decimal_pos_from_exif(gps[LNG], gps[LNG_REF])
        except (TypeError, KeyError) as err:
            print("Error in GPS read, using defaults,", err, type(err), self.fname)
            self.lat = self.DEFAULT_LAT
            self.lng = self.DEFAULT_LNG

    def __repr__(self):
        return "{0.fname} ({0.lat:.5f}, {0.lng:.5f})".format(self)

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

    succeeded = []
    failed = []

    for i, plaque in enumerate(plaques):
        print("posting {} / {} {}".format(i+1, len(plaques), plaque))
        try:
            if not DEBUG:
                plaque.submit()
            succeeded.append(plaque.fname)
        except requests.exceptions.HTTPError:
            failed.append(plaque.fname)

    if succeeded:
        print("\nUploaded successfully:\n\t{}".format("\n\t".join(succeeded)))
    if failed:
        print("\n\nFailed:\n\t{}".format("\n\t".join(failed)))

if __name__ == '__main__':
    main(sys.argv[1:])
