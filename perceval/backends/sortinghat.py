# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Authors:
#     Alvaro del Castillo <acs@bitergia.com>
#


import json
import logging

import requests


from ..backend import Backend, BackendCommand, metadata

from ..utils import str_to_datetime


logger = logging.getLogger(__name__)


class SortingHat(Backend):
    """SortingHat backend for Perceval.

    This class retrieves the uidentities from a SortingHat exported JSON
    uidentities file.

    :param url: SortingHat exported JSON uidentities file URL
    :param cache: cache object to store raw data
    """
    version = '0.1.0'

    def __init__(self, url=None, tag=None, cache=None):
        origin = url

        super().__init__(origin, tag=tag, cache=cache)
        self.url = url

        self.client = SortingHatClient(url)


    @metadata
    def fetch(self):
        """Fetch items from the SortingHat file.

        The method retrieves, from a SortingHat file URL the uidentities.

        :returns: a generator of items
        """
        logger.info("Loading uidentities from %s", self.url)

        nitems = 0  # number of items processed

        for uidentity in self.client.get_uidentities():
            yield uidentity
            nitems += 1

        logger.info("Total number of uidentities: %i ", nitems)

    @classmethod
    def has_caching(cls):
        """Returns whether it supports caching items on the fetch process.

        :returns: this backend supports items cache
        """
        return False

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return False

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a SortingHat uidentity."""
        return str(item['uuid'])

    @staticmethod
    def metadata_updated_on(item):
        """ SortingHat has no date information about
            when uidentities were added """

        ts = item['updated']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a SortingHat item.

        This backend only generates one type of item which is
        'uidentity'.
        """
        return 'uidentity'

class SortingHatClient:
    """SortingHat API client.

    In this simple backend, we don't use yet the SH API at all.

    :param url: URL of SortingHat file

    :raises
    """

    def __init__(self, url):
        self.url = url

    def get_uidentities(self):
        """Retrieve all uidentities from a JSON file """

        with open(self.url) as f:
            data = json.load(f)
            updated = data['time']
            uidentities = data['uidentities']

            for uidentity in uidentities.keys():
                item = uidentities[uidentity]
                item['updated'] = updated
                yield item

class SortingHatCommand(BackendCommand):
    """Class to run SortingHat backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)
        self.tag = self.parsed_args.tag
        self.url = self.parsed_args.url
        self.backend = SortingHat(self.url, tag=self.tag, cache=None)
        self.outfile = self.parsed_args.outfile

    def run(self):
        """Fetch and print the items.

        This method runs the backend to fetch the items of a given url.
        Items are converted to JSON objects and printed to the
        defined output.
        """
        items = self.backend.fetch()

        try:
            for item in items:
                obj = json.dumps(item, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(str(e.response.json()))
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            if self.backend.cache:
                self.backend.cache.recover()
            raise RuntimeError(str(e))

    @classmethod
    def create_argument_parser(cls):
        """Returns the SortingHat argument parser."""

        parser = super().create_argument_parser()

        # Remove --from-date argument from parent parser
        # because it is not needed by this backend
        action = parser._option_string_actions['--from-date']
        parser._handle_conflict_resolve(None, [('--from-date', action)])

        # SortingHat options
        group = parser.add_argument_group('SortingHat arguments')
        group.add_argument("url", nargs='?',
                           help="URL filepath with the SortingHat uidentities.")
        return parser
