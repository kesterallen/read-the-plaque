"""Import twitter plaques from twitter URLs"""

from attrdict import AttrDict
import sys
import time
import requests
from twython import Twython, TwythonError

POST_URL = 'https://readtheplaque.com/add'

DEFAULT_LAT = 44.0
DEFAULT_LNG = 46.0

def keys(keyfile="key_twitter.txt"):
    """Read the secret keys from a non-git file."""
    kvs = AttrDict({})
    with open(keyfile) as key_fh:
        for line in key_fh.readlines():
            k, v = line.split("=")
            kvs[k] = v.strip()
    for name in ["APP_KEY", "APP_SECRET", "OAUTH_TOKEN", "OAUTH_TOKEN_SECRET"]:
        assert name in kvs
    return(kvs.APP_KEY, kvs.APP_SECRET, kvs.OAUTH_TOKEN, kvs.OAUTH_TOKEN_SECRET)

class NoImageError(Exception):
    """Exception to indicate the there isn't an image in the tweet."""

def get_img_urls(tweet):
    """Extract the URL of the image from the tweet."""
    if 'extended_entities' in tweet:
        entities = tweet.extended_entities
    elif 'entities' in tweet:
        entities = tweet.entities
    else:
        raise NoImageError("No entities in tweet.")

    urls = []
    for media in entities['media']:
        url = media['media_url']
        urls.append(url)
    if not urls:
        raise NoImageError("No images in tweet.")
    return urls

def get_tweet(twitter, tweet_id, tweet_mode='extended'):
    tweet = twitter.show_status(id=tweet_id, tweet_mode=tweet_mode)
    tweet = AttrDict(tweet)
    tweet.url = f"https://twitter.com/{tweet.user.screen_name}/status/{tweet_id}"
    return tweet

def get_plaque_description(tweet, imgs):
    """Create plaque description."""
    # Append any extra images:
    #
    urls = [f' <br/><img class="img-responsive" src="{u}"/>' for u in imgs[1:]]
    img_desc = "\n".join(urls)
        
    text = ascii(tweet.full_text) #tweet.full_text.encode("utf8")
    user = tweet.user.screen_name
    desc = f"""
{text}

<a target="_blank" href="{tweet.url}">Tweet</a>

{img_desc}

<br/> <br/>Submitted by <a href="https://twitter.com/{user}">@{user}</a>."""
    return desc

def get_plaque_data(tweet):
    """Get data for plaque from tweet object."""
    if tweet.geo is not None:
        lat, lng = tweet.geo.coordinates
    else:
        lat, lng = DEFAULT_LAT, DEFAULT_LNG

    img_urls = get_img_urls(tweet)

    description = get_plaque_description(tweet, img_urls)

    plaque_data = AttrDict({
        'lat': lat,
        'lng': lng,
        'plaque_image_url': img_urls[0],
        'title': f"From {tweet.url}",
        'description': description,
    })
    return plaque_data

def _report(events, title):
    if events:
        text = "\n\t".join(events)
        print(f"\n{title}:\n\t{text}")

def main():
    """Extract and upload plaque pages for one or more Twitter URLs or IDs."""
    twitter = Twython(*keys())

    no_imgs = []

    # If the input is a twitter URL, grab just the ID at the end of the URL:
    #
    ids = sys.argv[1:]
    tweet_ids = [t.split('/')[-1] if t.startswith('http') else t for t in ids]

    fails = []
    successes = []

    for i, tweet_id in enumerate(tweet_ids):
        print("Submitting {} / {}".format(i+1, len(tweet_ids)))
        try:
            tweet = get_tweet(twitter, tweet_id)
            plaque_data = get_plaque_data(tweet)
            resp = requests.post(POST_URL, data=plaque_data)

            is_fail = resp.status_code != 200 or 'resubmit.' in resp.text
            if is_fail:
                fails.append(tweet.url)
            else:
                successes.append(tweet.url)

        except (TwythonError, NoImageError, KeyError) as err:
            print("{} Skipping {}".format(err, tweet_id))
            no_imgs.append(tweet_id)
            fails.append(tweet_id)

        time.sleep(1.5)

    _report(fails, "Failed")
    _report(successes, "Succeeded")

    if no_imgs:
        print("No Image URLS: {}".format(no_imgs))

if __name__ == '__main__':
    main()
