# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List, Set, Tuple
import os
import sys
import getopt
from json import load as json_load
import hashlib
import shutil
import logging

from angularhostpagetemplate.engine import TagMapper, replace_tags

_log = logging.getLogger(__name__)


def _prepare_contained_folder(child_path, child_type_title, container_path, container_type_title):
	if not child_path.startswith(container_path):
		raise ValueError(f"{child_type_title} not resides in {container_type_title} folder: {child_path!r} not prefixed with {container_path!r}")
	if os.path.isdir(child_path):
		return
	os.makedirs(child_path)


def _get_file_digest(file_path, block_size=8192):
	m = hashlib.sha512()
	with open(file_path, "rb") as fp:
		buf = fp.read(block_size)
		while buf:
			m.update(buf)
			buf = fp.read(block_size)
	return m.hexdigest()


def _check_file_overwrite_need(dest_path, src_path):
	try:
		dest_size = os.path.getsize(dest_path)
		src_size = os.path.getsize(src_path)
		if dest_size != src_size:
			return (True, 'size mis-match', dest_size, src_size)
		dest_digest = _get_file_digest(dest_path)
		src_digest = _get_file_digest(src_path)
		if dest_digest != src_digest:
			return (True, 'digest mis-match', dest_digest, src_digest)
	except Exception as e:
		return (True, 'unreachable element', e, None)
	return (False, None, None, None)


class AngularHostPageTagMapper(TagMapper):
	def __init__(self, static_namespace, *args, **kwds):
		super().__init__(*args, **kwds)
		self.static_namespace = static_namespace.strip("/") + "/"

	def map_base_href(self, path):  # pylint: disable=unused-argument
		return "<base href=\"" + self.static_namespace + "\">"


def _transform_to_host_page_template(dest_path, src_path, static_namespace):
	tag_mapper = AngularHostPageTagMapper(static_namespace)
	with open(src_path, "r", encoding='utf-8') as fp:
		template_text = fp.read()
	result_code = replace_tags(template_text, tag_mapper)
	with open(dest_path, "w", encoding='utf-8') as fp:
		fp.write(result_code)


def _copy_nonsync_file(dest, src):
	is_need, reason_type, dest_factor, src_factor = _check_file_overwrite_need(dest, src)
	if is_need:
		_log.info("copy file from upstream: %s => %s (%s; src: %r, dest: %r)", src, dest, reason_type, src_factor, dest_factor)
		shutil.copyfile(src, dest)
	else:
		_log.info("file in upstream availabled in destination: %s == %s", src, dest)


class PullLocation:
	def __init__(self, project_name, template_name, upstream_path, upstream_hostpage_filename, skip_paths, *args, **kwds):
		super().__init__(*args, **kwds)
		self.project_name = project_name
		self.template_name = template_name
		self.upstream_path = upstream_path
		self.upstream_hostpage_filename = upstream_hostpage_filename
		self.skip_paths = skip_paths

	@property
	def param_tuple(self):
		return (
				self.project_name,
				self.template_name,
				self.upstream_path,
				self.upstream_hostpage_filename,
				self.skip_paths,
		)

	@classmethod
	def parse_config(cls, app_name, project_index, cmap):
		project_name = cmap.get("name", "[NO-NAME-PART-" + str(project_index) + "]")
		template_name = (app_name + os.sep + "index.html") if app_name else "index.html"
		template_name = cmap.get("template_name", template_name)
		upstream_path = cmap.get("dist_path")
		upstream_hostpage_filename = cmap.get("dist_hostpage_filename", "index.html")
		skip_paths = cmap.get("skip_paths", None)
		return cls(project_name, template_name, upstream_path, upstream_hostpage_filename, skip_paths)

	@classmethod
	def parse_configs(cls, app_name, cmaplist):
		pull_locations = []
		for idx, cmap in enumerate(cmaplist):
			aux = cls.parse_config(app_name, idx + 1, cmap)
			pull_locations.append(aux)
		return pull_locations

	def build_template_namespaced_abspath(self, template_folder_abspath):
		p = os.path.join(template_folder_abspath, self.template_name)
		p = os.path.abspath(p)
		return p

	def get_dist_folder(self):
		for root, dirs, files in os.walk(self.upstream_path):
			if self.upstream_hostpage_filename in files:
				return os.path.abspath(root)
			to_drop = tuple(filter(lambda x: (x[0] == '.'), dirs))
			for n in to_drop:
				dirs.remove(n)
		raise ValueError(("cannot reach folder contains host page file: "
							f"{self.upstream_hostpage_filename!r} at {self.upstream_path!r}(project-name={self.project_name!r})"))

	def build_skip_relpaths_set(self, upstream_abspath):
		if not self.skip_paths:
			return frozenset()
		result = set()
		for frag in self.skip_paths:
			p = os.path.abspath(os.path.join(upstream_abspath, frag.strip(os.sep)))
			relp = os.path.relpath(p, upstream_abspath)
			result.add(relp)
		return frozenset(result)

	def build_operation_callable(self, static_namespace: str, static_namespaced_abspath: str, template_folder_abspath: str) -> PullOperation:
		return PullOperation(static_namespace, static_namespaced_abspath, template_folder_abspath, *self.param_tuple)


