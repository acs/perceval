#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016 Bitergia
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
#     Santiago Dueñas <sduenas@bitergia.com>
#     Alvaro del Castillo <acs@bitergia.com>
#

import argparse
import json
import sys
import unittest

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.backends.sortinghat import (
    SortingHat, SortingHatCommand, SortingHatClient)


SH_IDENTITIES_FILE='./sortinghat_uidentites.json'
IDENTITIES_TOTAL = 344

class TestSortingHatBackend(unittest.TestCase):
    """SortingHat backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        sortinghat = SortingHat(SH_IDENTITIES_FILE, tag='test')

        self.assertEqual(sortinghat.url, SH_IDENTITIES_FILE)
        self.assertEqual(sortinghat.origin, SH_IDENTITIES_FILE)
        self.assertEqual(sortinghat.tag, 'test')
        self.assertIsInstance(sortinghat.client, SortingHatClient)

        # When tag is empty or None it will be set to
        # the value in url
        sortinghat = SortingHat(SH_IDENTITIES_FILE)
        self.assertEqual(sortinghat.url, SH_IDENTITIES_FILE)
        self.assertEqual(sortinghat.origin, SH_IDENTITIES_FILE)
        self.assertEqual(sortinghat.tag, SH_IDENTITIES_FILE)

        sortinghat = SortingHat(SH_IDENTITIES_FILE, tag='')
        self.assertEqual(sortinghat.url, SH_IDENTITIES_FILE)
        self.assertEqual(sortinghat.origin, SH_IDENTITIES_FILE)
        self.assertEqual(sortinghat.tag, SH_IDENTITIES_FILE)


    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(SortingHat.has_caching(), False)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(SortingHat.has_resuming(), False)


    def test_fetch(self):
        """Test whether the identities are returned"""

        sortinghat = SortingHat(SH_IDENTITIES_FILE)

        identities = [identity for identity in sortinghat.fetch()]

        self.assertEqual(len(identities), IDENTITIES_TOTAL)

        # self.__check_identities_contents(identities)

class TestSortingHatCommand(unittest.TestCase):

    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['--tag', 'test', SH_IDENTITIES_FILE]

        cmd = SortingHatCommand(*args)
        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.url, SH_IDENTITIES_FILE)
        self.assertEqual(cmd.parsed_args.tag, 'test')
        self.assertIsInstance(cmd.backend, SortingHat)


    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = SortingHatCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)


class TestSortingHatClient(unittest.TestCase):
    """SortingHat API client tests
    """
    @httpretty.activate
    def test_init(self):
        """Test initialization"""
        client = SortingHatClient(SH_IDENTITIES_FILE)

    def test_get_identities(self):
        """Test get_events API call"""

        with open(SH_IDENTITIES_FILE) as f:
            json_test_uids = json.load(f)
            client = SortingHatClient(SH_IDENTITIES_FILE)

            for uid in client.get_uidentities():
                # Check that the uuid is included in the test_uids JSON
                self.assertEqual(uid['uuid'] in json_test_uids['uidentities'], True)

if __name__ == "__main__":
    unittest.main(warnings='ignore')
