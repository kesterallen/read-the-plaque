# -*- coding: utf-8 -*-

import json
import logging
import requests
import sys

remote_site_json_url = "http://readtheplaque.com/static/plaques_updated.json"

local_site_url = "http://localhost:8080"
local_post_url = local_site_url + "/add"
local_flush_url = local_site_url + "/flush"

def get_plaque_post_data(plaque):
	return {
        "plaque_image_url": plaque["img_url_tiny"],
        "title": plaque["title"],
        "description": plaque["title"],
        "lat": plaque["lat"],
        "lng": plaque["lng"],
    }

def main():
    log = logging.getLogger()
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    log.addHandler(ch)
    
    # download the json
    remote_site_response = requests.get(remote_site_json_url)
    data = remote_site_response.json()
    
    # loop through each plaque
    plaques = data["plaques"]
    for idx,plaque in enumerate(plaques):
    
        plaque_post_data = get_plaque_post_data(plaque)
        
        logging.info("+ loading '%s' (item %s of %s)..." % (plaque["title"], idx, len(plaques)))
        
        try:
            post_response = requests.post(local_post_url, data=plaque_post_data)
            if post_response.status_code != 200 or "resubmit." in post_response.text:
                logging.info("+ ... failed: %s" % post_response)
            else:
                logging.info("+ ... succeeded!")
        except Exception as error:
            logging.info("+ ... failed: %s" % error)
    

if __name__ == "__main__":
    main()
