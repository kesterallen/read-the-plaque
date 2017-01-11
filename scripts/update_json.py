
import datetime

import json
import os
import re
import requests
import sys


url_tmpl = 'http://readtheplaque.com/%s'
#url_tmpl = 'http://10.10.10.238:8080/%s'
post_url_all = url_tmpl % 'alljp'
post_url_update = url_tmpl % 'updatejp'
json_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             '../static/plaques_updated.json')

ALL = False
UTC_OFFSET = 8 # PST
#UTC_OFFSET = 7 # PDT

def offset_time(last_updated_str):
    """
    This shift into UTC time seems to be necessary. The GAE datastore shows
    the times recorded in the Plaque entities are in 'PDT'. As of this writing,
    it is Daylight Savings Times.

    Unclear to me why this is required. I think that something in the process
    is assuming dates are in UTC, but I don't see where.

    Anyhow:
        INPUTS:
            A string representing a date, prefereably in %Y-%m-%d %H:%M:%S.%f 
            format, but any string that the datetime constructor will consume
            after being split on hyphen/space/colon/period will work.
        RETURNS:
            A string representing a date UTC_OFFSET later.

    TODO: This'll break every time change.
    """
    last_updated_parts = [int(i) for i in re.split('[- :.]', last_updated_str)]
    last_updated = datetime.datetime(*last_updated_parts)
    timedelta = datetime.timedelta(hours=UTC_OFFSET)
    offset_forward = last_updated + timedelta
    offset_forward_str = offset_forward.strftime("%Y-%m-%d %H:%M:%S.%f")
    return offset_forward_str

def main():
    now = str(datetime.datetime.now())

    if ALL:
        resp = requests.get(post_url_all)
        all_plaques = json.loads(resp.content)
        print "Total: %s plaques" % len(all_plaques)
        json_data = {
            'plaques': all_plaques,
            'updated_on': now,
        }
    else:
        with open(json_filename) as fh:
            json_data = json.load(fh)

        last_updated_offset = offset_time(json_data['updated_on'])

        resp = requests.post(
            post_url_update, data={'updated_on': last_updated_offset})

        new_plaques = json.loads(resp.content)
        suffix = "s"
        if len(new_plaques) == 1:
            suffix = ""
        print "Found %s new plauque%s." % (len(new_plaques), suffix)
        if len(new_plaques) == 0:
            sys.exit(1)

        # Insert in descending time sort, and update the timestamp:
        for plaque in reversed(new_plaques):
            json_data['plaques'].insert(0, plaque)
        json_data['updated_on'] = now

    json_str = json.dumps(json_data)
    with open(json_filename, 'w') as fh:
        fh.write(json_str)

if __name__ == '__main__':
    main()
