
import datetime
import logging
import math
import random

from google.appengine.api import mail
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.api import search
from google.appengine.ext import ndb

from Models import Plaque

ADMIN_EMAIL = 'kester+readtheplaque@gmail.com'
NOTIFICATION_SENDER_EMAIL = '"Kester Allen" <kester@gmail.com>'

DEF_NUM_PENDING = 5
DYNAMIC_PLAQUE_CUTOFF = 50

PLAQUE_SEARCH_INDEX_NAME = 'plaque_index'

class SubmitError(Exception):
    pass

def latlng_angles_to_dec(ref, latlng_angles):
    """Convert a degrees, hours, minutes tuple to decimal degrees."""
    latlng = float(latlng_angles[0]) + \
             float(latlng_angles[1]) / 60.0 + \
             float(latlng_angles[2]) / 3600.0
    if ref == 'N' or ref == 'E':
        pass
    elif ref == 'S' or ref == 'W':
        latlng *= -1.0
    else:
        raise SubmitError(
            'reference "%s" needs to be either N, S, E, or W' % ref)

    return latlng

def email_admin(msg, body):
    try:
        mail.send_mail(sender=NOTIFICATION_SENDER_EMAIL,
                       to=ADMIN_EMAIL,
                       subject=msg,
                       body=body,
                       html=body)
    except Exception as err:
        logging.debug('mail failed: %s, %s' % (msg, err))

def get_bounding_box(plaques):
    if plaques:
        lats = [p.location.lat for p in plaques]
        lngs = [p.location.lon for p in plaques]
        bounding_box = [[min(lngs), min(lats)], [max(lngs), max(lats)]]
    else:
        bounding_box = None
    return bounding_box

def get_template_values(**kwargs):
    memcache_name = 'template_values_%s' % users.is_current_user_admin()
    template_values = memcache.get(memcache_name)
    if template_values is None:
        #num_pending = Plaque.num_pending(num=DEF_NUM_PENDING)
        footer_items = get_footer_items()
        loginout_output = loginout()

        template_values = {
            #'num_pending': num_pending,
            'footer_items': footer_items,
            'loginout': loginout_output,
            'dynamic_plaque_cutoff': DYNAMIC_PLAQUE_CUTOFF,
        }
        memcache_status = memcache.set(memcache_name, template_values)
        if not memcache_status:
            logging.debug(
                "memcache.set to %s for default_template_values failed" %
                memcache_name)
    else:
        logging.debug(
            "memcache.get from %s worked for default_template_values" %
            memcache_name)

    for key, val in kwargs.items():
        template_values[key] = val

    if 'plaques' in template_values:
        plaques = template_values['plaques']
        bounding_box = get_bounding_box(plaques)
        logging.info(plaques)
        logging.info(bounding_box)
        template_values['bounding_box'] = bounding_box

    return template_values

def get_footer_items():
    """
    Just 5 tags for the footer.
    Memcache the output of this so it doesn't get calculated every time.
    """
    footer_items = memcache.get('get_footer_items')
    if footer_items is None:
        random_plaques = [get_random_plaque() for _ in range(5)]
        tags = get_random_tags()
        footer_items = {'tags': tags,
                        'new_plaques': random_plaques,}

        memcache_status = memcache.set('get_footer_items', footer_items)
        if not memcache_status:
            logging.debug("memcachefor get_footer_items failed")
    else:
        logging.debug("memcache.get worked for get_footer_items")

    return footer_items

def get_random_plaque():
    plaque_key = get_random_plaque_key()
    if plaque_key is None:
        return None
    plaque = ndb.Key(urlsafe=plaque_key).get()
    return plaque

