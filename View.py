
import jinja2
import logging
import os
import webapp2

import Handlers as h

JINJA_ENVIRONMENT = jinja2.Environment (
    loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__), 'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=False) # autoescape off, to allow html redering of descriptions

def main():
    app = webapp2.WSGIApplication(
        [
            ('/admin', h.AdminLogin),
            ('/page/(.+?)/(.+?)/(.+?)/?', h.ViewPlaquesPage),
            ('/page/(.+?)/(.+?)/?', h.ViewPlaquesPage),
            ('/page/(.+?)/?', h.ViewPlaquesPage),
            ('/page/?', h.ViewPlaquesPage),
            ('/plaque/(.+?)/?', h.ViewOnePlaque),
            ('/plaque/?', h.ViewOnePlaque),
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
            ('/dup', h.DuplicateChecker),
            ('/add/?', h.AddPlaque),
            ('/submit-your-own/?', h.AddPlaque),
            ('/edit/(.+?)/?', h.EditPlaque),
            ('/edit/?', h.EditPlaque),
            #('/comment', h.AddComment),
            ('/tag/(.+?)/(.+?)/?', h.ViewTag),
            ('/tag/(.+?)', h.ViewTag),
            #('/tags/?', h.ViewAllTags),
            ('/about', h.About),
            ('/rss', h.RssFeed),
            ('/flush', h.FlushMemcache),
            ('/counts', h.Counts),
            ('/reindex', h.RedoIndex),
            #('/deleteall', h.DeleteEverything),
            ('/delete', h.DeleteOnePlaque),
            ('/pending/?', h.ViewPending),
            ('/oldpending/?', h.ViewOldPending),
            ('/pending/(.*?)/?', h.ViewPending),
            ('/nextpending/?', h.ViewNextPending),
            ('/randpending/?', h.ViewPendingRandom),
            ('/randpending/(.*?)/?', h.ViewPendingRandom),
            ('/disapprove', h.DisapprovePlaque),
            ('/approve', h.ApprovePending),
            ('/approveall', h.ApproveAllPending),
            #('/addsearchall', h.AddSearchIndexAll),
            ('/deletesearch/(.+?)', h.DeleteOneSearchIndex),
            #('/addtitleurlall', h.AddTitleUrlAll),
            ('/search/(.+?)', h.SearchPlaques),
            ('/search/pending/(.+?)', h.SearchPlaquesPending),
            ('/search/?', h.SearchPlaques),
            ('/geo/(.*?)/(.*?)/(.*?)/?', h.SearchPlaquesGeo),
            ('/geo/.+?', h.SearchPlaquesGeo),
            ('/geo/?', h.SearchPlaquesGeo),
            ('/nearby/(.+?)/(.+?)/(.+?)/?', h.NearbyPage),
            ('/nearby/(.+?)/(.+?)/?', h.NearbyPage),
            ('/nearby/?', h.NearbyPage),
            ('/s/(.+?)', h.SearchPlaques),
            ('/s/?', h.SearchPlaques),
            ('/setupdated', h.SetUpdatedOn),
            ('/setfeatured/(.*?)', h.SetFeatured),
            ('/featured', h.SetFeatured),
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
