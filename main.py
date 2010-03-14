#!/usr/bin/env python
#
# Copyright 2010 Brad Fitzpatrick
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


from google.appengine.ext import webapp
from google.appengine.ext.webapp import util


class MainHandler(webapp.RequestHandler):

  def get(self):
    self.response.out.write('Hello world!')


class SiteHandler(webapp.RequestHandler):

  def get(self):
    self.response.out.write("I'm a site admin page.")


class ProjectHandler(webapp.RequestHandler):

  def get(self, project):
    self.response.out.write("I'm a project page for: %s" % project)


def main():
  application = webapp.WSGIApplication([
      ('/', MainHandler),
      ('/s/.*', SiteHandler),
      (r'/([a-z][a-z0-9_\.\-]*[a-z0-9])/?', ProjectHandler),
      ],
      debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
