#!/usr/bin/env python

import sys
import logging
from optparse import OptionParser

from blogger_update_metatags.core import DEFAULT_CONFIG_FILE
from blogger_update_metatags.helpers import process_config_file, logger

if __name__ == '__main__':
	parser = OptionParser('Usage: %prog [-c <config_file>] <blog1> [<blog2> [...]]\n'
	                      '       %prog [-c <config_file>] --all\n'
	                      '       %prog --gui')
	parser.add_option('-a', '--all', dest='all', action='store_true', help='update meta tags for all configured blogs')
	parser.add_option('-c', dest='config_file', help='specify a configuration file')
	parser.add_option('--gui', dest='gui', action='store_true', help='enable Gtk+ frontend')

	options, args = parser.parse_args()

	if options.gui:
		if args or options.all or options.config_file:
			print >>sys.stderr, 'You can not specify any blogs or configuration file, when enabling the gui.'
			sys.exit(1)

		try:
			import pygtk
			pygtk.require('2.0')
		except (ImportError, AssertionError):
			print >>sys.stderr, 'PyGTK (Python bindings for Gtk+) is not installed.'
			sys.exit(1)

		from blogger_update_metatags.gui import Gui
		sys.exit(Gui().main())

	if not args and not options.all:
		print >>sys.stderr, "You don't have specified any blogs."
		sys.exit(1)

	if args and options.all:
		print >>sys.stderr, "You can not specify a list of blogs when using --all."
		sys.exit(1)

	logger.addHandler(logging.StreamHandler(sys.stderr))
	sys.exit(process_config_file(filename=(options.config_file or DEFAULT_CONFIG_FILE), blogs=(None if options.all else args)))
