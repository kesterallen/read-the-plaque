"""Import twitter plaques from twitter URLs"""

import sys
import time
from attrdict import AttrDict
import requests
from typing import Tuple, Iterator#, Union
from twython import Twython, TwythonError

POST_URL = "https://readtheplaque.com/add"

DEFAULT_LAT_LNG = (44.0, 46.0)

PLAQUE_IMAGE_INDEX = 0

class NoImageError(Exception):
    """Exception to indicate the there isn't an image in the tweet."""

def _keys(keyfile: str="key_twitter.txt") -> list:
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
    auth_names = ["APP_KEY", "APP_SECRET", "OAUTH_TOKEN", "OAUTH_TOKEN_SECRET"]
    for auth_name in auth_names:
        assert auth_name in file_keys
    return([file_keys[n] for n in auth_names])

def get_img_urls(tweet: dict) -> list:
    """Extract the URL(s) of the image from the tweet."""
    if "extended_entities" in tweet:
        entities = tweet.extended_entities
    elif "entities" in tweet:
        entities = tweet.entities
    else:
        raise NoImageError("No entities in tweet.")

    urls = [m["media_url"] for m in entities["media"]]
    if not urls:
        raise NoImageError("No images in tweet entities.")
    return urls

def get_tweet(tweet_id: str, tweet_mode: str="extended") -> dict:
    """Get the tweet object from twitter"""
    twitter = Twython(*_keys())
    tweet = twitter.show_status(id=tweet_id, tweet_mode=tweet_mode)
    tweet = AttrDict(tweet)
    tweet.url = f"https://twitter.com/{tweet.user.screen_name}/status/{tweet_id}"

    try:
        tweet.lat, tweet.lng = tweet.geo.coordinates
    except (AttributeError, TypeError):
        tweet.lat, tweet.lng = DEFAULT_LAT_LNG

    return tweet

def get_image_url_and_description(tweet: dict) -> Tuple:
    """Create plaque description."""

    img_url = None
    img_extras = []

    urls = get_img_urls(tweet)
    for i, url in enumerate(urls):
        if i == PLAQUE_IMAGE_INDEX:
            img_url = url
        else:
            img_extras.append(f'<br/><img class="img-responsive" src="{url}"/>')

    img_extras_desc = "\n".join(img_extras)

    name = tweet.user.screen_name
    submitter_link = f"""<a href="https://twitter.com/{name}">@{name}</a>"""

    desc = f"""
{ascii(tweet.full_text)}

<a target="_blank" href="{tweet.url}">Tweet</a>

{img_extras_desc}

<br/><br/>Submitted by {submitter_link}.
"""
    return img_url, desc

def get_plaque(tweet_id: str) -> dict:
    """Get data for plaque from tweet object."""
    tweet = get_tweet(tweet_id)

    img_url, description = get_image_url_and_description(tweet)

    plaque = AttrDict({
        "lat": tweet.lat,
        "lng": tweet.lng,
        "plaque_image_url": img_url,
        "title": f"From {tweet.url}",
        "description": description,
        "url": tweet.url,
    })
    return plaque

def _report(results: dict) -> None:
    for is_success, plaques in results.items():
        if plaques:
            print("Success" if is_success else "Failed")
            print("\t", "\n\t".join(plaques))
    if results["no_imgs"]:
        print("No image in:")
        print("\t", "\n\t".join(results["no_imgs"]))

def main():
    """Extract and upload plaque pages for one or more Twitter URLs or IDs."""

    # If the input is a twitter URL, grab just the ID at the end of the URL,
    # otherwise use the whole input (in which case the input is presumably just
    # the twitter status ID):
    #
    ids = sys.argv[1:]
    tweet_ids = [t.split("/")[-1] for t in ids]

    results = {True: [], False: [], "no_imgs": []}

    for i, tweet_id in enumerate(tweet_ids):
        print(f"Submitting {i+1} / {len(tweet_ids)}")
        try:
            plaque = get_plaque(tweet_id)
            resp = requests.post(POST_URL, data=plaque)

            is_good = not(resp.status_code != 200 or "resubmit." in resp.text)
            results[is_good].append(plaque.url)

        except (TwythonError, NoImageError, KeyError) as err:
            print(f"{err} Skipping {tweet_id}")
            results["no_imgs"].append(tweet_id)
            results[False].append(tweet_id)

        time.sleep(1.5)

    _report(results)

if __name__ == "__main__":
    main()