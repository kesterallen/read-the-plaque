# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import re
import requests
import urllib
import tempfile
import pprint
import os
import time
import sys

# TODO: Is there a way to discover this list from the page itself?

plaque_ids_500 = [936, 1064, 735, 783, 663]
plaque_ids_test_small = [871, 437, 431, 425]
plaque_ids_test = [
    871, 437, 431, 425, 439, 433, 396, 895, 368, 350, 348, 429, 340, 366, 336,
    338, 334, 326, 352, 354, 364, 344, 328, 322, 312, 310, 342, 346, 283, 277,
    291, 271, 267, 265, 255, 273, 275, 257, 253, 249, 247, 241, 237, 243, 235,
    161, 210, 114, 202, 206, 179, 897, 867, 239, 226, 212, 881, 214, 208, 196,
]
plaque_ids_all = [
    871, 437, 431, 425, 439, 433, 396, 895, 368, 350, 348, 429, 340, 366, 336,
    338, 334, 326, 352, 354, 364, 344, 328, 322, 312, 310, 342, 346, 283, 277,
    291, 271, 267, 265, 255, 273, 275, 257, 253, 249, 247, 241, 237, 243, 235,
    161, 210, 114, 202, 206, 179, 897, 867, 239, 226, 212, 881, 214, 208, 196,
    899, 903, 901, 905, 245, 192, 190, 168, 125, 117, 605, 609, 556, 558, 508,
    441, 421, 445, 447, 461, 378, 400, 406, 408, 320, 316, 279, 285, 287, 263,
    289, 293, 251, 204, 188, 186, 177, 175, 163, 165, 119, 150, 147, 107, 121,
    129, 123, 127, 109, 99, 95, 90, 86, 78, 70, 61, 45, 17, 5,
    380, 423, 427, 435, 500, 502, 476, 388, 392, 398, 382, 532, 546, 552,
    404, 419, 494, 544, 623, 627, 591, 534, 542, 554, 567, 569, 575, 589, 607,
    663, 655, 661, 805, 847, 859, 673, 655, 651, 711, 767, 851, 787, 795, 797,
    823, 839, 845, 861, 394, 402, 512, 615, 639, 643, 653, 675, 1064, 887, 885,
    811, 835, 443, 659, 713, 715, 699, 733, 683, 649, 741, 775, 773, 731, 763,
    781, 783, 785, 789, 765, 799, 807, 837, 855, 873, 701, 813, 883, 1240, 761,
    875, 889, 869, 779, 735, 697, 504, 516, 685, 687, 815, 853, 825, 817, 791,
    819, 705, 809, 803, 863, 865, 893, 909, 877, 936, 879, 1299, 1303, 1307,
    1309, 1315, 1319, 1322, 1325, 723, 729, 1331, 1336,
]

plaque_ids = plaque_ids_all

plaque_ids.sort()

#site_url = 'http://10.10.15.40:8080'
site_url = 'http://127.0.0.1:8080'
#site_url = 'http://readtheplaque.net'
post_url = site_url + '/submit-your-own'
flush_url = site_url + '/flush'

def body_p_filter(tag):
    """
    Filter out non-<p> elements, <p> elements containing the image, and <p>
    elements with a specified class.
    """
    #if tag.has_attr('class') or tag.find('img') or tag.name != 'p':
    if tag.has_attr('class') or tag.name != 'p':# or tag.find('img'):
        return False

    #img = tag.find('img')
    #if img:
        #try:
            #is_ext_img = img.get('src').index('readtheplaque.com')
            #return False
        #except ValueError as err:
            #print "error on tag" % tag
            #pass
    return True

def get_tags(soup):
    tags_div = soup.find(id='tags')

    if tags_div is not None:
        tags_raw = [a.text.encode('utf-8') for a in tags_div.find_all('a')]
        tags = [re.sub('[^\w\s]', '', t) for t in tags_raw]
    else:
        tags = []
    return tags

def get_gps_location(soup):
    metas = soup.find_all('meta')
    gps_loc = None
    for meta in metas:
        if 'name' in meta.attrs and meta.attrs['name'] == 'geo.position':
            gps_loc = [c.encode('utf-8')
                           for c in meta.attrs['content'].split(';')]
    if gps_loc is None:
        gps_str = "67,67"
    else:
        gps_str = ",".join(gps_loc)

    return gps_str

def get_page_contents(soup):
    #post = soup.find(id='post')
    post = soup.find_all('div', {'class': "post-content clear"})[0]
    imgtxt = post.find('img')

    title = post.find('h1').contents[0]

    # Get the body, including the html styling. Use a RE kludge to strip the
    # link to the WP image. Almost certainly a better way to do it, but this
    # works.
    #
    body = post.find_all(body_p_filter)
    body_str = "".join([str(b) for b in body])
    pattern = '<a href="http://readtheplaque.com/wp-content/uploads/' + \
              '\d{4}/\d{2}/.*?\..*?">%s</a>' % str(imgtxt)
    body_str = re.sub(pattern, '', body_str)
    body_str = re.sub(str(imgtxt), '', body_str)

    # Get the full-sized original if this is a WP-scaled-down version of the
    # image:
    #
    img = post.find('img')
    img_url = img.attrs['src']
    img_url = re.sub('-\d+x\d+\.jpg', '.jpg', img_url)
    #img_url = re.sub('_large.jpeg', '.jpg', img_url)

    tags = get_tags(soup)
    tags_str = ", ".join(tags)

    return title.encode('utf-8'),\
           body_str,\
           img_url.encode('utf-8'),\
           tags_str.encode('utf-8')

#def get_image(img_url):
#    img_resp = requests.get(img_url)
#    img = img_resp.content
#
#    img_fh, img_filename = tempfile.mkstemp(suffix=".jpg")
#    os.write(img_fh, img)
#    os.close(img_fh)
#
#    return img_filename

print 'Flushing', flush_url
response = requests.get(flush_url)
print 'Flush:', response

for iplaque, plaque_id in enumerate(plaque_ids):
    url = 'http://readtheplaque.com/%s' % plaque_id
    print url
    get_resp = requests.get(url)
    soup = BeautifulSoup(get_resp.text, 'html.parser')

    gps_loc = get_gps_location(soup)
    title, body, img_url, tags = get_page_contents(soup)
    #img_filename = get_image(img_url)

    values = {
        'location': gps_loc,
        'plaque_image_url': img_url,
        'plaque_image_file': '',
        'title': title,
        'tags': tags,
        'description': body,
        'old_site_id': plaque_id,
    }
    post_resp = requests.post(post_url, data=values)
    if post_resp.status_code != 200:
        print "FAIL FAIL FAIL",
    print 1+iplaque, '/', len(plaque_ids), url,
    print 'post:', post_url, post_resp
    print title

flush_resp = requests.get(flush_url)
print 'Flush:', flush_resp
