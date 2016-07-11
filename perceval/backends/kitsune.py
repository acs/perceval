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

import functools
import json
import logging
import os.path

import requests

from dateutil import parser

from ..backend import Backend, BackendCommand, metadata
from ..cache import Cache
from ..errors import BackendError, CacheError, ParseError

from ..utils import (DEFAULT_DATETIME,
                     datetime_to_utc,
                     str_to_datetime,
                     urljoin)


logger = logging.getLogger(__name__)

DEFAULT_OFFSET = 0
KITSUNE_URL = "https://support.mozilla.org"


def kitsune_metadata(func):
    """Kitsune metadata decorator.

    This decorator takes items overrides `metadata` decorator to add extra
    information related to Kitsune (offset).
    """
    @functools.wraps(func)
    def decorator(self, *args, **kwargs):
        offset = kwargs.get('offset', DEFAULT_OFFSET)
        # Normalize offset so it starts at page start
        offset = int(offset/KitsuneClient.QUESTIONS_PER_PAGE)*KitsuneClient.QUESTIONS_PER_PAGE

        for item in func(self, *args, **kwargs):
            item['offset'] = offset
            offset += 1
            yield item
    return decorator


class Kitsune(Backend):
    """Kitsune backend for Perceval.

    This class retrieves the questions and answers from a
    Kitsune url. To initialize this class a
    url could be provided. If not, https://support.mozilla.org will be used.

    :param url: Kitsune url
    :param cache: cache object to store raw data
    :param origin: identifier of the repository; when `None` or an
        empty string are given, it will be set to `url` value
    """
    version = '0.1.0'

    def __init__(self, url=None, cache=None, origin=None):
        if not url:
            url = KITSUNE_URL
        origin = origin if origin else url

        super().__init__(origin, cache=cache)
        self.url = url
        self.client = KitsuneClient(url)

    @kitsune_metadata
    @metadata
    def fetch(self, offset=DEFAULT_OFFSET):
        """Fetch questions from the Kitsune url.

        The method retrieves, from a Kitsune url, the
        questions.

        :offset: page from which start the fetching
        :returns: a generator of questions
        """

        logger.info("Looking for questions at url '%s' offset %s", self.url, offset)

        self._purge_cache_queue()

        nquestions = 0  # number of questions processed
        tquestions = 0  # number of questions from API data

        for raw_questions in self.client.get_questions(offset):
            self._push_cache_queue(raw_questions)
            questions_data = json.loads(raw_questions)

            try:
                logger.debug("Questions: %i/%i", nquestions, tquestions)
                tquestions = questions_data['count']
                questions = questions_data['results']
            except:
                cause = ("Bad JSON format for mozilla_questions: %s" % (questions_data))
                raise ParseError(cause=cause)

            for question in questions:
                yield question
                nquestions += 1

            self._flush_cache_queue()

        logger.info("Total number of questions: %i (%i total, %i offset)", nquestions, tquestions, offset)

    @kitsune_metadata
    @metadata
    def fetch_from_cache(self):
        """Fetch the questions from the cache.

        :returns: a generator of questions

        :raises CacheError: raised when an error occurs accessing the
            cache
        """

        logger.info("Retrieving cached questions: '%s'", self.url)

        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        cache_items = self.cache.retrieve()

        nquestions = 0

        for items in cache_items:
            questions = json.loads(items)['results']
            for question in questions:
                nquestions += 1
                yield question

        logger.info("Retrieval process completed: %s questions retrieved from cache",
                    nquestions)

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from an question item."""
        return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a Kitsune item.

        The timestamp is extracted from 'timestamp' field.
        This date is a UNIX timestamp but needs to be converted to
        a float value.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        return float(parser.parse(item['updated']).timestamp())


class KitsuneClient:
    """Kitsune API client.

    This class implements a simple client to retrieve questions and answers from
    a Kitsune site.

    :param url: URL of Kitsune (sample https://support.mozilla.org)

    :raises HTTPError: when an error occurs doing the request
    """

    QUESTIONS_PER_PAGE = 20  # Fixed param from API

    def __init__(self, url):
        self.url = url
        self.api_url = urljoin(self.url, '/api/2/')

    def call(self, api_url, params):
        """Run an API command.
        :param cgi: cgi command to run on the server
        :param params: dict with the HTTP parameters needed to run
            the given command
        """
        logger.debug("Kitsune client calls API: %s params: %s",
                     api_url, str(params))

        req = requests.get(api_url, params=params)
        req.raise_for_status()

        return req.text

    def get_questions(self, offset=None):
        """Retrieve questions from page"""
        page = 1

        if offset:
            # First containes contains the offset item but could include
            # previous questions also from the same page
            page = int(offset/self.QUESTIONS_PER_PAGE)+1

        more_questions = True # There are more questions to be processed
        next_uri = None # URI for the next questions query

        while more_questions:

            if next_uri:
                # https://support.mozilla.org/api/2/question/?page=2
                page = next_uri.split('page=')[1]

            api_questions_url = urljoin(self.api_url, '/question')+'/'

            params = {
                "page":page
            }

            questions = self.call(api_questions_url, params)
            yield questions

            questions_json = json.loads(questions)
            next_uri = questions_json['next']

            if not next_uri:
                more_questions = False

    def get_answers(self, page=0):
        """Retrieve answers from page"""

        api_answers_url = urljoin(self.api_url, '/answer')+'/'

        params = {
            "page":page
        }

        return self.call(api_answers_url, params)



class KitsuneCommand(BackendCommand):
    """Class to run Kitsune backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)
        self.url = self.parsed_args.url
        self.origin = self.parsed_args.origin
        self.outfile = self.parsed_args.outfile
        self.offset = self.parsed_args.offset

        if not self.parsed_args.no_cache:
            if not self.parsed_args.cache_path:
                base_path = os.path.expanduser('~/.perceval/cache/')
            else:
                base_path = self.parsed_args.cache_path

            cache_path = os.path.join(base_path, self.url)

            cache = Cache(cache_path)

            if self.parsed_args.clean_cache:
                cache.clean()
            else:
                cache.backup()
        else:
            cache = None

        self.backend = Kitsune(self.url, cache=cache, origin=self.origin)

    def run(self):
        """Fetch and print the Events.

        This method runs the backend to fetch the questions of a given url.
        Events are converted to JSON objects and printed to the
        defined output.
        """
        if self.parsed_args.fetch_cache:
            questions = self.backend.fetch_from_cache()
        else:
            questions = self.backend.fetch(offset=self.offset)

        try:
            for question in questions:
                obj = json.dumps(question, indent=4, sort_keys=True)
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
        """Returns the Kitsune argument parser."""

        parser = super().create_argument_parser()
        # Remove --from-date argument from parent parser
        # because it is not needed by this backend
        action = parser._option_string_actions['--from-date']
        parser._handle_conflict_resolve(None, [('--from-date', action)])

        # Kitsune options
        group = parser.add_argument_group('Kitsune arguments')

        # Optional arguments
        parser.add_argument('--offset', dest='offset',
                            type=int, default=0,
                            help='Offset to start fetching questions')

        group.add_argument("url", default="https://support.mozilla.org", nargs='?',
                           help="Kitsune URL (default: https://support.mozilla.org)")

        return parser
