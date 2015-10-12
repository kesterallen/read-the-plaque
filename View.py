
import jinja2
import logging
import os
import webapp2

import Handlers as h

JINJA_ENVIRONMENT = jinja2.Environment (
    loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__),
                     'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=False) # autoescape off, to allow html redering of descriptions

def main():
    app = webapp2.WSGIApplication([
        ('/page/(.+?)/(.+?)/(.+?)/?', h.ViewPlaquesPage),
        ('/page/(.+?)/(.+?)/?', h.ViewPlaquesPage),
        ('/page/(.+?)/?', h.ViewPlaquesPage),
        ('/page/?', h.ViewPlaquesPage),
        ('/plaque/(.+?)/?', h.ViewOnePlaque),
        ('/plaque/?', h.ViewOnePlaque),
        ('/randompage.*', h.RandomPlaquesPage),
        ('/random.*', h.RandomPlaque),
        #('/plaque_comment/(.+?)', h.ViewOnePlaqueFromComment),
        ('/jp/?', h.JsonOnePlaque),
        ('/alljp/?', h.JsonAllPlaques),
        ('/add/?', h.AddPlaque),
        ('/submit-your-own/?', h.AddPlaque),
        ('/edit/(.+?)/?', h.EditPlaque),
        ('/edit/?', h.EditPlaque),
        #('/comment', h.AddComment),
        ('/tag/(.+?)', h.ViewTag),
        ('/tags/?', h.ViewAllTags),
        ('/about', h.About),
        ('/rss', h.RssFeed),
        ('/flush', h.FlushMemcache),
        ('/counts', h.Counts),
        #('/deleteall', h.DeleteEverything),
        ('/delete', h.DeleteOnePlaque),
        ('/pending', h.ViewPending),
        ('/disapprove', h.DisapprovePlaque),
        ('/approve', h.ApprovePending),
        ('/approveall', h.ApproveAllPending),
        ('/addsearchall', h.AddSearchIndexAll),
        ('/addtitleurlall', h.AddTitleUrlAll),
        ('/search/(.+?)', h.SearchPlaques),
        ('/search/?', h.SearchPlaques),
        ('/geo/(.*?)/(.*?)/(.*?)/?', h.SearchPlaquesGeo),
        ('/geo/.+?', h.SearchPlaquesGeo),
        ('/geo/?', h.SearchPlaquesGeo),
        ('/s/(.+?)', h.SearchPlaques),
        ('/s/?', h.SearchPlaques),
        ('/', h.ViewPlaquesPage),
        ('/(.+?)/(.+?)', h.ViewOnePlaque), # supports the old_site_id
        ('/(.+?)/?', h.ViewOnePlaque), # supports the old_site_id
    ], debug=True)

    app.error_handlers[404] = h.handle_404
    app.error_handlers[500] = h.handle_500

    return app

app = main()
