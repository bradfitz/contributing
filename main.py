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


import os

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util


class User(db.Model):
  """A user's global state, not specific to a project."""
  user = db.UserProperty(required=True)
  url = db.StringProperty()
  last_login = db.DateProperty()


class Project(db.Model):
  """A project which can be contributed to, with its metadata."""
  name = db.StringProperty(required=True)  # primary key
  pretty_name = db.StringProperty(required=False)
  # main URL (String)
  # main version control (String)
  # how to send patches (text box)
  # Owners (list/map User -> LastSeen, involvement level)


class Contributor(db.Model):
  """A user-project tuple."""
  user = db.ReferenceProperty(User, required=True)
  project = db.ReferenceProperty(Project, required=True)

  is_active = db.BooleanProperty()
  role = db.StringProperty()  # e.g. "Founder" freeform.
  
  


  
class MainHandler(webapp.RequestHandler):

  def get(self):
    path = os.path.join(os.path.dirname(__file__), 'index.html')
    template_values = {
      "foo": "bar",
    }
    self.response.out.write(template.render(path, template_values))


class SiteHandler(webapp.RequestHandler):

  def get(self):
    self.response.out.write("I'm a site admin page.")


class CreateHandler(webapp.RequestHandler):

  def get(self):
    self.response.out.write("Create page.")


class ProjectHandler(webapp.RequestHandler):

  def get(self, project):
    self.response.out.write("I'm a project page for: %s" % project)


def main():
  application = webapp.WSGIApplication([
      ('/', MainHandler),
      ('/s/create', CreateHandler),
      ('/s/.*', SiteHandler),
      (r'/([a-z][a-z0-9_\.\-]*[a-z0-9])/?', ProjectHandler),
      ],
      debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
