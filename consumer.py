#!/usr/bin/python
#
# Copyright 2008 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
A sample OpenID consumer app for Google App Engine. Allows users to log into
other OpenID providers, then displays their OpenID login. Also stores and
displays the most recent logins.

Part of http://code.google.com/p/google-app-engine-samples/.

For more about OpenID, see:
  http://openid.net/
  http://openid.net/about.bml

Uses JanRain's Python OpenID library, version 2.1.1, licensed under the
Apache Software License 2.0:
  http://openidenabled.com/python-openid/

The JanRain library includes a reference OpenID provider that can be used to
test this consumer. After starting the dev_appserver with this app, unpack the
JanRain library and run these commands from its root directory:

  setenv PYTHONPATH .
  python ./examples/server.py -s localhost

Then go to http://localhost:8080/ in your browser, type in
http://localhost:8000/test as your OpenID identifier, and click Verify.
"""

import datetime
import logging
import os
import re
import sys
import urlparse
import wsgiref.handlers

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from openid import fetchers
from openid.consumer.consumer import Consumer
from openid.consumer import discover
from openid.extensions import pape, sreg
import fetcher
import store

# Set to True if stack traces should be shown in the browser, etc.
_DEBUG = False


class Session(db.Expando):
  """An in-progress OpenID login."""
  claimed_id = db.StringProperty()
  server_url = db.LinkProperty()
  store_and_display = db.BooleanProperty()


class Login(db.Model):
  """A completed OpenID login."""
  status = db.StringProperty(choices=('success', 'cancel', 'failure'))
  claimed_id = db.LinkProperty()
  server_url = db.LinkProperty()
  timestamp = db.DateTimeProperty(auto_now_add=True)
  session = db.ReferenceProperty(Session)


class Handler(webapp.RequestHandler):
  """A base handler class with a couple OpenID-specific utilities."""
  consumer = None
  session = None
  session_args = None

  def __init__(self):
    self.session_args = {}

  def get_consumer(self):
    """Returns a Consumer instance.
    """
    if not self.consumer:
      fetchers.setDefaultFetcher(fetcher.UrlfetchFetcher())
      if not self.load_session():
        return
      self.consumer = Consumer(self.session_args, store.DatastoreStore())

    return self.consumer

  def args_to_dict(self):
    """Converts the URL and POST parameters to a singly-valued dictionary.

    Returns:
      dict with the URL and POST body parameters
    """
    req = self.request
    return dict([(arg, req.get(arg)) for arg in req.arguments()])

  def load_session(self):
    """Loads the current session.
    """
    if not self.session:
      id = self.request.get('session_id')
      if id:
        try:
          self.session = db.get(db.Key.from_path('Session', int(id)))
          assert self.session
        except (AssertionError, db.Error), e:
          self.report_error('Invalid session id: %d' % id)
          return None

        fields = self.session.dynamic_properties()
        self.session_args = dict((f, getattr(self.session, f)) for f in fields)

      else:
        self.session_args = {}
        self.session = Session()
        self.session.claimed_id = self.request.get('openid')

      return self.session

  def store_session(self):
    """Stores the current session.
    """
    assert self.session
    for field, value in self.session_args.items():
      setattr(self.session, field, value)
    self.session.put()

  def render(self, extra_values={}):
    """Renders the page, including the extra (optional) values.

    Args:
      template_name: string
      The template to render.

      extra_values: dict
      Template values to provide to the template.
    """
    logins = Login.gql('ORDER BY timestamp DESC').fetch(20)
    for login in logins:
      login.display_name = self.display_name(login.claimed_id)
      login.friendly_time = self.relative_time(login.timestamp)

    values = {
      'response': {},
      'openid': '',
      'logins': logins,
    }
    values.update(extra_values)
    cwd = os.path.dirname(__file__)
    path = os.path.join(cwd, 'templates', 'base.html')
    self.response.out.write(template.render(path, values, debug=_DEBUG))

  def report_error(self, message, exception=None):
    """Shows an error HTML page.

    Args:
      message: string
      A detailed error message.
    """
    if exception:
      logging.exception('Error: %s' % message)
    self.render({'error': message})

  def show_front_page(self):
    """Do an internal (non-302) redirect to the front page.

    Preserves the user agent's requested URL.
    """
    front_page = FrontPage()
    front_page.request = self.request
    front_page.response = self.response
    front_page.get()

  def relative_time(self, timestamp):
    """Returns a friendly string describing how long ago the timestamp was.

    Args:
      timestamp: a datetime

    Returns:
      string
    """
    def format_number(num):
      if num <= 9:
        return {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five',
                6: 'six', 7: 'seven', 8: 'eight', 9: 'nine'}[num]
      else:
        return str(num)

    delta = datetime.datetime.now() - timestamp
    minutes = delta.seconds / 60
    hours = minutes / 60

    if delta.days > 1:
      return '%s days ago' % format_number(delta.days)
    elif delta.days == 1:
      return 'yesterday'
    elif hours > 1:
      return '%s hours ago' % format_number(hours)
    elif hours == 1:
      return 'an hour ago'
    elif minutes > 25:
      return 'half an hour ago'
    elif minutes > 5:
      return '%s minutes ago' % format_number(minutes)
    else:
      return 'moments ago'

  def display_name(self, openid_url):
    """Extracts a short, representative part of an OpenID URL for display.

    For example, it returns "ryan" for:
      ryan.com
      www.ryan.com
      ryan.provider.com
      provider.com/ryan
      provider.com/id/path/ryan

    Adapted from Net::OpenID::Consumer, by Brad Fitzpatrick. See:

    http://code.sixapart.com/svn/openid/trunk/perl/Net-OpenID-Consumer/lib/Net/OpenID/VerifiedIdentity.pm

    Args:
      openid_url: string

    Returns:
      string
    """
    if not openid_url:
      return 'None'

    username_re = '[\w.+-]+'

    scheme, host, path, params, query, frag = urlparse.urlparse(openid_url)

    def sanitize(display_name):
      if '@' in display_name:
        # don't display full email addresses; use just the user name part
        display_name = display_name[:display_name.index('@')]
      return display_name

    # is the username in the params?
    match = re.search('(u|id|user|userid|user_id|profile)=(%s)' % username_re,
                      path)
    if match:
      return sanitize(match.group(2))

    # is the username in the path?
    path = path.split('/')
    if re.match(username_re, path[-1]):
      return sanitize(path[-1])

    # use the hostname
    host = host.split('.')
    if len(host) == 1:
      return host[0]

    # strip common tlds and country code tlds
    common_tlds = ('com', 'org', 'net', 'edu', 'info', 'biz', 'gov', 'mil')
    if host[-1] in common_tlds or len(host[-1]) == 2:
      host = host[:-1]
    if host[-1] == 'co':
      host = host[:-1]

    # strip www prefix
    if host[0] == 'www':
      host = host[1:]

    return sanitize('.'.join(host))


class FrontPage(Handler):
  """Show the default front page."""
  def get(self):
    self.render()


class LoginHandler(Handler):
  """Handles a POST response to the OpenID login form."""

  def post(self):
    """Handles login requests."""
    logging.info(self.args_to_dict())
    openid_url = self.request.get('openid')
    if not openid_url:
      self.report_error('Please enter an OpenID URL.')
      return

    logging.debug('Beginning discovery for OpenID %s' % openid_url)
    try:
      consumer = self.get_consumer()
      if not consumer:
        return
      auth_request = consumer.begin(openid_url)
    except discover.DiscoveryFailure, e:
      self.report_error('Error during OpenID provider discovery.', e)
      return
    except discover.XRDSError, e:
      self.report_error('Error parsing XRDS from provider.', e)
      return

    self.session.claimed_id = auth_request.endpoint.claimed_id
    self.session.server_url = auth_request.endpoint.server_url
    self.session.store_and_display = self.request.get('display', 'no') != 'no'
    self.store_session()

    sreg_request = sreg.SRegRequest(optional=['nickname', 'fullname', 'email'])
    auth_request.addExtension(sreg_request)

    pape_request = pape.Request([pape.AUTH_MULTI_FACTOR,
                                 pape.AUTH_MULTI_FACTOR_PHYSICAL,
                                 pape.AUTH_PHISHING_RESISTANT,
                                 ])
    auth_request.addExtension(pape_request)

    parts = list(urlparse.urlparse(self.request.uri))
    parts[2] = 'finish'
    parts[4] = 'session_id=%d' % self.session.key().id()
    parts[5] = ''
    return_to = urlparse.urlunparse(parts)
    realm = urlparse.urlunparse(parts[0:2] + [''] * 4)

    redirect_url = auth_request.redirectURL(realm, return_to)
    logging.debug('Redirecting to %s' % redirect_url)
    self.response.set_status(302)
    self.response.headers['Location'] = redirect_url


class FinishHandler(Handler):
  """Handle a redirect from the provider."""
  def get(self):
    args = self.args_to_dict()
    consumer = self.get_consumer()
    if not consumer:
      return

    if self.session.login_set.get():
      self.render()
      return

    response = consumer.complete(args, self.request.uri)
    assert response.status in Login.status.choices

    if response.status == 'success':
      sreg_data = sreg.SRegResponse.fromSuccessResponse(response).items()
      pape_data = pape.Response.fromSuccessResponse(response)
      self.session.claimed_id = response.endpoint.claimed_id
      self.session.server_url = response.endpoint.server_url
    elif response.status == 'failure':
      logging.error(str(response))

    logging.debug('Login status %s for claimed_id %s' %
                  (response.status, self.session.claimed_id))

    if self.session.store_and_display:
      login = Login(status=response.status,
                    claimed_id=self.session.claimed_id,
                    server_url=self.session.server_url,
                    session=self.session.key())
      login.put()

    self.render(locals())


# Map URLs to our RequestHandler subclasses above
_URLS = [
  ('/', FrontPage),
  ('/login', LoginHandler),
  ('/finish', FinishHandler),
]

def main(argv):
  application = webapp.WSGIApplication(_URLS, debug=_DEBUG)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main(sys.argv)
