# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bitergia
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
#   Alvaro del Castillo San Felix <acs@bitergia.com>
#

import json
import logging
import os.path

from time import sleep

from ..backend import Backend, BackendCommand, metadata
from ..cache import Cache
from ..errors import CacheError
from ..utils import DEFAULT_DATETIME, str_to_datetime, urljoin

logger = logging.getLogger(__name__)

def get_update_time(item):
    """Extracts the update time from a Hello item"""
    return None

class Hello(Backend):
    """Hello sample backend for Perceval.

    This class allows the fetch hello messages (hellos).

    :param name: Hello to this name
    :param cache: Hello messages already retrieved in cache
    """
    version = '0.1.0'

    def __init__(self, name, cache=None):
        super().__init__(name, cache=cache)
        self.client = HelloClient(name)

    @metadata(get_update_time)
    def fetch(self):
        """Fetch the hellos from the system.

        :returns: a generator of hellos
        """

        self._purge_cache_queue()

        hellos = self.client.get_hellos()

        for raw_hello in hellos:
            self._push_cache_queue(raw_hello)
            self._flush_cache_queue()
            hello = json.loads(raw_hello)
            yield hello

    @metadata(get_update_time)
    def fetch_from_cache(self):
        """Fetch the hellos from the cache.

        :returns: a generator of hellos

        :raises CacheError: raised when an error occurs accessing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        cache_items = self.cache.retrieve()

        hellos = None

        for raw_hello in cache_items:
            hello = json.loads(raw_hello)
            yield hello


class HelloClient:
    """ Client for retieving hellos """

    _max_hellos = 10  # Max number of hellos to return

    def __init__(self, name):
        self.name = name

    def get_hellos(self, start=None):
        """ Return the hellos """

        for i in range(1, self._max_hellos):
            hello_msg = "Hello %s from Perceval backed %i" % (self.name, i)
            hello_msg_json_str = '{"message": "%s"}' % (hello_msg)
            sleep(0.5)  # To simulate a delay in no cache generation
            yield hello_msg_json_str

class HelloCommand(BackendCommand):
    """Class to run Hello backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)
        self.name = self.parsed_args.name
        self.outfile = self.parsed_args.outfile

        if not self.parsed_args.no_cache:
            if not self.parsed_args.cache_path:
                base_path = os.path.expanduser('~/.perceval/cache/')
            else:
                base_path = self.parsed_args.cache_path
            # All hellos goes to the same cache file
            cache_path = os.path.join(base_path, "hellos", self.name)

            cache = Cache(cache_path)

            if self.parsed_args.clean_cache:
                cache.clean()
            else:
                cache.backup()
        else:
            cache = None

        self.backend = Hello(self.name, cache=cache)

    def run(self):
        """Fetch and print the hellos.

        This method runs the backend to fetch the hellos from system.
        Hellos are converted to JSON objects and printed to the
        defined output.
        """
        if self.parsed_args.fetch_cache:
            hellos = self.backend.fetch_from_cache()
        else:
            hellos = self.backend.fetch()

        try:
            for hello in hellos:
                obj = json.dumps(hello, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            if self.backend.cache:
                self.backend.cache.recover()
            raise RuntimeError(str(e))

    @classmethod
    def create_argument_parser(cls):
        """Returns the Hello argument parser."""

        parser = super().create_argument_parser()

        # Hello options
        group = parser.add_argument_group('Hello arguments')

        group.add_argument("--name", required=True,
                           help="name to Hello")

        return parser
