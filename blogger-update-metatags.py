#!/usr/bin/env python

import os
import re
import sys
import itertools
import urlparse
from optparse import OptionParser
from ConfigParser import ConfigParser, NoOptionError, NoSectionError

import mechanize
import simplejson
from BeautifulSoup import BeautifulSoup


BEGIN_COMMENT = '<!-- BEGIN OF AUTO-GENERATED META TAGS -->'
END_COMMENT = '<!-- END OF AUTO-GENERATED META TAGS -->'


def html2text(text):
	output = []
	for line in re.split(r'\s*<br(?:[\s/][^>]*)?>\s*', text):
		output.append(re.sub(r'\s+', ' ', re.compile(r'<.*?>', re.S).sub('', line)))
	return '\n'.join(output)

def node2text(node):
	text = node['$t']
	if node.get('type') != 'html':
		return text
	return str(BeautifulSoup(html2text(text), convertEntities=BeautifulSoup.ALL_ENTITIES))


class Error(Exception):
	pass

def print_error(e, indent='', fd=sys.stderr):
	import textwrap

	for s in str(e).splitlines():
		for line in textwrap.wrap(s, width=80,
		                             initial_indent=indent,
		                             subsequent_indent=indent + '  '):
			print >>fd, line


def blogger_login(browser, email, password):
	# Login at the Blogger startpage.
	browser.open('https://www.blogger.com/')
	browser.select_form(name='login')
	browser['Email'] = email
	browser['Passwd'] = password
	resp = browser.submit()

	# Check whether we were redirected to the dashboard.
	if urlparse.urlparse(resp.geturl())[2] == '/home':
		return

	# Find the error message.
	soup = BeautifulSoup(resp.get_data(), convertEntities=BeautifulSoup.ALL_ENTITIES)
	raise Error(html2text(str(soup.find(attrs={'class': 'errormsg'}))))

def blogger_logout(browser):
	browser.open('http://www.blogger.com/logout.g')


class Variable(object):
	needs_quotes = False

	def __init__(self, name):
		self.name = name

	def __str__(self):
		return 'data:' + self.name

	def __repr__(self):
		return '%s(%r)' % (self.__class__.__name__, self.name)

class Blog(object):
	def __init__(self, browser, url):
		self.browser = browser
		self.url = url

		# Download the summarized feed for the blog.
		resp = self.browser.open(url + '/feeds/posts/summary/?alt=json')
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
			tags = [c['term'] for c in entry['category']]

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
		resp = self.browser.open('http://www.blogger.com/html?blogID=' + self.id)
		soup = BeautifulSoup(resp.get_data(), convertEntities=BeautifulSoup.ALL_ENTITIES)

		regex = re.compile(r'(?<=%s).*(?=%s)' % (BEGIN_COMMENT, END_COMMENT), re.S)
		templ = soup.find(id='templateText').string

		if regex.search(templ):
			templ = regex.sub('\n%s\n' % '\n'.join(output), templ)
		else:
			regex = re.compile(r'(?=\s*(?:<b:skin>|</head>))', re.I)
			templ = regex.sub('\n\n%s\n%s\n%s' % (BEGIN_COMMENT, '\n'.join(output), END_COMMENT), templ, 1)

		self.browser.select_form('templateEdit')
		self.browser['templateText'] = templ
		resp = self.browser.submit()

		# Look for a possible error message.
		soup = BeautifulSoup(resp.get_data(), convertEntities=BeautifulSoup.ALL_ENTITIES)
		errmsg = soup.find(id='error-message')

		if not errmsg:
			return
		raise Error.from_html(html2text(str(errmsg)))

if __name__ == '__main__':
	parser = OptionParser('Usage: %prog [-c <config_file>] <blog1> [<blog2> [...]]\n'
	                      '       %prog [-c <config_file>] --all')
	parser.add_option('-a', '--all', dest='all', action='store_true',
	                  help='update meta tags for all configured blogs')
	parser.add_option('-c', dest='config_file',
	                  default=os.path.expanduser(os.path.join('~', '.config', os.path.splitext(os.path.basename(sys.argv[0]))[0] + '.conf')),
	                  help='specify a configuration file')
	options, args = parser.parse_args()

	if not args and not options.all:
		print >>sys.stderr, "You don't have specified any blogs."
		sys.exit(1)

	if args and options.all:
		print >>sys.stderr, "You can not specify a list of blogs when using --all."
		sys.exit(1)

	config = ConfigParser()
	if not config.read(options.config_file):
		print >>sys.stderr, 'Can not read config file (%s).' % options.config_file
		sys.exit(1)

	if options.all:
		args = [s[5:] for s in config.sections() if s.startswith('blog ')]

	sessions = {}
	try:
		for name in args:
			try:
				url  = config.get('blog ' + name, 'url')
				user = config.get('blog ' + name, 'user')

				try:
					browser = sessions[user]
				except KeyError:
					email    = config.get('user ' + user, 'email')
					password = config.get('user ' + user, 'password')

					browser = mechanize.Browser()

					try:
						try:
							blogger_login(browser, email, password)
						except:
							browser.close()
							raise
					except Error, e:
						print >>sys.stderr, "Skipping blog '%s'. Login failed." % name
						print_error(e, indent='  ')
						continue

					sessions[user] = browser
			except NoOptionError, e:
				print >>sys.stderr, "Skipping blog '%s'. No %s configured for %s." % (name, e.option, e.section.split()[0])
				continue
			except NoSectionError, e:
				print >>sys.stderr, "Skipping blog '%s'. The %s is not configured." % (name, e.section.split()[0])
				continue

			try:
				blog = Blog(browser, url)
				blog.update_meta_tags()
			except Error, e:
				print >>sys.stderr, "Skipping blog '%s'. Failed to update meta tags." % name
				print_error(e, indent='  ')
				continue

			print "Updated meta tags for blog '%s' (%s)." % (name, url)
	finally:
		for browser in sessions.itervalues():
			blogger_logout(browser)
			browser.close()
