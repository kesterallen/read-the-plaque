"""Script to upload exif-tagged images as Read the Plaque plaques."""

import datetime
import sys
import time

from PIL import Image
import requests

DEBUG = False
GPS_INFO_TAG = 34853  # "GPSInfo"

# Values in these constants was extracted from:
# from PIL.ExifTags import TAGS, GPSTAGS
# pprint(img.getexif().get_ifd(GPS_INFO_TAG))
# {
#   1: 'N',
#   2: (44.0, 2.0, 18.02),
#   3: 'W',
#   4: (123.0, 3.0, 23.11),
#   5: b'\x00',
#   6: 200.624308608708,
#  12: 'K',
#  13: 0.17858947470426592,
#  16: 'M',
#  17: 84.61828618286182,
#  23: 'M',
#  24: 84.61828618286182,
#  31: 5.369866362451108
# }

LAT_REF = 1  # e.g. "N"
LAT = 2  # e.g.  (37.0, 47.0, 12.85)
LNG_REF = 3  # e.g. W
LNG = 4  # e.g. (122.0, 15.0, 19.94)


class Plaque:
    """
    Class to encapsulate the image/location of the plaque, and provide a method
    to submit the object to Read the Plaque.
    """

    DEFAULT_LAT = 44.0
    DEFAULT_LNG = 46.0

    if DEBUG:
        submit_url = "http://127.0.0.1:8080/add"
    else:
        submit_url = "https://readtheplaque.com/add"

    def __init__(self, fname, title="", description=""):
        """Lat/Lng is extracted from the exif tags of the image file."""
        self.fname = fname
        self.title = title
        self.description = description
        self._set_exif_lat_lng()

    def submit(self):
        """Submit the plaque with a POST request to Read The Plaque"""
        with open(self.fname, "rb") as plaque_image_fh:
            files = {"plaque_image_file": plaque_image_fh}
            data = {
                "lat": self.lat,
                "lng": self.lng,
                "title": self.title,
                "description": self.description,
                "tags": "",
            }
            response = requests.post(
                Plaque.submit_url, files=files, data=data, timeout=60
            )
            response.raise_for_status()

    def _set_exif_lat_lng(self):
        """Extract the location from the image tags, using exiftool"""

        def _decimal_pos_from_exif(exif, ref):
            degs, mins, secs = [float(exif[i]) for i in range(3)]
            decimal = degs + mins / 60.0 + secs / 3600.0
            if ref in ("S", "W"):
                decimal *= -1
            return decimal

        try:
            with Image.open(self.fname) as img:
                gps = img.getexif().get_ifd(GPS_INFO_TAG)
                self.lat = _decimal_pos_from_exif(gps[LAT], gps[LAT_REF])
                self.lng = _decimal_pos_from_exif(gps[LNG], gps[LNG_REF])
        except (TypeError, KeyError) as err:
            print(f"Can't read GPS in {self.fname}, using defaults. {err}")
            self.lat = self.DEFAULT_LAT
            self.lng = self.DEFAULT_LNG

    def __repr__(self):
        return f"{self.fname} ({self.lat:.5f}, {self.lng:.5f})"


def main(img_fnames):
    """
    For a list of images, make plaque instances and submit to Read The Plaque.
    """
    plaques = []
    print(f"Loading {len(img_fnames)} images")
    for fname in img_fnames:
        plaque = Plaque(fname, "", "")
        plaques.append(plaque)
    print("Loading complete")

    posted = []
    failed = []

    for i, plaque in enumerate(plaques):
        print(f"posting {i+1} / {len(plaques)} {plaque}", end="")
        try:
            if not DEBUG:
                tstart = datetime.datetime.now()
                plaque.submit()
                tend = datetime.datetime.now()
                print(" ", tend - tstart)
                time.sleep(30)
            posted.append(plaque.fname)
        except requests.exceptions.HTTPError as err:
            failed.append(plaque.fname)
            print(", failed", err)


    (prefix, items) = ("Uploaded", posted) if posted else ("Failed", failed)
    items_str = "\n\t".join(items)
    print(f"{prefix}:\n\t{items_str}")

if __name__ == "__main__":
    main(sys.argv[1:])
