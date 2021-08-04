
import json
import os

here_path = os.path.dirname(os.path.abspath(__file__))
json_in = os.path.join(here_path, "../static/plaques_updated.json")
json_out = os.path.join(here_path, "../static/plaques.geojson")

def plaque_to_geojson_feature(plaque):
    geojson_feature = {
        "type": "Feature",
        "geometry": dict(
            type="Point",
            coordinates=[float(plaque["lng"]), float(plaque["lat"])]),
        "properties": dict(
            img_url_tiny=plaque["img_url_tiny"],
            title_page_url=plaque["title_page_url"],
            title=plaque["title"]),
    }
    return geojson_feature

def main():
    with open(json_in) as json_fh:
        json_data = json.load(json_fh)

    features = [plaque_to_geojson_feature(p) for p in json_data["plaques"]]
    geojson = dict(type="FeatureCollection", features=features)

    with open(json_out, "w") as json_fh:
        json_str = json.dumps(geojson)
        json_fh.write(json_str)

if __name__ == "__main__":
    #main()
    print("not needed anymore, run update_json.py")
    pass
