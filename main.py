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


import os
import re

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util

import models

  
class MainHandler(webapp.RequestHandler):

  def get(self):
    template_values = {
      "foo": "bar",
    }
    self.response.out.write(template.render("index.html", template_values))


class SiteHandler(webapp.RequestHandler):

  def get(self):
    self.response.out.write("I'm a site page.")


class LoginHandler(webapp.RequestHandler):

  def get(self):
    user = users.get_current_user()
    google_login_url = users.create_login_url('/')
    template_values = {
      "user": user,
      "google_login_url": google_login_url,
    }
    self.response.out.write(template.render("login.html", template_values))


class CreateHandler(webapp.RequestHandler):

  def get(self):
    user = users.get_current_user()
    if not user:
      # enforced in app.yaml
      return
    template_values = {
      "user": user,
    }
    self.response.out.write(template.render("create.html", template_values))

  def post(self):
    user = users.get_current_user()
    if not user:
      return  # enforced in app.yaml anyway
    def error(msg):
      self.response.out.write("Error creating project:<ul><li>%s</li></ul>." %
                              msg)
      return
    project_key = self.request.get('project')
    if not project_key:
      return error("No project specified.")
    if not re.match(r'^[a-z][a-z0-9\.\-]*[a-z0-9]$', project_key):
      return error("Project name must match regular expression " +
                   "<tt>/^[a-z][a-z0-9\.\-]*[a-z0-9]$/</tt>.")
    project = models.Project.get_by_key_name(project_key)
    if project:
      return error("Project already exists: <a href='/%s'>%s</a>" %
                   (project_key, project_key))
    project = models.Project(key_name=project_key,
                             owner=user)
    project.put()
    self.redirect("/%s" % project_key)


class ProjectHandler(webapp.RequestHandler):

  def get(self, project_key):
    user = users.get_current_user()
    project = models.Project.get_by_key_name(project_key)
    if not project:
      self.response.out.write(
        "Project doesn't exist.  <a href='/s/create'>Create it</a>?")
      return
    template_values = {
      "user": user,
      "project": project,
    }
    self.response.out.write(template.render("project.html", template_values))


def main():
  application = webapp.WSGIApplication([
      ('/', MainHandler),
      ('/s/create', CreateHandler),
      ('/s/login', LoginHandler),
      ('/s/.*', SiteHandler),
      (r'/([a-z][a-z0-9\.\-]*[a-z0-9])/?', ProjectHandler),
      ],
      debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
