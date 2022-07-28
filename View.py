
import jinja2
import os

import webapp2

import Handlers as h
import AdminHandlers as ah
import SearchHandlers as sh

JINJA_ENVIRONMENT = jinja2.Environment (
    loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__), 'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=False) # autoescape off, to allow html redering of descriptions

def main():
    app = webapp2.WSGIApplication(
        [
            # Admin routes
            ('/admin', ah.AdminLogin),
            ('/dup', ah.DuplicateChecker),
            ('/counts', ah.Counts),
            ('/flush', ah.FlushMemcache),
            ('/add/?', ah.AddPlaque),
            ('/submit-your-own/?', ah.AddPlaque),
            ('/edit/(.+?)/?', ah.EditPlaque),
            ('/edit/?', ah.EditPlaque),
            ('/setfeatured/(.*?)', ah.SetFeatured),
            ('/featured', ah.SetFeatured),
            ('/setupdated', ah.SetUpdatedOn),
            ('/disapprove', ah.DisapprovePlaque),
            ('/approve', ah.ApprovePending),
            ('/approveall', ah.ApproveAllPending),
            ('/delete', ah.DeleteOnePlaque),
            ('/deletesearch/(.+?)', ah.DeleteOneSearchIndex),
            #('/addsearchall', ah.AddSearchIndexAll),
            ('/reindex', ah.RedoIndex),
            #('/addtitleurlall', ah.AddTitleUrlAll),

            # Search routes
            ('/search/(.+?)', sh.SearchPlaques),
            ('/search/pending/(.+?)', sh.SearchPlaquesPending),
            ('/search/?', sh.SearchPlaques),
            ('/geo/(.*?)/(.*?)/(.*?)/?', sh.SearchPlaquesGeo),
            ('/geo/.+?', sh.SearchPlaquesGeo),
            ('/geo/?', sh.SearchPlaquesGeo),
            ('/nearby/(.+?)/(.+?)/(.+?)/?', sh.NearbyPage),
            ('/nearby/(.+?)/(.+?)/?', sh.NearbyPage),
            ('/nearby/?', sh.NearbyPage),
            ('/s/(.+?)', sh.SearchPlaques),
            ('/s/?', sh.SearchPlaques),

            # Non-admin routes
            ('/page/(.+?)/(.+?)/(.+?)/?', h.ViewPlaquesPage),
            ('/page/(.+?)/(.+?)/?', h.ViewPlaquesPage),
            ('/page/(.+?)/?', h.ViewPlaquesPage),
            ('/page/?', h.ViewPlaquesPage),
            ('/plaque/?', h.ViewOnePlaque), # home page
            ('/plaque/(.+?)/?', h.ViewOnePlaque), # specific plaque's page
            ('/plaque/(.+?)/(.*)', h.ViewOnePlaque), # attack? ignore extra params in an unused arg
            ('/randompage/(.+?)/?', h.RandomPlaquesPage),
            ('/randompage.*', h.RandomPlaquesPage),
            ('/random.*', h.RandomPlaque),
            #('/plaque_comment/(.+?)', h.ViewOnePlaqueFromComment),
            ('/geojson/(.+?)/?', h.GeoJson),
            ('/geojson/?', h.GeoJson),
            ('/tweet/?', h.TweetText),
            ('/alljp/(.+?)/?', h.JsonAllPlaques),
            ('/alljp/?', h.JsonAllPlaques),
            ('/updatejp/?', h.JsonAllPlaques),
            ('/fulljp/?', h.JsonAllPlaquesFull),
            #('/loc', h.LocationChecker), # POST only
            #('/comment', h.AddComment),
            ('/tag/(.+?)/(.+?)/?', h.ViewTag),
            ('/tag/(.+?)', h.ViewTag),
            #('/tags/?', h.ViewAllTags),
            ('/about', h.About),
            ('/rss', h.RssFeed),
            #('/deleteall', h.DeleteEverything),
            ('/pending/?', h.ViewPending),
            ('/oldpending/?', h.ViewOldPending),
            ('/pending/(.*?)/?', h.ViewPending),
            ('/nextpending/?', h.ViewNextPending),
            ('/randpending/?', h.ViewPendingRandom),
            ('/randpending/(.*?)/?', h.ViewPendingRandom),
            ('/map/(.*?)/(.*?)/(.*?)/?', h.BigMap), # lat, lng, zoom.
            ('/map/(.*?)/(.*?)/?', h.BigMap), # lat, lng
            ('/map/?', h.BigMap),
            ('/ocr/(.*?)', h.Ocr),
            ('/', h.ViewPlaquesPage),
            ('/(.+?)/(.+?)', h.ViewOnePlaque), # supports the old_site_id
            ('/(.+?)/?', h.ViewOnePlaque), # supports the old_site_id
        ],
        debug=True,
    )
    app.error_handlers[404] = h.handle_404
    app.error_handlers[500] = h.handle_500

    return app

app = main()
