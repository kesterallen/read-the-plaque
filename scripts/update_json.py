
import datetime

import json
import os
import pytz
import requests

post_url_all = 'http://readtheplaque.com/alljp'
post_url_update = 'http://readtheplaque.com/updatejp'

ALL = True

def main():
    now = str(datetime.datetime.now(pytz.timezone('US/Pacific')))
    json_filename = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '../static/plaques_updated.json')

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

        resp = requests.post(post_url_update, data={'updated_on': json_data['updated_on']})
        new_plaques = json.loads(resp.content)
        print "found %s new plaques" % len(new_plaques)

        import ipdb; ipdb.set_trace()
        # Insert in descending time sort, and update the timestamp:
        for plaque in reversed(new_plaques):
            json_data['plaques'].insert(0, plaque)
        json_data['updated_on'] = now

    json_str = json.dumps(json_data)
    with open(json_filename, 'w') as fh:
        fh.write(json_str)

if __name__ == '__main__':
    main()
