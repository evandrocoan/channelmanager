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
import threading

import re
import shlex
import subprocess

from collections import OrderedDict


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
assert_path( os.path.join( os.path.dirname( CURRENT_DIRECTORY ), "PythonDebugTools/all" ) )
assert_path( os.path.join( os.path.dirname( CURRENT_DIRECTORY ), "Package Control" ) )

from package_control.package_manager import PackageManager
from package_control.providers.channel_provider import ChannelProvider
from package_control import cmd


# Import the debugger
from debug_tools import Debugger

# Debugger settings: 0 - disabled, 127 - enabled
log = Debugger( 127, os.path.basename( __file__ ) )

#log.log_to_file( "Debug.txt" )
#log.clear_log_file()

# log( 2, "..." )
# log( 2, "..." )
# log( 2, "Debugging" )
# log( 2, "CURRENT_DIRECTORY: " + CURRENT_DIRECTORY )


def main():
    log( 2, "Entering on main(0)" )
    threading.Thread(target=run).start()


def run():
    all_packages = load_deafault_channel()

    # print_some_repositoies(all_packages)
    repositories, dependencies = get_repositories( all_packages )

    create_channel_file( repositories, dependencies )
    create_repository_file( repositories, dependencies )


def load_deafault_channel():
    package_manager  = PackageManager()
    channel_provider = ChannelProvider( "https://packagecontrol.io/channel_v3.json", package_manager.settings )

    all_packages = {}
    channel_repositories = channel_provider.get_sources()

    for repository in channel_repositories:
        packages = channel_provider.get_packages(repository)
        all_packages.update( packages )

    return all_packages


def create_repository_file( repositories, dependencies ):
    repository_file = OrderedDict()
    repository_file['schema_version'] = "3.0.0"

    repository_file['packages']     = repositories
    repository_file['dependencies'] = dependencies

    # print_data_file( STUDIO_REPOSITORY_FILE, repository_file )
    write_data_file( STUDIO_REPOSITORY_FILE, repository_file )


def create_channel_file( repositories, dependencies ):
    channel_file   = OrderedDict()
    repository_url = "https://raw.githubusercontent.com/evandrocoan/SublimeTextStudioChannel/master/repository.json"

    channel_file['repositories'] = []
    channel_file['repositories'].append( repository_url )

    channel_file['schema_version'] = "3.0.0"
    channel_file['packages_cache'] = OrderedDict()
    channel_file['packages_cache'][repository_url] = repositories

    channel_file['dependencies_cache'] = OrderedDict()
    channel_file['dependencies_cache'][repository_url] = dependencies

    # print_data_file( STUDIO_CHANNEL_FILE, channel_file )
    write_data_file( STUDIO_CHANNEL_FILE, channel_file )


def get_repositories( all_packages ):
    sublimeFolder  = os.path.dirname( os.path.dirname( CURRENT_DIRECTORY ) )
    gitFilePath    = os.path.join( sublimeFolder, '.gitmodules' )
    gitModulesFile = configparser.RawConfigParser()

    repositories = []
    dependencies = []
    gitModulesFile.read( gitFilePath )

    index = 0
    command_line_interface = cmd.Cli( None, True )

    for section in gitModulesFile.sections():
        url      = gitModulesFile.get( section, "url" )
        path     = gitModulesFile.get( section, "path" )
        upstream = gitModulesFile.get( section, "upstream" )

        user_forker  = get_user_name( url )
        release_date = get_git_date( os.path.join( sublimeFolder, path ), command_line_interface )

        # # For quick testing
        # index += 1
        # if index > 7:
        #     break

        if 'Packages' in os.path.dirname( path ):
            release_data    = OrderedDict()
            repository_info = OrderedDict()
            repository_name = os.path.basename( path )

            if repository_name in all_packages:
                repository_info = all_packages[repository_name]
                release_data    = repository_info['releases'][0]
            else:

                repository_info['details']  = url
                repository_info['homepage'] = url

                release_data['platforms']    = "*"
                release_data['sublime_text'] = ">=3126"

            ensure_author_name( user_forker, upstream, repository_info )

            release_data['date']    = release_date
            release_data['version'] = get_git_version( release_date )

            if 'description' not in repository_info:
                repository_info['description'] = "No description available."


            # If it has the dependency option, then it:
            # 1. It is a module dependency only
            # 2. It is a module dependency and has other dependencies
            # 3. It is a package and has dependencies
            if gitModulesFile.has_option( section, "dependency" ):
                dependency      = gitModulesFile.get( section, "dependency" )
                dependency_list = get_parse_list( dependency )

                if len( dependency_list ) > 0:

                    try:
                        load_order = int( dependency_list[0] )

                        repository_info['issues']     = url + "/issues"
                        repository_info['load_order'] = load_order

                        release_data['url']  = get_download_url( url )
                        release_data['base'] = url
                        release_data['tags'] = True

                        del dependency_list[0]
                        dependencies.append( repository_info )

                        if len( dependency_list ) > 0:
                            release_data['dependencies'] = dependency_list

                    except ValueError:
                        release_data['dependencies'] = dependency_list

                        release_data['url'] = get_download_url( url )
                        repositories.append( repository_info )

                else:
                    release_data['url'] = get_download_url( url )
                    repositories.append( repository_info )

            else:
                release_data['url'] = get_download_url( url )
                repositories.append( repository_info )

            release_data = sort_dictionary( release_data )

            repository_info['name']     = repository_name
            repository_info['releases'] = [ release_data ]

    return sort_list_of_dictionary( repositories) , sort_list_of_dictionary( dependencies )


