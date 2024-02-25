
import unittest
import main

# README: run with 'python main_test.py'


#def test_buckets():
#    """Test that buckets are accessible, listable, and pointed at the right project"""
#    main.app.testing = True
#    client = main.app.test_client()
#    routes = ['/buckets', '/buckets/list']
#    for route in routes:
#        r = client.get(route)
#        assert r.status_code == 200
#        assert 'surlyfritter-python3' in r.data.decode('utf-8')
#
class TestMainPages(unittest.TestCase):
    def test_index(self):
        main.app.testing = True
        client = main.app.test_client()
        r = client.get('/')
        assert r.status_code == 200
        assert 'hello' in r.data.decode('utf-8')

if __name__ == '__main__':
    """
    @app.route("/", methods=["GET", "HEAD"])
    @app.route("/pending")
    @app.route("/pending/<int:num>")
    @app.route("/randpending")
    @app.route("/randpending/<int:num>")
    @app.route("/plaque/<string:title_url>", methods=["GET", "HEAD"])
    @app.route("/add", methods=["GET", "POST"])
    @app.route("/submit", methods=["GET", "POST"])
    @app.route("/submit-your-own", methods=["GET", "POST"])
    @app.route("/edit", methods=["POST"])
    @app.route("/edit/<string:plaque_key>", methods=["GET"])
    @app.route("/approve/<string:plaque_key>", methods=["POST"])
    @app.route("/disapprove/<string:plaque_key>", methods=["POST"])
    @app.route("/random")
    @app.route("/random/<int:num_plaques>")
    @app.route("/randompage")
    @app.route("/randompage/<int:num_plaques>")
    @app.route("/setfeatured/<string:plaque_key>", methods=["GET"])
    @app.route("/featured", methods=["GET"])
    @app.route("/featured/geojson", methods=["GET"])
    @app.route("/tweet", methods=["GET"])
    @app.route("/geojson/<string:title_url>", methods=["GET"])
    @app.route("/featured/random", methods=["GET"])
    @app.route("/tag/<string:tag>")
    @app.route("/map")
    @app.route("/map/<string:lat>/<string:lng>")
    @app.route("/map/<string:lat>/<string:lng>/<string:zoom>")
    @app.route("/counts")
    @app.route("/rss")
    @app.route("/about")
    @app.route(
    # @app.route("/search/pending/<string:search_term>", methods=["GET"]) # TODO
    @app.route("/search", methods=["POST"])
    @app.route("/search/<string:search_term>", methods=["GET"])
    @app.route("/nearby/<float(signed=True):lat>/<float(signed=True):lng>", methods=["GET"])
    @app.route(
    @app.route("/updatejp", methods=["GET"])  # delete?
    @app.route("/fulljp", methods=["GET"])  # delete?
    @app.route("/alljp", methods=["GET"])
    @app.route("/alljp/<string:plaque_keys_str>", methods=["GET"])
    """
    unittest.main()
