#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# These lines allow to use UTF-8 encoding and run this file with `./update.py`, instead of `python update.py`
# https://stackoverflow.com/questions/7670303/purpose-of-usr-bin-python3
# https://stackoverflow.com/questions/728891/correct-way-to-define-python-source-code-encoding
#
#

#
# Licensing
#
# Channel Manager Tests, some simple tests for channel manager
# Copyright (C) 2017 Evandro Coan <https://github.com/evandrocoan>
#
#  This program is free software; you can redistribute it and/or modify it
#  under the terms of the GNU General Public License as published by the
#  Free Software Foundation; either version 3 of the License, or ( at
#  your option ) any later version.
#
#  This program is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import sys
import unittest

from .channel_manager import fix_semantic_version
from .channel_manager import increment_patch_version

from debug_tools import getLogger

# Debugger settings: 0 - disabled, 127 - enabled
log = getLogger( 127, __name__ )


def main():
    log( 1, "Entering on main(0)" )
    # log.newline()

    runner = unittest.TextTestRunner()
    runner.run( suite() )


def suite():
    """
        Problem with sys.argv[1] when unittest module is in a script
        https://stackoverflow.com/questions/2812218/problem-with-sys-argv1-when-unittest-module-is-in-a-script

        Is there a way to loop through and execute all of the functions in a Python class?
        https://stackoverflow.com/questions/2597827/is-there-a-way-to-loop-through-and-execute-all-of-the-functions

        looping over all member variables of a class in python
        https://stackoverflow.com/questions/1398022/looping-over-all-member-variables-of-a-class-in-python
    """
    suite   = unittest.TestSuite()
    classes = [ ChannelManagerUnitTests ]

    for _class in classes:
        _object = _class()

        for methode_name in dir( _object ):

            if methode_name.lower().startswith( "test" ):
                suite.addTest( ChannelManagerUnitTests( methode_name ) )

    return suite


class ChannelManagerUnitTests(unittest.TestCase):

    def test_increment_patch_version(self):
        self.increment_patch_version( "1", True, "1.0.1" )
        self.increment_patch_version( "1.1", True, "1.1.1" )
        self.increment_patch_version( "1.1.1", True, "1.1.2" )

        self.increment_patch_version( "v1", True, "v1.0.1" )
        self.increment_patch_version( "v1.1", True, "v1.1.1" )
        self.increment_patch_version( "v1.1.1", True, "v1.1.2" )

    def increment_patch_version(self, tag, increment, goal):
        fixed = increment_patch_version( tag, increment )

        # log( 1, "increment_patch_version(%s), fixed: %s" % ( tag, fixed ) )
        self.assertEqual( fixed[0], goal )

    def test_fix_semantic_version(self):
        self.fix_semantic_version( "1.0", "1.0.0", "1.0" )
        self.fix_semantic_version( "1.6", "1.6.0", "1.6" )

        self.fix_semantic_version("v1", "1.0.0", "1" )
        self.fix_semantic_version("v1.1", "1.1.0", "1.1" )
        self.fix_semantic_version("v1.1.1", "1.1.1", "1.1.1" )

        self.fix_semantic_version( "v1.0", "1.0.0", "1.0" )
        self.fix_semantic_version( "v1.6", "1.6.0", "1.6" )
        self.fix_semantic_version( "v1.6a", "1.6.0", "1.6" )

        self.fix_semantic_version( "1.0.0", "1.0.0", "1.0.0" )
        self.fix_semantic_version( "1.6.0", "1.6.0", "1.6.0" )
        self.fix_semantic_version( "1.6.1", "1.6.1", "1.6.1" )

        self.fix_semantic_version( "v1.0.0", "1.0.0", "1.0.0" )
        self.fix_semantic_version( "v1.6.0", "1.6.0", "1.6.0" )
        self.fix_semantic_version( "v1.6.1", "1.6.1", "1.6.1" )

    def fix_semantic_version(self, tag, fix_goal, match_goal):
        fixed, matched = fix_semantic_version(tag)

        # log( 1, "fix_semantic_version(%s), fixed: %s, matched: %s" % ( tag, fixed, matched ) )
        self.assertEqual( fixed, fix_goal )
        self.assertEqual( matched, match_goal )


