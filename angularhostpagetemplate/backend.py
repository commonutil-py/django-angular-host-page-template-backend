# -*- coding: utf-8 -*-

from urllib.parse import quote, urljoin

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template.backends.base import BaseEngine
from django.template import Origin, TemplateDoesNotExist
from django.utils.encoding import iri_to_uri

from angularhostpagetemplate.engine import TagMapper, replace_tags


def _simple_static_url_wrapper(path):
	prefix = iri_to_uri(getattr(settings, "STATIC_URL", ''))
	return urljoin(prefix, quote(path))


def get_static_url_wrapper():
	if apps.is_installed('django.contrib.staticfiles'):
		from django.contrib.staticfiles.storage import staticfiles_storage  # pylint: disable=import-outside-toplevel
		return staticfiles_storage.url
	return _simple_static_url_wrapper


class AngularHostPage(BaseEngine, TagMapper):
	app_dirname = 'angularhostpages'

	def __init__(self, params):
		params = params.copy()
		options = params.pop('OPTIONS').copy()
		if options:
			raise ImproperlyConfigured(f"Unknown options: {', '.join(options)}")
		super().__init__(params)
		self.static_url_wrapper = get_static_url_wrapper()

	def map_base_href(self, path):
		return "<base href=\"" + self.static_url_wrapper(path) + "\">"

	def from_string(self, template_code):
		return Template(template_code, self)

	def get_template(self, template_name):
		tried = []
		for template_file in self.iter_template_filenames(template_name):
			try:
				with open(template_file, encoding='utf-8') as fp:
					template_code = fp.read()
			except FileNotFoundError:
				tried.append((
						Origin(template_file, template_name, self),
						'Host page file not exist',
				))
			else:
				return Template(template_code, self)
		raise TemplateDoesNotExist(template_name, tried=tried, backend=self)


class Template:
	def __init__(self, template_code, tag_mapper):
		self.result_code = replace_tags(template_code, tag_mapper)

	def render(self, context=None, request=None):  # pylint: disable=unused-argument
		return self.result_code