def sort_dictionary(dictionary):
    return OrderedDict( sorted( dictionary.items() ) )


def sort_list_of_dictionary(list_of_dictionaries):
    """
        How do I sort a list of dictionaries by values of the dictionary in Python?
        https://stackoverflow.com/questions/72899/how-do-i-sort-a-list-of-dictionaries-by-values-of-the-dictionary-in-python

        case-insensitive list sorting, without lowercasing the result?
        https://stackoverflow.com/questions/10269701/case-insensitive-list-sorting-without-lowercasing-the-result
    """
    sorted_list = []

    for dictionary in list_of_dictionaries:
        sorted_list.append( sort_dictionary( dictionary ) )

    return sorted( sorted_list, key=lambda k: k['name'].lower() )


def get_parse_list( comma_separated_list ):

    if comma_separated_list:
        return [ dependency.strip() for dependency in comma_separated_list.split(',') ]

    return []


def ensure_author_name(user_forker, upstream, repository_info):

    if 'authors' not in repository_info:

        if len( upstream ) > 20:

            original_author            = get_user_name( upstream )
            repository_info['authors'] = [ original_author ]

        else:

            # If there is not upstream set, then it is your own package (user_forker)
            repository_info['authors'] = [user_forker]

    if user_forker not in repository_info['authors']:
        repository_info['authors'].append( "Forked by " + user_forker )


def get_user_name( url, regular_expression="github\.com\/(.+)/(.+)", allow_recursion=True ):
    """
        How to extract a substring from inside a string in Python?
        https://stackoverflow.com/questions/4666973/how-to-extract-a-substring-from-inside-a-string-in-python
    """
    # https://regex101.com/r/TRxkI9/1/
    matches = re.search( regular_expression, url )

    if matches:
        return matches.group(1)

    elif allow_recursion:
        return get_user_name( url, "bitbucket\.org\/(.+)/(.+)", False )

    return ""


def get_download_url(url):
    return url.replace("//github.com/", "//codeload.github.com/") + "/zip/master"


def get_git_date(repository_path, command_line_interface):
    """
        Get timestamp of the last commit in git repository
        https://gist.github.com/bitrut/1494315
    """
    # command = shlex.split( "git log -1 --date=iso" )
    command = shlex.split( "git log -1 --pretty=format:%ci" )

    output = command_line_interface.execute( command, repository_path )
    return output[0:19]


def get_git_version(release_date):
    """
        Get timestamp of the last commit in git repository
        https://gist.github.com/bitrut/1494315
    """
    return release_date.replace("-", ".")[0:10]


def write_data_file(file_path, channel_file):

    with open(file_path, 'w', encoding='utf-8') as output_file:
        json.dump( channel_file, output_file, indent=4 )


def print_data_file(file_path, channel_file):

    with open( file_path, 'r', encoding='utf-8' ) as studio_channel_data:
        channel_file = json.load( studio_channel_data)
        log( 1, "channel_file: " + json.dumps( channel_file, indent=4, sort_keys=True ) )


def print_some_repositoies(all_packages):
    index = 1

    for package in all_packages:
        index += 1

        if index > 10:
            break

        log( 1, "" )
        log( 1, "package: %-20s" %  str( package ) + json.dumps( all_packages[package], indent=4 ) )


class SublimeTextStudioGenerateChannelFileCommand( sublime_plugin.TextCommand ):

    def run(self):
        print( 'Calling SublimeTextStudioGenerateChannelFile...' )


if __name__ == "__main__":
    main()


def plugin_loaded():
    # main()
    pass

