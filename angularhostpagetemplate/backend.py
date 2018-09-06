# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import io
import errno

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template.backends.base import BaseEngine
from django.template import Origin, TemplateDoesNotExist
from django.utils.encoding import iri_to_uri
from django.utils.six.moves.urllib.parse import quote, urljoin  # pylint: disable=import-error

from angularhostpagetemplate.engine import TagMapper, replace_tags


def _simple_static_url_wrapper(path):
	prefix = iri_to_uri(getattr(settings, "STATIC_URL", ''))
	return urljoin(prefix, quote(path))


def get_static_url_wrapper():
	if apps.is_installed('django.contrib.staticfiles'):
		from django.contrib.staticfiles.storage import staticfiles_storage
		return staticfiles_storage.url
	return _simple_static_url_wrapper


class AngularHostPageTemplate(BaseEngine, TagMapper):
	app_dirname = 'angularhostpages'

	def __init__(self, params):
		params = params.copy()
		options = params.pop('OPTIONS').copy()
		if options:
			raise ImproperlyConfigured("Unknown options: {}".format(", ".join(options)))
		super(AngularHostPageTemplate, self).__init__(params)
		self.static_url_wrapper = get_static_url_wrapper()

	def map_base_href(self, path):
		return "<base href=\"" + self.static_url_wrapper(path) + "\">"

	def from_string(self, template_code):
		return Template(template_code, self)

	def get_template(self, template_name):
		tried = []
		for template_file in self.iter_template_filenames(template_name):
			try:
				with io.open(template_file, encoding=settings.FILE_CHARSET) as fp:
					template_code = fp.read()
			except IOError as e:
				if e.errno == errno.ENOENT:
					tried.append((
							Origin(template_file, template_name, self),
							'Host page file not exist',
					))
					continue
				raise
			return Template(template_code, self)
		raise TemplateDoesNotExist(template_name, tried=tried, backend=self)


class Template(object):
	def __init__(self, template_code, tag_mapper):
		self.result_code = replace_tags(template_code, tag_mapper)

	def render(self, context=None, request=None):  # pylint: disable=unused-argument
		return self.result_code
