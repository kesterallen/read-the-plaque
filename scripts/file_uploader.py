
import subprocess
import sys
import time
import requests

DEBUG = True

class Plaque(object):
    """
    Class to encapsulate the image/location of the plaque, and how to submit it.
    """
    if DEBUG:
        submit_url = 'http://localhost:8080/add'
    else:
        submit_url = 'http://readtheplaque.com/add'

    def __init__(self, filename, title='', description=''):
        """
        Lat/Lng is extracted from the exif tags of the image file.
        """
        self.filename = filename
        self.title = title
        self.description = description
        self._set_exif_lat_lng()

    def submit(self):
        """
        Submit the plaque with a POST request to Read The Plaque
        """
        with open(self.filename,'rb') as plaque_image_fh:
            files = { 'plaque_image_file': plaque_image_fh }
            data = {
                'lat': self.lat,
                'lng': self.lng,
                'title': self.title,
                'description': self.description,
            }
            response = requests.post(Plaque.submit_url, files=files, data=data)
            return response.status_code

    def _set_exif_lat_lng(self):
        """
        Extract the location info from the image tags, using exiftool
        """
        cmd = "exiftool -c '%.10f' -p '$gpslatitude $gpslongitude' {}"
        latlng = subprocess.check_output(cmd.format(self.filename), shell=True)
        lat, lat_dir, lng, lng_dir = latlng.split()

        self.lat = float(lat) * (1.0 if lat_dir == 'N' else -1.0)
        self.lng = float(lng) * (1.0 if lng_dir == 'E' else -1.0)

    def __repr__(self):
        return "{0.filename} ({0.lat}, {0.lng})".format(self)

def main(img_filenames):
    """
    For a given list of images, make plaque instances and submit them to Read
    The Plaque.
    """

    plaques = []
    for filename in img_filenames:
        plaque = Plaque(filename)
        plaques.append(plaque)
        
    for i, plaque in enumerate(plaques):
        plaque.submit()
        print("uploaded {}/{} {}".format(i+1, len(plaques), plaque))
        if not DEBUG:
            time.sleep(10)

if __name__ == '__main__':
    main(sys.argv[1:])
