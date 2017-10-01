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

import sublime
import sublime_plugin

import os
import sys
import json


def assert_path(module):
    """
        Import a module from a relative path
        https://stackoverflow.com/questions/279237/import-a-module-from-a-relative-path
    """
    if module not in sys.path:
        sys.path.append( module )


# https://stackoverflow.com/questions/14087598/python-3-importerror-no-module-named-configparser
try:
    import configparser
    from configparser import NoOptionError

except:
    from six.moves import configparser
    from six.moves.configparser import NoOptionError


CURRENT_DIRECTORY      = os.path.dirname( os.path.realpath( __file__ ) )
STUDIO_CHANNEL_FILE    = os.path.join( CURRENT_DIRECTORY, "channel.json" )
STUDIO_REPOSITORY_FILE = os.path.join( CURRENT_DIRECTORY, "repository.json" )


# print( "CURRENT_DIRECTORY: " + CURRENT_DIRECTORY )
assert_path( os.path.join( os.path.dirname( CURRENT_DIRECTORY ), 'PythonDebugTools' ) )

# Import the debugger
from debug_tools import Debugger

# Debugger settings: 0 - disabled, 127 - enabled
log = Debugger( 127, os.path.basename( __file__ ) )

log( 2, "..." )
log( 2, "..." )
log( 2, "Debugging" )
log( 2, "CURRENT_DIRECTORY: " + CURRENT_DIRECTORY )


def main():
    log( 2, "Entering on main(0)" )
    repositories = get_repositories()

    create_channel_file( repositories )
    create_repository_file( repositories )


def create_repository_file( repositories ):
    repository_file = {}

    repository_file['packages']       = repositories
    repository_file['schema_version'] = "3.0.0"

    # print_data_file( STUDIO_REPOSITORY_FILE, repository_file )
    write_data_file( STUDIO_REPOSITORY_FILE, repository_file )


def create_channel_file( repositories ):
    channel_file   = {}
    repository_url = "https://raw.githubusercontent.com/evandrocoan/SublimeTextStudioChannel/master/repository.json"

    channel_file['repositories'] = []
    channel_file['repositories'].append( repository_url )

    channel_file['schema_version'] = "3.0.0"
    channel_file['packages_cache'] = {}
    channel_file['packages_cache'][repository_url] = repositories

    # print_data_file( STUDIO_CHANNEL_FILE, channel_file )
    write_data_file( STUDIO_CHANNEL_FILE, channel_file )


def get_repositories():
	gitFilePath    = os.path.join( os.path.dirname( os.path.dirname( CURRENT_DIRECTORY ) ), '.gitmodules' )
	gitModulesFile = configparser.RawConfigParser()

	repositories = []
	gitModulesFile.read( gitFilePath )

	for section in gitModulesFile.sections():
		url  = gitModulesFile.get( section, "url" )
		path = gitModulesFile.get( section, "path" )

		repository_info = {}
		repository_name = os.path.basename( path )

		log( 1, "url:             ", url )
		log( 1, "repository_name: ", repository_name )

		repository_info['name']     = repository_name
		repository_info['details']  = url
		repository_info['homepage'] = url
		repository_info['releases'] = []

		release_info        = {}
		release_info['url'] = url + "/archive/master.zip"

		release_info['platforms']    = "*"
		release_info['version']      = "1.0.0"
		release_info['sublime_text'] = ">=3126"

		repository_info['releases'].append( release_info )
		repositories.append(repository_info)

	return repositories


def write_data_file(file_path, channel_file):

    with open(file_path, 'w', encoding='utf-8') as output_file:
        json.dump( channel_file, output_file, indent=4 )


def print_data_file(file_path, channel_file):

	with open( file_path, 'r', encoding='utf-8' ) as studio_channel_data:
	    channel_file = json.load( studio_channel_data)
	    log( 1, "channel_file: " + json.dumps( channel_file, indent=4 ) )


class SublimeTextStudioGenerateChannelFileCommand( sublime_plugin.TextCommand ):

    def run(self):
        print( 'Calling SublimeTextStudioGenerateChannelFile...' )


if __name__ == "__main__":
    main()


def plugin_loaded():
    main()

