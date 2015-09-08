
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
    autoescape=False) # turn off autoescape to allow html redering of descriptions

def handle_404(request, response, exception):
    template = JINJA_ENVIRONMENT.get_template('error.html')
    response.write(template.render({'code': 404, 'error_text': exception}))
    response.set_status(404)

def handle_500(request, response, exception):
    # TODO: email admin
    template = JINJA_ENVIRONMENT.get_template('error.html')
    response.write(template.render({'code': 500, 'error_text': exception}))
    response.set_status(500)

def main():
    app = webapp2.WSGIApplication([
        ('/page/(.+?)/(.+?)', h.ViewPlaquesPage),
        ('/page/(.+?)/?', h.ViewPlaquesPage),
        ('/page/?', h.ViewPlaquesPage),
        ('/plaque/(.+?)/?', h.ViewOnePlaque),
        ('/plaque/?', h.ViewOnePlaque),
        ('/plaque_comment/(.+?)', h.ViewOnePlaqueFromComment),
        ('/jp/?', h.JsonOnePlaque),
        ('/add/?', h.AddPlaque),
        ('/submit-your-own/?', h.AddPlaque),
        ('/update/(.+?)/?', h.EditPlaque),
        ('/update/?', h.EditPlaque),
        ('/edit/(.+?)/?', h.EditPlaque),
        ('/edit/?', h.EditPlaque),
        #('/rotate_image/(.+?)', h.RotateImage),
        ('/comment', h.AddComment),
        ('/tag/(.+?)', h.ViewTag),
        ('/tags/?', h.ViewAllTags),
        ('/about', h.About),
        ('/rss', h.RssFeed),
        ('/flush', h.FlushMemcache),
        ('/counts', h.Counts),
        ('/deleteall', h.DeleteEverything),
        ('/delete', h.DeleteOnePlaque),
        ('/pending', h.ViewPending),
        ('/approve', h.ApprovePending),
        ('/approveall', h.ApproveAllPending),
        ('/', h.ViewPlaquesPage),
        ('/(.+?)/?', h.ViewOnePlaque), # supports the old_site_id
        ('/(.+?)/(.+?)', h.ViewOnePlaque), # supports the old_site_id
    ], debug=True)

    app.error_handlers[404] = handle_404
    #app.error_handlers[500] = handle_500

    return app

app = main()
