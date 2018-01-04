
import datetime
import json
import os
import requests

post_url_all = 'http://readtheplaque.com/fulljp'
json_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             '../static/plaques_updated.json')
def main():
    now = str(datetime.datetime.now())

    resp = requests.get(post_url_all)
    all_plaques = json.loads(resp.content)
    print "Total: %s plaques" % len(all_plaques)

    json_data = {
        'plaques': all_plaques,
        'updated_on': now,
    }
    json_str = json.dumps(json_data)

    with open(json_filename, 'w') as fh:
        fh.write(json_str)

if __name__ == '__main__':
    main()
