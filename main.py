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
import logging

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util

import consumer
import models
import filters

webapp.template.register_template_library('filters')


def GetCurrentUser(request):
  """Returns a User entity (OpenID or Google) or None."""
  user = users.get_current_user()
  if user:
    return models.User(google_user=user)
  session_id = request.cookies.get('session', '')
  if not session_id:
    return None
  login = consumer.Login.get_by_key_name(session_id)
  if not login:
    return None
  return models.User(openid_user=login.claimed_id)


class IndexHandler(webapp.RequestHandler):

  def get(self):
    user = GetCurrentUser(self.request)
    template_values = {
      "user": user,
    }
    self.response.out.write(template.render("index.html", template_values))


class SiteHandler(webapp.RequestHandler):

  def get(self):
    self.response.out.write("I'm a site page.")


class LoginHandler(webapp.RequestHandler):

  def get(self):
    next_url = self.request.get("next")
    if not re.match(r'^/[\w/]*$', next_url):
      next_url = '/'
    user = GetCurrentUser(self.request)
    google_login_url = users.create_login_url('/s/notelogin?next=' + next_url)
    template_values = {
      "user": user,
      "google_login_url": google_login_url,
    }
    self.response.out.write(template.render("login.html", template_values))


class NoteLoginHandler(webapp.RequestHandler):
  """Update a just-logged-in user's last_login property and send them along."""
  
  def get(self):
    next_url = self.request.get("next")
    if not re.match(r'^/[\w/]*$', next_url):
      next_url = '/'
    user = GetCurrentUser(self.request)
    if user:
      user = user.GetOrCreateFromDatastore()
      user.put()  # updates time
    self.redirect(next_url)


class LogoutHandler(webapp.RequestHandler):
  def get(self):
    next_url = self.request.get("next")
    if not re.match(r'^/[\w/]*$', next_url):
      next_url = '/'
    user = GetCurrentUser(self.request)
    if user:
      user.LogOut(self, next_url)
    else:
      self.redirect(next_url)


class UserHandler(webapp.RequestHandler):

  def get(self, user_key):
    user = GetCurrentUser(self.request)
    profile_user = models.User.get_by_key_name(user_key)
    if not profile_user:
      self.response.set_status(404)
      return
    can_edit = user and user.sha1_key == profile_user.sha1_key
    edit_mode = can_edit and (self.request.get('mode') == "edit")

    # get all the projects that this user maintains metadata for
    pquery = db.Query(models.Project, keys_only=True)
    pquery.filter('owner =', profile_user)
    projects = [key.name() for key in pquery.fetch(500)]

    url = ""
    if profile_user.openid_user:
      url = profile_user.openid_user
    elif profile_user.url:
      url = profile_user.url

    template_values = {
      "user": user,   # logged-in user, or None
      "edit_mode": edit_mode,
      "can_edit": can_edit,
      "profile_user": profile_user,
      "user_key": user_key,   # the sha1-ish thing
      "projects": projects,   # list(str), of project keys
      "url": url,
    }
    self.response.out.write(template.render("user.html", template_values))


class CreateHandler(webapp.RequestHandler):

  def get(self):
    user = GetCurrentUser(self.request)
    if not user:
      self.redirect('/s/login?next=/s/create')
      return
    template_values = {
      "user": user,
    }
    self.response.out.write(template.render("create.html", template_values))

  def post(self):
    user = GetCurrentUser(self.request)
    if not user:
      self.redirect('/s/login?next=/s/create')
      return
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
    user = user.GetOrCreateFromDatastore()
    project = models.Project(key_name=project_key,
                             owner=user)
    project.put()
    self.redirect("/%s" % project_key)


class ProjectHandler(webapp.RequestHandler):

  def get(self, project_key):
    user = GetCurrentUser(self.request)
    project = models.Project.get_by_key_name(project_key)
    if not project:
      self.response.set_status(404)
    can_edit = user and project and user.sha1_key == project.owner.sha1_key
    edit_mode = can_edit and (self.request.get('mode') == "edit")

    template_values = {
      "user": user,
      "project": project,
      "edit_mode": edit_mode,
      "can_edit": can_edit,
      "project_key": project_key,
    }
    self.response.out.write(template.render("project.html", template_values))


class ProjectEditHandler(webapp.RequestHandler):
  """Handles POSTs to edit a project."""

  def post(self):
    user = GetCurrentUser(self.request)
    project_key = self.request.get('project')
    logging.info("project key: %s", project_key)
    project = models.Project.get_by_key_name(project_key)
    logging.info("project: %s", project)
    if not project:
      self.response.set_status(404)
      return
    can_edit = user and user.sha1_key == project.owner.sha1_key
    if not can_edit:
      self.response.set_status(403)
      return
    project.how_to = self.request.get("how_to")
    project.code_repo = self.request.get("code_repo")
    project.home_page = self.request.get("home_page")
    project.bug_tracker = self.request.get("bug_tracker")
    project.put()
    self.redirect('/' + project_key)


def main():
  application = webapp.WSGIApplication([
      ('/', IndexHandler),
      ('/s/create', CreateHandler),
      ('/s/login', LoginHandler),
      ('/s/logout', LogoutHandler),
      ('/s/editproject', ProjectEditHandler),
      ('/s/notelogin', NoteLoginHandler),
      ('/s/.*', SiteHandler),
      (r'/u/([a-f0-9]{6,})', UserHandler),
      (r'/([a-z][a-z0-9\.\-]*[a-z0-9])/?', ProjectHandler),
      ],
      debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
