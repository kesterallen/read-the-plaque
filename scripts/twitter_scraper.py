"""Import twitter plaques from twitter URLs"""

import sys
import time
from attrdict import AttrDict
import requests
from twython import Twython, TwythonError

POST_URL = 'https://readtheplaque.com/add'

DEFAULT_LAT = 44.0
DEFAULT_LNG = 46.0

def keys(keyfile="key_twitter.txt"):
    """
    Read the secret keys from a non-git file and return them in the order that
    the Twython constructor expects.
    """
    # Read keys from file
    file_keys = {}
    with open(keyfile) as key_fh:
        for line in key_fh.readlines():
            key_name, key_value = line.split("=")
            file_keys[key_name] = key_value.strip()

    # Verify and return in correct order
    auth_keys = ["APP_KEY", "APP_SECRET", "OAUTH_TOKEN", "OAUTH_TOKEN_SECRET"]
    for auth_key in auth_keys:
        assert auth_key in file_keys
    return([file_keys[k] for k in auth_keys])

class NoImageError(Exception):
    """Exception to indicate the there isn't an image in the tweet."""

def get_img_urls(tweet):
    """Extract the URL(s) of the image from the tweet."""
    if 'extended_entities' in tweet:
        entities = tweet.extended_entities
    elif 'entities' in tweet:
        entities = tweet.entities
    else:
        raise NoImageError("No entities in tweet.")

    urls = [m['media_url'] for m in entities['media']]
    if not urls:
        raise NoImageError("No images in tweet entities.")
    return urls

def get_tweet(tweet_id, tweet_mode='extended'):
    """Get the tweet object from twitter"""
    twitter = Twython(*keys())
    tweet = twitter.show_status(id=tweet_id, tweet_mode=tweet_mode)
    tweet = AttrDict(tweet)
    tweet.url = f"https://twitter.com/{tweet.user.screen_name}/status/{tweet_id}"
    return tweet

def get_plaque_description(tweet, imgs):
    """Create plaque description."""
    # Append any extra images:
    #
    urls = [f' <br/><img class="img-responsive" src="{i}"/>' for i in imgs[1:]]
    img_desc = "\n".join(urls)

    text = ascii(tweet.full_text) #tweet.full_text.encode("utf8")
    user = tweet.user.screen_name
    desc = f"""
{text}

<a target="_blank" href="{tweet.url}">Tweet</a>

{img_desc}

<br/> <br/>Submitted by <a href="https://twitter.com/{user}">@{user}</a>.
"""
    return desc

def get_plaque(tweet_id):
    """Get data for plaque from tweet object."""
    tweet = get_tweet(tweet_id)
    if tweet.geo is not None:
        lat, lng = tweet.geo.coordinates
    else:
        lat, lng = DEFAULT_LAT, DEFAULT_LNG

    img_urls = get_img_urls(tweet)

    description = get_plaque_description(tweet, img_urls)

    plaque = AttrDict({
        'lat': lat,
        'lng': lng,
        'plaque_image_url': img_urls[0],
        'title': f"From {tweet.url}",
        'description': description,
        'url': tweet.url,
    })
    return plaque

def _report(events, title):
    if events:
        text = "\n\t".join([e.url for e in  events])
        print(f"\n{title}:\n\t{text}")

def main():
    """Extract and upload plaque pages for one or more Twitter URLs or IDs."""
    no_imgs = []

    # If the input is a twitter URL, grab just the ID at the end of the URL,
    # otherwise use the whole input (in which case the input is presumably just
    # the twitter status ID):
    #
    ids = sys.argv[1:]
    tweet_ids = [t.split('/')[-1] for t in ids]

    results = {True: [], False: []}

    for i, tweet_id in enumerate(tweet_ids):
        print("Submitting {} / {}".format(i+1, len(tweet_ids)))
        try:
            plaque = get_plaque(tweet_id)
            resp = requests.post(POST_URL, data=plaque)

            is_good = not(resp.status_code != 200 or 'resubmit.' in resp.text)
            results[is_good].append(plaque)

        except (TwythonError, NoImageError, KeyError) as err:
            print("{} Skipping {}".format(err, tweet_id))
            no_imgs.append(tweet_id)
            results[False].append(tweet_id)

        time.sleep(1.5)

    _report(results[False], "Failed")
    _report(results[True], "Succeeded")

    if no_imgs:
        print("No Image URLS: {}".format(no_imgs))

if __name__ == '__main__':
    main()
