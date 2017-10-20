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

from .channel_manager import fix_semantic_version


def main():
    log( 2, "Entering on main(2)" )
    test_fix_semantic_version( "1.0.0" )
    test_fix_semantic_version( "1.6.0" )
    test_fix_semantic_version( "1.6.1" )

    test_fix_semantic_version( "v1.0.0" )
    test_fix_semantic_version( "v1.6.0" )
    test_fix_semantic_version( "v1.6.1" )


def test_fix_semantic_version(tag):
    log( 1, "fix_semantic_version(%s): %s" % ( tag, fix_semantic_version(tag) ) )


def plugin_loaded():
    main()
    pass


