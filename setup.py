#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup viktor.
"""
import os
import versioneer
from setuptools import setup, find_packages


here_dir = os.path.abspath(os.path.dirname(__file__))
init_fp = os.path.join(here_dir, *['viktor', '__init__.py'])

setup_args = {
    'name': 'viktor',
    'version': versioneer.get_version(),
    'cmdclass': versioneer.get_cmdclass(),
    'license': 'MIT',
    'description': 'A bot for Slack',
    'url': 'https://github.com/barretobrock/viktor',
    'author': 'Barret Obrock',
    'author_email': 'barret@barretobrock.ee',
    'packages': find_packages(exclude=['tests']),
    'dependency_links': [
        'https://github.com/barretobrock/slacktools/tarball/master#egg=slacktools'
    ],
    'install_requires': [
        'slacktools',
        'flask==1.1.1'
        'slackeventsapi==2.1.0'
    ],

}

setup(**setup_args)