class PullOperation(PullLocation):
	def __init__(self, static_namespace, static_namespaced_abspath, template_folder_abspath, *args, **kwds):
		super().__init__(*args, **kwds)
		self.static_namespace = static_namespace
		self.static_namespaced_abspath = static_namespaced_abspath
		self.template_folder_abspath = template_folder_abspath
		self.template_namespaced_abspath = self.build_template_namespaced_abspath(template_folder_abspath)
		self.upstream_abspath = self.get_dist_folder()
		self.expect_hostpage_abspath = os.path.abspath(os.path.join(self.upstream_abspath, self.upstream_hostpage_filename))
		self.skip_relpaths = self.build_skip_relpaths_set(self.upstream_abspath)

	def prepare_template_namespaced_folder(self):
		folder_path = os.path.dirname(self.template_namespaced_abspath)
		_prepare_contained_folder(folder_path, f"namespaced template folder of {self.project_name}", self.template_folder_abspath, "template folder")

	def assemble_static_namespaced_paths(self, walk_root, walk_frag):
		src_abspath = os.path.abspath(os.path.join(walk_root, walk_frag))
		res_relpath = os.path.relpath(src_abspath, self.upstream_abspath)
		dest_abspath = os.path.abspath(os.path.join(self.static_namespaced_abspath, res_relpath))
		return (src_abspath, res_relpath, dest_abspath)

	def _copy_walking_upstream_dirs(self, root, dirs):
		to_drop = []
		for d in dirs:
			_aux, rel, dest = self.assemble_static_namespaced_paths(root, d)
			if rel in self.skip_relpaths:
				to_drop.append(rel)
				continue
			_prepare_contained_folder(dest, f"static sub-folder for {self.project_name}", self.static_namespaced_abspath, "static namespaced folder")
			yield rel
		for d in to_drop:
			dirs.remove(d)

	def _copy_walking_upstream_files(self, root, files):
		for f in files:
			src, rel, dest = self.assemble_static_namespaced_paths(root, f)
			if rel in self.skip_relpaths:
				continue
			if src == self.expect_hostpage_abspath:
				_transform_to_host_page_template(self.template_namespaced_abspath, src, self.static_namespace)
			else:
				_copy_nonsync_file(dest, src)
				yield rel

	def copy_from_upstream(self):
		seem_dirs = []
		seem_files = []
		for root, dirs, files in os.walk(self.upstream_abspath):
			seem_dirs.extend(self._copy_walking_upstream_dirs(root, dirs))
			seem_files.extend(self._copy_walking_upstream_files(root, files))
		return (seem_dirs, seem_files)

	def __call__(self) -> Tuple[List[str], List[str], Set[str]]:
		self.prepare_template_namespaced_folder()
		seem_dirs, seem_files = self.copy_from_upstream()
		return (seem_dirs, seem_files, self.skip_relpaths)