#TODO: Generate random lat/lng point and get nearest plaque by index search?
def get_random_plaque_key(method='time'):
    """
    Get a random plaque key.  Limit to total number of runs to 100 to prevent
    infinite loop if there are no plaques.

    There are at least three strategies to get a random plaque:

        1. Perform a Plaque.query().count(), get a random int in the [0,count)
           range, and get the plaque at that offset using
           Plaque.query.get(offset=foo).

           This technique favors large submissions of plaques that were
           imported automatically (e.g. North Carolina, Geographs,
           Toronto/Ontario), and that large offsets are expensive in the NDB
           system.

        2. 'time': Pick a random time since the start of the site, and find a
           plaque that has a created_by value close to that time.

           This technique favors plaques which were submitted by users who have
           submitted many plaques over a long period of time, and will be
           unlikely to pick a plaque which would be picked by technique #1.

        3. 'geo': Pick a random geographical spot on the globe, and get the
           plaque closest to that.

           This will favor plaques that are further away from other plaques.

    """
    plaque_key = None
    bailout = 0
    plaque_search_index = search.Index(PLAQUE_SEARCH_INDEX_NAME)
    while plaque_key is None and bailout < 100:
        bailout += 1
        if method == 'geo':
            # Math from http://mathworld.wolfram.com/SpherePointPicking.html
            rand_u = random.random()
            rand_v = random.random()
            lng = ((2.0 * rand_u) - 1.0) * 180.0 # Range: [-180.0, 180.0)
            lat = math.acos(2.0 * rand_v - 1) * 180.0 / math.pi - 90.0
            search_radius_meters = 100000 # 100 km

            query_string = 'distance(location, geopoint(%s, %s)) < %s' % (
                            lat, lng, search_radius_meters)
            query = search.Query(query_string)
            results = plaque_search_index.search(query)
            logging.info("bailout %s: produced results (%s)" % (bailout, results))
            if results.number_found > 0:
                doc_id= results[0].doc_id
                plaque_key = ndb.Key(doc_id).get()
        else: #method == 'time'
            random_time = get_random_time()
            if random_time is not None:
                plaque_key = Plaque.query(
                                  ).filter(Plaque.approved == True
                                  ).filter(Plaque.created_on > random_time
                                  ).get(keys_only=True)
    if plaque_key is None:
        return None

    return plaque_key.urlsafe()

def get_random_time():
    """
    Get a random time during the operation of the site.
    """
    memcache_names = ['first', 'last']
    memcache_out = memcache.get_multi(memcache_names)
    memcache_worked = len(memcache_out.keys()) == len(memcache_names)
    if memcache_worked:
        first = memcache_out[memcache_names[0]]
        last = memcache_out[memcache_names[1]]
    else:
        first_plaque = Plaque.query().filter(Plaque.approved == True).order(Plaque.created_on).get()
        if first_plaque:
            first = first_plaque.created_on
        else:
            first = None

        last_plaque = Plaque.query().filter(Plaque.approved == True).order(-Plaque.created_on).get()
        if last_plaque:
            last = last_plaque.created_on
        else:
            last = None

        memcache_status = memcache.set_multi({
            memcache_names[0]: first,
            memcache_names[1]: last
        })
        if memcache_status:
            logging.debug("""memcache.set in Handlers.get_random_time() failed:
                %s were not set""" % memcache_status)

    if first is None or last is None:
        random_time = None
    else:
        diff = last - first
        diff_seconds = int(diff.total_seconds())
        rand_seconds = random.randint(0, diff_seconds)
        random_delta = datetime.timedelta(seconds=rand_seconds)
        random_time = first + random_delta

    return random_time

def get_random_tags(num=5):
    """
    Get a list of random tags. Limit to total number of runs to 100 to prevent
    infinite loop if there are no plaques or tags.
    """
    tags = set()
    bailout = 0
    try:
        while len(tags) < num and bailout < 100:
            bailout += 1
            plaque = get_random_plaque()
            if plaque is None:
                continue
            if plaque.tags:
                tag = random.choice(plaque.tags)
                tags.add(tag)
    except ValueError:
        logging.info("no plaques in get_random_tags")

    outtags = list(tags)
    outtags = outtags[:num]
    return outtags

def loginout():
    # Login/Logout link:
    user = users.get_current_user()
    if user:
        loginout = {'is_admin': users.is_current_user_admin(),
                    'url': users.create_logout_url('/'),
                    'text': 'Log out'}
    else:
        loginout = {'is_admin': users.is_current_user_admin(),
                    'url': users.create_login_url('/'),
                    'text': 'Admin login'}
    return loginout

