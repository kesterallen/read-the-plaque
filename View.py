
#TODO: Waymarking.com, openplaques.com
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
    autoescape=False)#True) # turn off autoescape to allow html redering of descriptions

def handle_404(request, response, exception):
    template = JINJA_ENVIRONMENT.get_template('error.html')
    response.write(template.render({'code': 404, 'error_text': exception}))
    response.set_status(404)

def handle_500(request, response, exception):
    template = JINJA_ENVIRONMENT.get_template('error.html')
    response.write(template.render({'code': 500, 'error_text': exception}))
    response.set_status(500)

def main():
    app = webapp2.WSGIApplication([
        ('/', h.ViewAllPlaques),
        ('/all/?', h.ViewAllPlaques),
        ('/all/(.+?)/?', h.ViewAllPlaques),
        ('/all/(.+?)/(.+?)', h.ViewAllPlaques),
        ('/plaque/?', h.ViewOnePlaque),
        ('/jp/?', h.JsonOnePlaque),
        ('/plaque/(.+?)', h.ViewOnePlaque),
        ('/plaque_comment/(.+?)', h.ViewOnePlaqueFromComment),
        ('/add/?', h.AddPlaque),
        ('/addmigrate/?', h.AddPlaqueMigrate),
        ('/comment', h.AddComment),
        ('/tag/(.+?)', h.ViewTag),
        ('/tags/?', h.ViewAllTags),
        ('/about', h.About),
        ('/rss', h.RssFeed),
        ('/flush', h.FlushMemcache),
        ('/counts', h.Counts),
        ('/delete', h.DeleteEverything),
    ], debug=True)

    app.error_handlers[404] = handle_404
    #app.error_handlers[500] = handle_500

    return app

app = main()
