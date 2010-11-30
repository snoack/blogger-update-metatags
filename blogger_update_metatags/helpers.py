#!/usr/bin/env python

import logging
from ConfigParser import ConfigParser, NoOptionError, NoSectionError, ParsingError

from blogger_update_metatags.core import Blog, Session, Error


logger = logging.getLogger('blogger-update-metatags')
logger.setLevel(logging.INFO)


def process_blog(url, email, password):
	try:
		with Session(email, password) as session:
			try:
				blog = Blog(session, url)
			except IOError:
				logger.error('Failed to fetch RSS feed. Possibly the URL of your blog is incorrect or its not powered at Blogger.')
				return 1

			blog.update_meta_tags()
	except Error, e:
		logger.error(unicode(e))
		return 1
	except IOError:
		logger.error('Failed to connect. Possibly you are offline.')
		return 1

	logger.info('Updated meta tags for blog, successful.')
		
def process_config_file(filename, blogs=None):
	config = ConfigParser()

	try:
		if not config.read(filename):
			logger.error('Can not open config file (%s).' % filename)
			return 1
	except ParsingError:
		logger.error('Can not parse config file (%s).' % filename)
		return 1

	if blogs is None:
		blogs = [s[5:] for s in config.sections() if s.startswith('blog ')]

	sessions = {}
	try:
		for name in blogs:
			try:
				url  = config.get('blog ' + name, 'url')
				user = config.get('blog ' + name, 'user')

				try:
					session = sessions[user]
				except KeyError:
					email    = config.get('user ' + user, 'email')
					password = config.get('user ' + user, 'password')

					try:
						session = Session(email, password)
					except Error, e:
						logger.warn("Skipping blog '%s'. Login failed.\n%s" % (name, e))
						continue

					sessions[user] = session
			except NoOptionError, e:
				logger.warn("Skipping blog '%s'. No %s configured for %s." % (name, e.option, e.section.split()[0]))
				continue
			except NoSectionError, e:
				logger.warn("Skipping blog '%s'. The %s is not configured." % (name, e.section.split()[0]))
				continue

			try:
				try:
					blog = Blog(session, url)
				except IOError:
					logger.warn("Skipping blog '%s'. Failed to fetch RSS feed. Possibly the URL of your blog is incorrect or its not powered at Blogger." % name)
					continue
				blog.update_meta_tags()
			except Error, e:
				logger.warn("Skipping blog '%s'. Failed to update meta tags.\n%s" % (name, e))
				continue

			logger.info("Updated meta tags for blog '%s' (%s)." % (name, url))
	except IOError:
		logger.error('Failed to connect. Possibly you are offline.')
		return 1
	finally:
		for sessions in sessions.itervalues():
			session.close()
