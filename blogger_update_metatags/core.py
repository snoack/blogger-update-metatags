#!/usr/bin/env python

import os
import re
import itertools
import urlparse

import mechanize
import simplejson
from BeautifulSoup import BeautifulSoup


DEFAULT_CONFIG_FILE = os.path.expanduser(os.path.join('~', '.config', 'blogger-update-metatags.conf'))

BEGIN_COMMENT = '<!-- BEGIN OF AUTO-GENERATED META TAGS -->'
END_COMMENT   = '<!-- END OF AUTO-GENERATED META TAGS -->'

MAX_RESULTS = 100


def html2text(text):
	output = []
	for line in re.split(r'\s*<br(?:[\s/][^>]*)?>\s*', text):
		output.append(re.sub(r'\s+', ' ', re.compile(r'<.*?>', re.S).sub('', line).strip()))
	return '\n'.join(output)

def node2text(node):
	text = node['$t']
	if node.get('type') != 'html':
		return text
	return unicode(BeautifulSoup(html2text(text), convertEntities=BeautifulSoup.ALL_ENTITIES))

def escape(s):
	return s.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')

class Error(Exception):
	pass

class Session(object):
	def __init__(self, email, password):
		self.browser = mechanize.Browser()

		# Login at the Blogger startpage.
		self.browser.open('https://www.google.com/accounts/ServiceLoginAuth')
		encoding = self.browser.encoding()
		self.browser.select_form(nr=0)
		self.browser['Email']  = isinstance(email,    unicode) and email.encode(encoding)    or email
		self.browser['Passwd'] = isinstance(password, unicode) and password.encode(encoding) or password
		resp = self.browser.submit()

		# Check whether we were redirected to the dashboard.
		if urlparse.urlparse(resp.geturl())[2] == '/accounts/ManageAccount':
			return

		# Find the error message.
		data = resp.get_data().decode(self.browser.encoding())
		soup = BeautifulSoup(data, convertEntities=BeautifulSoup.ALL_ENTITIES)
		raise Error(html2text(unicode(soup.find(attrs={'class': 'errormsg'}))))
	
	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, exc_traceback):
		self.close()

	def close(self):
		self.browser.open('https://www.google.com/accounts/Logout')
		self.browser.close()

class Variable(object):
	needs_quotes = False

	def __init__(self, name):
		self.name = name

	def __str__(self):
		return 'data:' + self.name

	def __repr__(self):
		return '%s(%r)' % (self.__class__.__name__, self.name)

class Blog(object):
	def __init__(self, session, url):
		self.session = session
		self.url     = url
		self.pages   = []

		all_tags = []

		for i in itertools.count():
			# Fetch the summarized feed for up to MAX_RESULTS blog posts.
			resp = self.session.browser.open(urlparse.urljoin(url, 'feeds/posts/summary/?alt=json&max-results=%d&start-index=%d' % (MAX_RESULTS, MAX_RESULTS * i + 1)))
			feed = simplejson.loads(resp.get_data().decode(self.session.browser.encoding()))['feed']

			# Collect the description and tags for the fetched posts.
			for entry in feed['entry']:
				for link in entry['link']:
					if link['rel'] == 'alternate':
						break
				else:
					continue

				desc = re.split(r'(?:\r\n?|(?<!\r)\n){2}', node2text(entry['summary']))[0]	# Only the first paragraph.
				tags = [c['term'] for c in entry.get('category', [])]

				self.pages.append((link['href'], desc, tags))
				all_tags.extend(tags)

			if len(feed['entry']) < MAX_RESULTS:
				break

		# Get the blog id.
		self.id = node2text(feed['id']).split(':')[-1].split('-')[-1]

		# Get the description and tags for the homepage. The most
		# popular/relevant tags are used for the homepage.
		popular_tags = []
		for n, tags in itertools.groupby(sorted(set(all_tags), key=all_tags.count, reverse=True), all_tags.count):
			popular_tags.extend(sorted(tags))
			if len(popular_tags) >= 5:
				break

		self.pages.insert(0, (Variable('blog.homepageUrl'), node2text(feed['subtitle']), popular_tags))

	def update_meta_tags(self):
		# Build the template code for generating the meta tags.
		output = []
		for url, description, tags in self.pages:
			if getattr(url, 'needs_quotes', True):
				url = '"%s"' % url
			output.append("<b:if cond='data:blog.url == %s'>" % url)
			if description:
				output.append('  <meta name="description" content="%s"/>' % escape(description))
			if tags:
				output.append('  <meta name="keywords" content="%s"/>' % escape(', '.join(tags)))
			output.append('</b:if>')

		# Update the meta tags in the template.
		resp = self.session.browser.open('http://www.blogger.com/html?blogID=' + self.id)
		encoding = self.session.browser.encoding()
		data = resp.get_data().decode(encoding)
		soup = BeautifulSoup(data, convertEntities=BeautifulSoup.ALL_ENTITIES)

		regex = re.compile(r'(?<=%s).*(?=%s)' % (BEGIN_COMMENT, END_COMMENT), re.S)
		templ = soup.find(id='templateText').string

		if regex.search(templ):
			templ = regex.sub('\n%s\n' % '\n'.join(output), templ)
		else:
			regex = re.compile(r'(?=\s*(?:<b:skin>|</head>))', re.I)
			templ = regex.sub('\n\n%s\n%s\n%s' % (BEGIN_COMMENT, '\n'.join(output), END_COMMENT), templ, 1)

		self.session.browser.select_form('templateEdit')
		self.session.browser['templateText'] = templ.encode(encoding)
		resp = self.session.browser.submit()

		# Look for a possible error message.
		data = resp.get_data().decode(self.session.browser.encoding())
		soup = BeautifulSoup(data, convertEntities=BeautifulSoup.ALL_ENTITIES)
		errmsg = soup.find(id='error-message')

		if not errmsg:
			return
		raise Error(html2text(unicode(errmsg)))
