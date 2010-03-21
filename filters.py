import re
from google.appengine.ext import webapp

register = webapp.template.create_template_register()

def linkify(text):
  """Escape tags, add line breaks, and linkify HTTP URLs."""
  if not text:
    return ""
  text = text.replace('<', '&lt;').replace('>', '&gt;').replace("\n", '<br/>\n')
  text = re.sub(r'\b(https?://[\w\-\/\?\&\=\.\:\%\#]+)',
                lambda x: "<a href='%s'>%s</a>" % (x.group(1), x.group(1)),
                text)
  return text

register.filter(linkify)

