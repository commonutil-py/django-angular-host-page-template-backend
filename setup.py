# -*- coding: utf-8 -*-
""" Setup script for Angular Host-page Template Backend and Utility for Django """

from setuptools import setup

setup(
		name="django-angular-host-page-template-backend",
		version="0.1.2",  # REV-CONSTANT:rev 5d022db7d38f580a850cd995e26a6c2f
		description="Angular Host-page Template Backend and Utility for Django",
		packages=[
				"angularhostpagetemplate",
				"angularhostpagetemplate.tool",
		],
		classifiers=[
				'Development Status :: 5 - Production/Stable',
				'Intended Audience :: Developers',
				'License :: OSI Approved :: MIT License',
				'Programming Language :: Python :: 2.7',
				'Framework :: Django :: 1.11',
		],
		license='MIT License',
)

# vim: ts=4 sw=4 ai nowrap
