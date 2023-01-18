"""Import twitter plaques from twitter URLs"""

import sys
import time
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
        entities = tweet["extended_entities"]
    elif "entities" in tweet:
        entities = tweet["entities"]
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
    url = f"https://twitter.com/{tweet['user']['screen_name']}/status/{tweet_id}"
    tweet["url"] = url

    try:
        coordinates = tweet["geo"]["coordinates"]
    except (AttributeError, TypeError):
        coordinates = DEFAULT_LAT_LNG
    tweet["lat"], tweet["lng"] = coordinates

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

    desc = (
        f"{ascii(tweet['full_text'])}"
        f"\n\n<br/><br/><a target=\"_blank\" href=\"{tweet['url']}\">Tweet</a>"
        f"\n\n<br/>{img_extras_desc}"
        f"\n\n<br/><br/>Submitted by <a href=\"{tweet['url']}\">@{tweet['user']['screen_name']}</a>."
    )
    return img_url, desc

def get_plaque(tweet_id: str) -> dict:
    """Get data for plaque from tweet object."""
    tweet = get_tweet(tweet_id)

    img_url, description = get_image_url_and_description(tweet)

    plaque = {
        "lat": tweet["lat"],
        "lng": tweet["lng"],
        "plaque_image_url": img_url,
        "title": tweet["url"],
        "description": description,
        "url": tweet["url"],
    }
    return plaque

def _report(results: dict) -> None:
    """
	Error on failure: Success is reported twice??

			python scripts/twitter_scraper.py https://twitter.com/David_F_Taylor/status/1431574391696003072 https://twitter.com/HerbertHistory/status/1431635636981743622 https://twitter.com/pkmonaghan/status/1431692799162916871 https://twitter.com/thepracticalpen/status/1431765931685040135
			Submitting 1 / 4
			Submitting 2 / 4
			Submitting 3 / 4
			'media' Skipping 1431692799162916871
			Submitting 4 / 4
			Success:
					https://twitter.com/David_F_Taylor/status/1431574391696003072
					https://twitter.com/HerbertHistory/status/1431635636981743622
					https://twitter.com/thepracticalpen/status/1431765931685040135
			Failed:
					1431692799162916871
			Success:
					1431692799162916871
			No image in:
					1431692799162916871

    """
    for is_success, plaques in results.items():
        if plaques:
            msg_str = "\n\t".join(plaques)
            print("Success:" if is_success else "Failed:")
            print(f"\t{msg_str}")
    if results["no_imgs"]:
        msg_str= "\n\t".join(results["no_imgs"])
        print("No image in:")
        print(f"\t{msg_str}")

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
            results[is_good].append(plaque["url"])

        except (TwythonError, NoImageError, KeyError) as err:
            print(f"{err} Skipping {tweet_id}")
            results["no_imgs"].append(tweet_id)
            results[False].append(tweet_id)

        time.sleep(1.5)

    _report(results)

if __name__ == "__main__":
    main()
