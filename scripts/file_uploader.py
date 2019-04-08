
import time
import requests

# Run this:
#     exiftool ~/Desktop/IMG*.JPG  | grep 'File Name|GPS Latitude  |GPS Longitude  ' | perl -F: -lane 'print $F[1]' | sed 's/deg //; s/N//; s/W//; s/"//' | sed "s/'//" | xargs -n7 > portland.txt
# to get the list of filename/lat/lng

post_url = 'http://readtheplaque.com/add'
#post_url = 'http://localhost:8080/add'

class Plaque(object):
    def __init__(self, title, filename, lats, lngs, desc):
        lat = float(lats[0]) + float(lats[1]) / 60.0 + float(lats[2]) / 3600.0
        lng = float(lngs[0]) + float(lngs[1]) / 60.0 + float(lngs[2]) / 3600.0

        self.title = title
        self.filename = filename
        self.lat = lat # north
        self.lng = -1.0 * lng # west
        self.description = desc

def main():
    img_list = 'portland.txt'

    plaques = []
    with open(img_list) as fh:
        for line in fh.readlines():
            fields = line.split()
            filename = "/home/kester/Desktop/{}".format(fields[0])
            plaque = Plaque('', filename, fields[1:4], fields[4:], '')
            plaques.append(plaque)
        
    for i, plaque in enumerate(plaques):
        post_resp = requests.post(
            post_url, 
            files={'plaque_image_file': open(plaque.filename,'rb')},
            data={
                'lat': plaque.lat,
                'lng': plaque.lng,
                'title': plaque.title,
                'description': plaque.description,
            }
        )
        print("done uploading {0} {1.lat} {1.lng}".format(i+1, plaque))
        time.sleep(10)

if __name__ == '__main__':
    main()
