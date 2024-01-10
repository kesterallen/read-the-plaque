
import unittest
import main

# README: run with 'python main_test.py'

##TODO: /kid_is, /same-age, /tj, /sbs, 
## First/middle/last for /picture/add, /picture/delete
## /recipies ...
## /resume
## /air
## , etc
#
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
class TestStringMethods(unittest.TestCase):
    def test_index(self):
        main.app.testing = True
        client = main.app.test_client()
        r = client.get('/')
        assert r.status_code == 200
        assert 'hello' in r.data.decode('utf-8')

    def test_index_abc(self):
        main.app.testing = True
        client = main.app.test_client()
        r = client.get('/abc')
        assert r.status_code == 200
        assert 'hello abc' in r.data.decode('utf-8')

    def test_about_abc(self):
        main.app.testing = True
        client = main.app.test_client()
        r = client.get('/abc_about')
        assert r.status_code == 200
        assert 'food salad things' in r.data.decode('utf-8')

#def test_ordering():
#    main.app.testing = True
#    client = main.app.test_client()
#    r = client.get('/check/order')
#    assert r.status_code == 200
#    assert 'date ordering correct' in r.data.decode('utf-8')
#
#def test_img():
#    main.app.testing = True
#    client = main.app.test_client()
#    routes = ['img', 'i']
#    for route in routes:
#        r = client.get(f'/{route}/1')
#        assert r.status_code == 200
#
#def test_imgp():
#    main.app.testing = True
#    client = main.app.test_client()
#    routes = ['imgperm', 'imgp', 'ip']
#    for route in routes:
#        r = client.get(f'/{route}/5')
#        assert r.status_code == 200
#
#def test_date():
#    main.app.testing = True
#    client = main.app.test_client()
#    route = '/date/2016-10-01'
#    r = client.get(route)
#    assert r.status_code == 200
#
#def test_display():
#    main.app.testing = True
#    client = main.app.test_client()
#    routes = ['/d/1', '/display/1', '/d', '/display']
#    for route in routes:
#        r = client.get(route)
#        assert r.status_code == 200
#
#def test_display_perm():
#    main.app.testing = True
#    client = main.app.test_client()
#    routes = ['navperm', 'displayperm', 'perm', 'p']
#    for route in routes:
#        r = client.get(f'/{route}/5')
#        print(r.status_code)
#        assert r.status_code == 200
#
#def test_random():
#    main.app.testing = True
#    client = main.app.test_client()
#    r = client.get('/random')
#    assert r.status_code == 200
#
#def test_feed():
#    main.app.testing = True
#    client = main.app.test_client()
#    routes = ['/feed', '/feeds/feed.xml']
#    for route in routes:
#        r = client.get(route)
#        assert r.status_code == 200
#        assert 'Lots of pictures of the kids' in r.data.decode('utf-8')
#
#def test_air():
#    main.app.testing = True
#    client = main.app.test_client()
#    r = client.get('/air')
#    assert r.status_code == 200
#
#def test_resume():
#    main.app.testing = True
#    client = main.app.test_client()
#    r = client.get('/resume')
#    assert r.status_code == 200

if __name__ == '__main__':
    unittest.main()