class PullDist:
	def __init__(self, app_path, static_folder, static_namespace, template_folder, pull_locations, delete_missing_files, *args, **kwds):
		super().__init__(*args, **kwds)
		self.app_path = app_path
		self.static_folder = static_folder
		self.static_namespace = static_namespace
		self.template_folder = template_folder
		self.pull_locations = pull_locations
		self.delete_missing_files = delete_missing_files
		self._cached_static_namespaced_abspath = None

	@classmethod
	def build_via_config(cls, cfg_path):
		with open(cfg_path, "r", encoding='utf-8') as fp:
			cmap = json_load(fp)
		app_path = cmap.get("app_path", None)
		app_name = os.path.basename(app_path.rstrip(os.sep)) if app_path else None
		static_folder = cmap.get("static_folder", "static")
		static_namespace = cmap.get("static_namespace", app_name)
		template_folder = cmap.get("template_folder", "angularhostpages")
		if not app_path:
			raise ValueError("app_path is required")
		if app_path[0] != os.sep:
			app_path = os.path.join(os.path.dirname(os.path.abspath(cfg_path)), app_path)
			_log.info("application-path: %r", app_path)
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

	def get_pull_location_via_project_name(self, project_name: str) -> PullLocation:
		for pull_loc in self.pull_locations:
			if pull_loc.project_name == project_name:
				return pull_loc
		return None

	def set_upstream_path(self, project_name, dist_path):
		if not project_name:
			if len(self.pull_locations) != 1:
				raise ValueError("there are multiple upstreams, name for pulling from is required.")
			pull_loc = self.pull_locations[0]
		else:
			pull_loc = self.get_pull_location_via_project_name(project_name)
			if not pull_loc:
				raise KeyError(f"cannot found project named {project_name!r} to pull host page from")
		pull_loc.upstream_path = dist_path

	@property
	def app_abspath(self):
		return os.path.abspath(self.app_path)

	def _prepare_sub_folder(self, sub_folder_path, sub_folder_type_title):
		_prepare_contained_folder(sub_folder_path, sub_folder_type_title, self.app_abspath, "app")

	@property
	def static_namespaced_abspath(self):
		if self._cached_static_namespaced_abspath is None:
			path_frags = [self.app_path, self.static_folder]
			if self.static_namespace:
				path_frags.append(self.static_namespace)
			aux = os.path.abspath(os.path.join(*path_frags))
			self._cached_static_namespaced_abspath = aux
		return self._cached_static_namespaced_abspath

	def prepare_static_namespaced_path(self):
		self._prepare_sub_folder(self.static_namespaced_abspath, "static folder")

	@property
	def template_abspath(self):
		path_frags = [self.app_path, self.template_folder]
		return os.path.abspath(os.path.join(*path_frags))

	def prepare_template_path(self):
		self._prepare_sub_folder(self.template_abspath, "template folder")

	def get_static_namespaced_paths(self, walk_root, walk_frag):
		res_abspath = os.path.abspath(os.path.join(walk_root, walk_frag))
		res_relpath = os.path.relpath(res_abspath, self.static_namespaced_abspath)
		return (res_abspath, res_relpath)

	def _walk_for_missing_dirs(self, seem_dirs, skip_relpaths, root, dirs):
		to_drop = []
		for d in dirs:
			abs_p, rel_p = self.get_static_namespaced_paths(root, d)
			if rel_p in seem_dirs:
				continue
			to_drop.append(d)
			if rel_p in skip_relpaths:
				_log.info("found folder in skip list: %r", rel_p)
				continue
			yield abs_p
			_log.info("found folder no longer in upstream: %r", rel_p)
		for d in to_drop:
			dirs.remove(d)

	def _walk_for_missing_files(self, seem_files, skip_relpaths, root, files):
		for f in files:
			abs_p, rel_p = self.get_static_namespaced_paths(root, f)
			if rel_p in seem_files:
				continue
			if rel_p in skip_relpaths:
				_log.info("found folder in skip list: %r", rel_p)
				continue
			yield abs_p
			_log.info("found file no longer in upstream: %r", rel_p)

	def remove_missing_file_entries(self, seem_dirs, seem_files, skip_relpaths):
		dir_to_del = []
		file_to_del = []
		for root, dirs, files in os.walk(self.static_namespaced_abspath):
			dir_to_del.extend(self._walk_for_missing_dirs(seem_dirs, skip_relpaths, root, dirs))
			file_to_del.extend(self._walk_for_missing_files(seem_files, skip_relpaths, root, files))
		for aux in dir_to_del:
			shutil.rmtree(aux)
		for aux in file_to_del:
			os.unlink(aux)

	def pull_files(self):
		pull_ops = []
		seem_dirs = set()
		seem_files = set()
		skip_relpaths = set()
		for pull_loc in self.pull_locations:
			pull_op = pull_loc.build_operation_callable(self.static_namespace, self.static_namespaced_abspath, self.template_abspath)
			pull_ops.append(pull_op)
		for pull_op in pull_ops:
			saw_dirs, saw_files, skipped_relpaths = pull_op()
			seem_dirs.update(saw_dirs)
			seem_files.update(saw_files)
			skip_relpaths.update(skipped_relpaths)
		if self.delete_missing_files:
			self.remove_missing_file_entries(seem_dirs, seem_files, skip_relpaths)
		_log.info("SUCCESS: pull operation completed.")


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
	except getopt.GetoptError as e:
		_log.exception("failed on parsing command line options")
		raise SystemExit(2) from e
	for opt, arg in opts:
		if opt in ("-h", "--help"):
			print(_HELP_MESSAGE)
			raise SystemExit
		if opt in ("-C", "--conf"):
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
