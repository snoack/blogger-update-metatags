import sys
import os
import logging
import threading

import glib
import gobject
import gtk
import gtk.gdk

from blogger_update_metatags.core import DEFAULT_CONFIG_FILE
from blogger_update_metatags.helpers import process_config_file, process_blog, logger


class GtkListStoreHandler(logging.Handler):
	def __init__(self, store, *args, **kwargs):
		logging.Handler.__init__(self, *args, **kwargs)
		self.store = store

	def emit(self, record):
		if record.levelno >= logging.ERROR:
			icon = gtk.STOCK_DIALOG_ERROR
		elif record.levelno <= logging.INFO:
			icon = gtk.STOCK_DIALOG_INFO
		else:
			icon = gtk.STOCK_DIALOG_WARNING

		def append_to_store():
			self.store.append([icon, record.getMessage()])
		gobject.idle_add(append_to_store)

class Gui(object):
	def __init__(self):
		builder = gtk.Builder()

		if hasattr(sys ,'frozen'):
			from blogger_update_metatags import resources
			data = resources.GUI_XML
		else:
			try:
				import pkgutil
				data = pkgutil.get_data(__name__, 'gui.xml')
			except ImportError:
				from pkg_resources import get_provider, ResourceManager
				data = get_provider(__name__).get_resource_string(ResourceManager(), 'gui.xml')

		builder.add_from_string(data)
		builder.connect_signals(self)

		for obj in builder.get_objects():
			setattr(self, gtk.Buildable.get_name(obj), obj)

		if os.access(DEFAULT_CONFIG_FILE, os.R_OK):
			self.filechooserbutton.set_filename(DEFAULT_CONFIG_FILE)

		self.treeview_log.append_column(gtk.TreeViewColumn(None, gtk.CellRendererPixbuf(), stock_id=0))
		self.treeview_log.append_column(gtk.TreeViewColumn(None, gtk.CellRendererText(), text=1))

		self.dialog.show_all()

		logger.addHandler(GtkListStoreHandler(self.liststore_log))
	
	def _set_button_ok_sensitive(self):
		for frame in (self.frame_blog, self.frame_config):
			alignment, radio = frame.get_children()

			if not radio.get_active():
				continue
			
			children = [alignment]
			for child in children:
				if isinstance(child, gtk.Entry) and child.get_text().strip() == '':
					completed = False
					break

				if isinstance(child, gtk.FileChooserButton) and child.get_filename() is None:
					completed = False
					break

				if isinstance(child, gtk.Container):
					children.extend(child.get_children())
			else:
				completed = True

			self.button_ok.set_sensitive(completed)

	def on_toggled(self, radio):
		radio.parent.child.set_sensitive(radio.get_active())
		self._set_button_ok_sensitive()

	def on_change(self, entry):
		self._set_button_ok_sensitive()

	def on_entry_url_focus_out(self, entry, event):
		url = self.entry_url.get_text().strip()

		if url and '://' not in url:
			url = 'http://' + url

		self.entry_url.set_text(url)

	def on_file_set(self, chooser):
		self._set_button_ok_sensitive()

	def on_ok(self, button):
		self.liststore_log.clear()

		self.frame_blog.set_sensitive(False)
		self.frame_config.set_sensitive(False)
		self.button_ok.set_sensitive(False)

		if self.radiobutton_config.get_active():
			func = process_config_file
			args = (self.filechooserbutton.get_filename(),)
		else:
			func = process_blog
			args = (self.entry_url.get_text(), self.entry_email.get_text(), self.entry_password.get_text())

		finished = [False]

		def wrapper():
			func(*args)

			def on_finished():
				self.frame_blog.set_sensitive(True)
				self.frame_config.set_sensitive(True)
				self.button_ok.set_sensitive(True)

				self.progressbar.set_fraction(0)

				finished[0] = True
			glib.idle_add(on_finished, priority=glib.PRIORITY_HIGH)
		threading.Thread(target=wrapper).start()

		def update_progressbar():
			if not finished[0]:
				self.progressbar.pulse()
				return True
		gobject.timeout_add(75, update_progressbar)

	def on_quit(self, button):
		gtk.main_quit()

	def on_delete(self, dialog, event):
		gtk.main_quit()

	def main(self):
		gtk.gdk.threads_init()
		gtk.gdk.threads_enter()

		gtk.main()

		gtk.gdk.threads_leave()
