#!/usr/bin/python
#
# Copyright 2007, Google Inc.
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
An HTTPFetcher implementation that uses Google App Engine's urlfetch module.

HTTPFetcher is an interface defined in the top-level fetchers module in
  JanRain's OpenID python library: http://openidenabled.com/python-openid/

For more, see openid/fetchers.py in that library.
"""

import logging

from openid import fetchers
from google.appengine.api import urlfetch


class UrlfetchFetcher(fetchers.HTTPFetcher):
  """An HTTPFetcher subclass that uses Google App Engine's urlfetch module.
  """
  def fetch(self, url, body=None, headers=None):
    """
    This performs an HTTP POST or GET, following redirects along
    the way. If a body is specified, then the request will be a
    POST. Otherwise, it will be a GET.

    @param headers: HTTP headers to include with the request
    @type headers: {str:str}

    @return: An object representing the server's HTTP response. If
      there are network or protocol errors, an exception will be
      raised. HTTP error responses, like 404 or 500, do not
      cause exceptions.

    @rtype: L{HTTPResponse}

    @raise Exception: Different implementations will raise
      different errors based on the underlying HTTP library.
    """
    if not fetchers._allowedURL(url):
      raise ValueError('Bad URL scheme: %r' % (url,))

    if not headers:
      headers = {}

    if body:
      method = urlfetch.POST
      if 'Content-Type' not in headers:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    else:
      method = urlfetch.GET

    if not headers:
      headers = {}

    # follow up to 10 redirects
    for i in range(10):
      resp = urlfetch.fetch(url, body, method, headers)
      if resp.status_code in (301, 302):
        logging.debug('Following %d redirect to %s' %
                      (resp.status_code, resp.headers['location']))
        url = resp.headers['location']
      else:
        break

    return fetchers.HTTPResponse(url, resp.status_code, resp.headers,
                                 resp.content)
