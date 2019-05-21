"""Script to upload exif-tagged images as Read the Plaque plaques."""

import subprocess
import sys
import time
import requests

DEBUG = False

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
        submit_url = 'http://readtheplaque.com/add'

    def __init__(self, fname, title='', description=''):
        """ Lat/Lng is extracted from the exif tags of the image file.  """
        self.fname = fname
        self.title = title
        self.description = description
        self._set_exif_lat_lng()

    def submit(self):
        """ Submit the plaque with a POST request to Read The Plaque """
        with open(self.fname, 'rb') as plaque_image_fh:
            files = {'plaque_image_file': plaque_image_fh}
            data = {
                'lat': self.lat,
                'lng': self.lng,
                'title': self.title,
                'description': self.description,
            }
            response = requests.post(Plaque.submit_url, files=files, data=data)
            response.raise_for_status()

    def _set_exif_lat_lng(self):
        """ Extract the location info from the image tags, using exiftool """
        cmd_tmpl = "exiftool -m -c '%.10f' -p '$gpslatitude $gpslongitude' {}"
        cmd = cmd_tmpl.format(self.fname)
        if DEBUG:
            print(cmd)
        try:
            latlng = subprocess.check_output(cmd, shell=True)
            lat, lat_dir, lng, lng_dir = latlng.split()

            self.lat = float(lat)
            if lat_dir == b'S': # b-string because latlng appears to be a "<class 'bytes'>" object
                self.lat *= -1.0

            self.lng = float(lng)
            if lng_dir == b'W': # b-string because latlng appears to be a "<class 'bytes'>" object
                self.lng *= -1.0

        except (subprocess.CalledProcessError, ValueError):
            print("Can't get location of {.fname}, using default".format(self))
            self.lat = Plaque.DEFAULT_LAT
            self.lng = Plaque.DEFAULT_LNG

    def __repr__(self):
        return "{0.fname} ({0.lat}, {0.lng})".format(self)

def main(img_fnames):
    """
    For a given list of images, make plaque instances and submit them to Read
    The Plaque.
    """

    plaques = []
    for fname in img_fnames:
        plaque = Plaque(fname)
        plaques.append(plaque)

    for i, plaque in enumerate(plaques):
        try:
            if not DEBUG:
                plaque.submit()
            print("uploaded {}/{} {}".format(i+1, len(plaques), plaque))
        except requests.exceptions.HTTPError as err:
            print("upload for {} failed, {}".format(plaque, err))
        if not DEBUG:
            time.sleep(10)

if __name__ == '__main__':
    main(sys.argv[1:])
