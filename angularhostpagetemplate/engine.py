# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Iterable, Tuple
import re

TRAP_BASEHREF = re.compile(r'<base\s+href\s*=\s*"([^"]*)"\s*/?\s*>', re.IGNORECASE)


class TagMapper:
	def impl_map_tag(self, tag_type, *args, **kwds):
		callable_name = "map_" + tag_type
		f = getattr(self, callable_name, None)
		if f:
			return f(*args, **kwds)
		return None


def map_base_href(template_text: str, tag_mapper: TagMapper) -> Iterable[Tuple[bool, str]]:
	aux = TRAP_BASEHREF.split(template_text)
	if not aux:
		return
	for idx, txt in enumerate(aux):
		if (idx & 1) == 0:
			yield (False, txt)
		else:
			yield (True, tag_mapper.impl_map_tag("base_href", txt))


def apply_map_callables(template_text, tag_mapper, callable_1, *remain_callables):
	for mapped, txt in callable_1(template_text, tag_mapper):
		if not txt:
			continue
		if mapped or (not remain_callables):
			yield txt
			continue
		for inner_txt in apply_map_callables(template_text, tag_mapper, *remain_callables):  # pylint: disable=no-value-for-parameter
			yield inner_txt


def replace_tags(template_text: str, tag_mapper: TagMapper) -> str:
	fragments = list(apply_map_callables(template_text, tag_mapper, map_base_href))
	return ''.join(fragments)
