# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import sys
import getopt
from json import load as json_load
import logging

_log = logging.getLogger(__name__)


def _prepare_contained_folder(child_path, child_type_title, container_path, container_type_title):
	if not child_path.startswith(container_path):
		raise ValueError("%s not resides in %s folder: %r not prefixed with %r" % (
				child_type_title,
				container_type_title,
				child_path,
				container_path,
		))
	if os.path.isdir(child_path):
		return
	os.makedirs(child_path)


class PullLocation(object):
	def __init__(self, project_name, template_name, upstream_path, upstream_hostpage_filename, *args, **kwds):
		super(PullLocation, self).__init__(*args, **kwds)
		self.project_name = project_name
		self.template_name = template_name
		self.upstream_path = upstream_path
		self.upstream_hostpage_filename = upstream_hostpage_filename

	@classmethod
	def parse_config(cls, app_name, project_index, cmap):
		project_name = cmap.get("name", "[NO-NAME-PART-" + str(project_index) + "]")
		template_name = (app_name + os.sep + "index.html") if app_name else "index.html"
		template_name = cmap.get("template_name", template_name)
		upstream_path = cmap.get("dist_path")
		upstream_hostpage_filename = cmap.get("dist_hostpage_filename", "index.html")
		return cls(project_name, template_name, upstream_path, upstream_hostpage_filename)

	@classmethod
	def parse_configs(cls, app_name, cmaplist):
		pull_locations = []
		for idx, cmap in enumerate(cmaplist):
			aux = cls.parse_config(app_name, idx + 1, cmap)
			pull_locations.append(aux)
		return pull_locations


class PullDist(object):
	def __init__(self, app_path, static_folder, static_namespace, template_folder, pull_locations, delete_missing_files, *args, **kwds):
		super(PullDist, self).__init__(*args, **kwds)
		self.app_path = app_path
		self.static_folder = static_folder
		self.static_namespace = static_namespace
		self.template_folder = template_folder
		self.pull_locations = pull_locations
		self.delete_missing_files = delete_missing_files

	@classmethod
	def build_via_config(cls, cfg_path):
		with open(cfg_path, "r") as fp:
			cmap = json_load(fp)
		app_path = cmap.get("app_path", None)
		app_name = os.path.basename(app_path.rstrip(os.sep)) if app_path else None
		static_folder = cmap.get("static_folder", "static")
		static_namespace = cmap.get("static_namespace", app_name)
		template_folder = cmap.get("template_folder", "angularhostpages")
		if not app_path:
			raise ValueError("app_path is required")
		loc_cmap = cmap.get("pull_from")
		if loc_cmap:
			pull_locations = PullLocation.parse_configs(app_name, loc_cmap)
		else:
			aux = PullLocation.parse_config(app_name, 1, cmap)
			pull_locations = [
					aux,
			]
		delete_missing_files = bool(cmap.get("delete_missing_files", True))
		return cls(app_path, static_folder, static_namespace, template_folder, pull_locations, delete_missing_files)

	def set_upstream_path(self, project_name, dist_path):
		if not project_name:
			if len(self.pull_locations) > 1:
				raise ValueError("there are multiple upstreams, name for pulling from is required.")
			self.pull_locations[0].upstream_path = dist_path
		else:
			for pull_loc in self.pull_locations:
				if pull_loc == project_name:
					pull_loc.upstream_path = dist_path
					return
			raise KeyError("cannot found project named %r to pull host page from" % (project_name, ))

	@property
	def app_abspath(self):
		return os.path.abspath(self.app_path)

	def _prepare_sub_folder(self, sub_folder_path, sub_folder_type_title):
		_prepare_contained_folder(sub_folder_path, sub_folder_type_title, self.app_abspath, "app")

	@property
	def static_namespaced_abspath(self):
		path_frags = [self.app_path, self.static_folder]
		if self.static_namespace:
			path_frags.append(self.static_namespace)
		return os.path.abspath(os.path.join(*path_frags))

	def prepare_static_namespaced_path(self):
		self._prepare_sub_folder(self.static_namespaced_abspath, "static folder")

	@property
	def template_abspath(self):
		path_frags = [self.app_path, self.template_folder]
		return os.path.abspath(os.path.join(*path_frags))

	def prepare_template_path(self):
		self._prepare_sub_folder(self.template_abspath, "template folder")

	def pull_files(self):
		pass  # TODO: impl


_HELP_MESSAGE = """
Argument: [Options...] [PROJECT_NAME=ANGULAR_DIST_PATHS...]

Options:
	--help | -h
		Display help message.
	--conf=[CONFIG_PATH] | -C [CONFIG_PATH]
		Load configuration from given path.

""".replace("\t", "    ")


def parse_option(argv):
	cfg_path = ".angular-host-page-pull.json"
	try:
		opts, args = getopt.getopt(argv, "hC:", ["help", "conf="])
	except getopt.GetoptError:
		_log.exception("failed on parsing command line options")
		sys.exit(2)
		return None
	for opt, arg in opts:
		if opt in ("-h", "--help"):
			print _HELP_MESSAGE
			sys.exit()
			return None
		elif opt in ("-C", "--conf"):
			cfg_path = arg
	pull_instance = PullDist.build_via_config(os.path.abspath(cfg_path))
	for arg in args:
		aux = arg.split("=", 1)
		if len(aux) == 1:
			pull_instance.set_upstream_path(None, arg)
		else:
			pull_instance.set_upstream_path(aux[0], aux[1])
	return pull_instance


def main():
	logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
	pull_instance = parse_option(sys.argv[1:])
	pull_instance.pull_files()
	return 0


if __name__ == "__main__":
	sys.exit(main())
