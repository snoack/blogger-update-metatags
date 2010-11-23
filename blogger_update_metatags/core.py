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


def html2text(text):
	output = []
	for line in re.split(r'\s*<br(?:[\s/][^>]*)?>\s*', text):
		output.append(re.sub(r'\s+', ' ', re.compile(r'<.*?>', re.S).sub('', line).strip()))
	return '\n'.join(output)

def node2text(node):
	text = node['$t']
	if node.get('type') != 'html':
		return text
	return str(BeautifulSoup(html2text(text), convertEntities=BeautifulSoup.ALL_ENTITIES))

class Error(Exception):
	pass

class Session(object):
	def __init__(self, email, password):
		self.browser = mechanize.Browser()

		# Login at the Blogger startpage.
		self.browser.open('https://www.google.com/accounts/ServiceLoginAuth')
		self.browser.select_form(nr=0)
		self.browser['Email'] = email
		self.browser['Passwd'] = password
		resp = self.browser.submit()

		# Check whether we were redirected to the dashboard.
		if urlparse.urlparse(resp.geturl())[2] == '/accounts/ManageAccount':
			return

		# Find the error message.
		soup = BeautifulSoup(resp.get_data(), convertEntities=BeautifulSoup.ALL_ENTITIES)
		raise Error(html2text(str(soup.find(attrs={'class': 'errormsg'}))))
	
	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, exc_traceback):
		self.close()

	def close(self):
		self.browser.open('http://www.blogger.com/logout.g')
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
		self.url = url

		# Download the summarized feed for the blog.
		resp = self.session.browser.open(url + '/feeds/posts/summary/?alt=json')
		feed = simplejson.loads(resp.get_data())['feed']

		# Get the blog id.
		self.id = node2text(feed['id']).split(':')[-1].split('-')[-1]

		# Collect the description and tags for all posts.
		self.pages = []
		all_tags   = []

		for entry in feed['entry']:
			for link in entry['link']:
				if link['rel'] == 'alternate':
					url = link['href']
					break
			else:
				continue

			desc = re.split(r'(?:\r\n?|(?<!\r)\n){2}', node2text(entry['summary']))[0]	# Only the first paragraph.
			tags = [c['term'] for c in entry.get('category', [])]

			self.pages.append((url, desc, tags))
			all_tags.extend(tags)

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
				output.append('  <meta name="description" content="%s"/>' % description.replace('"', '&quot;'))
			if tags:
				output.append('  <meta name="keywords" content="%s"/>' % ', '.join(tags).replace('"', '&quot;'))
			output.append('</b:if>')

		# Update the meta tags in the template.
		resp = self.session.browser.open('http://www.blogger.com/html?blogID=' + self.id)
		soup = BeautifulSoup(resp.get_data(), convertEntities=BeautifulSoup.ALL_ENTITIES)

		regex = re.compile(r'(?<=%s).*(?=%s)' % (BEGIN_COMMENT, END_COMMENT), re.S)
		templ = soup.find(id='templateText').string

		if regex.search(templ):
			templ = regex.sub('\n%s\n' % '\n'.join(output), templ)
		else:
			regex = re.compile(r'(?=\s*(?:<b:skin>|</head>))', re.I)
			templ = regex.sub('\n\n%s\n%s\n%s' % (BEGIN_COMMENT, '\n'.join(output), END_COMMENT), templ, 1)

		self.session.browser.select_form('templateEdit')
		self.session.browser['templateText'] = templ
		resp = self.session.browser.submit()

		# Look for a possible error message.
		soup = BeautifulSoup(resp.get_data(), convertEntities=BeautifulSoup.ALL_ENTITIES)
		errmsg = soup.find(id='error-message')

		if not errmsg:
			return
		raise Error(html2text(str(errmsg)))
