import sys
from distutils.core import setup

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
	  scripts=['blogger-update-metatags.py'])
