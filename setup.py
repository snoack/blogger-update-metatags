import sys
from distutils.core import setup

if 'py2exe' in sys.argv:
	import os
	import re

	from distutils import log
	from distutils.errors import DistutilsError
	from distutils.command.build_py import build_py as _build_py

	from py2exe.build_exe import py2exe as _py2exe

	# Extending the build_py command (internally used by py2exe), to create a
	# submodule containing the package_data for each package that defines any.
	# This is required because of you can not bundle data files with py2exe.
	class build_py(_build_py):
		def build_package_data(self):
			for package, src_dir, build_dir, filenames in self.data_files:
				outfile = os.path.join(build_dir, 'resources.py')
				file = open(outfile, 'w')

				for filename in filenames:
					infile = os.path.join(src_dir, filename)

					log.info('adding %s to %s' % (infile, outfile))

					varname = re.sub(r'[^A-Za-z0-9]', '_', filename).upper()
					content = open(infile, 'rb').read().decode('raw_unicode_escape').encode('ascii', 'backslashreplace')

					file.write("%s = '''%s'''\n" % (varname, content))

				file.close()
				self.byte_compile([outfile])

	# Extend the py2exe command, to also include data files required by gtk+ and
	# enable the "MS-Windows" theme. In order to make gtk+ find the data files
	# we also ensure that the gtk+ libraries are not bundled.
	class py2exe(_py2exe):
		def create_binaries(self, py_files, extensions, dlls):
			gtk_dlls = []

			for libdir in os.environ['PATH'].split(os.path.pathsep):
				if not os.path.exists(os.path.join(libdir, 'libgtk-win32-2.0-0.dll')):
					continue

				for filename in os.listdir(libdir):
					dll = os.path.join(libdir, filename)

					if dll in dlls:
						gtk_dlls.append(dll)

			if not gtk_dlls:
				raise DistutilsError('could not find gtk+ to copy libraries and data files.')

			_py2exe.create_binaries(self, py_files, extensions, [l for l in dlls if l not in gtk_dlls])

			for dll in gtk_dlls:
				self.copy_file(dll, os.path.join(self.exe_dir, os.path.basename(dll)), preserve_mode=0)

			for subdir in ('lib', 'share', 'etc'):
				self.copy_tree(os.path.join(os.path.dirname(os.path.dirname(gtk_dlls[0])), subdir), os.path.join(self.exe_dir, subdir))

			log.info('enabling "MS-Windows" theme for gtk+')

			file = open(os.path.join(self.exe_dir, 'etc', 'gtk-2.0', 'gtkrc'), 'w')
			print >>file, 'gtk-theme-name = "MS-Windows"'
			file.close()

	kwargs = dict(windows=[{'script': 'blogger-update-metatags-py2exe.py', 'dest_base': 'blogger-update-metatags'}],
	              zipfile=None,
	              options={'py2exe': dict(includes=['cairo', 'gio', 'pango', 'pangocairo', 'atk'],
	                                      excludes=['pkgutil', 'pkg_resources'],
	                                      bundle_files=1,
	                                      optimize=2,
	                                      compressed=1)},
	              cmdclass={'build_py': build_py, 'py2exe': py2exe})
else:
	kwargs = dict(scripts=['blogger-update-metatags.py'])

setup(name='blogger-update-metatags',
      version='1.0',
      license='GPL',
      description='Generates and updates your meta tags on Blogger based on the feed.',
      author='Sebastian Noack',
      author_email='s.noack@placement24.com',
      classifiers=[
          'Topic :: Software Development :: Code Generators',
          'Topic :: Internet :: WWW/HTTP :: Site Management',
          'Intended Audience :: End Users/Desktop',
          'License :: OSI Approved :: GNU General Public License (GPL)',
          'Operating System :: POSIX',
          'Operating System :: Microsoft :: Windows',
          'Environment :: Console',
          'Environment :: X11 Applications :: GTK',
          'Environment :: Win32 (MS Windows)',
          'Programming Language :: Python :: 2',
          'Natural Language :: English',
          'Development Status :: 5 - Production/Stable',
      ],
      url='http://www.no-ack.org/2010/07/auto-generated-meta-tags-for-your-blog.html',
      packages=['blogger_update_metatags'],
      package_data={'blogger_update_metatags': ['gui.xml']},
      **kwargs)
