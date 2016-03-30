
import datetime
import json
import os
import requests

#post_url = 'http://localhost:8080/updatejp'
post_url = 'http://readtheplaque.com/updatejp'

def main():
    import ipdb; ipdb.set_trace()
    json_filename = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '../static/plaques_updated.json')

    with open(json_filename) as fh:
        json_data = json.load(fh)

    import ipdb; ipdb.set_trace()
    resp = requests.post(post_url, data={'updated_on': json_data['updated_on']})
    new_plaques = json.loads(resp.content)

    # Insert in descending time sort, and update the timestamp:
    for plaque in reversed(new_plaques):
        json_data['plaques'].insert(0, plaque)
    json_data['updated_on'] = str(datetime.datetime.now())
    json_str = json.dumps(json_data)
    import ipdb; ipdb.set_trace()

    with open(json_filename, 'w') as fh:
        fh.write(json_str)

if __name__ == '__main__':
    main()
