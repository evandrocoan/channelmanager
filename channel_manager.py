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


# https://stackoverflow.com/questions/14087598/python-3-importerror-no-module-named-configparser
try:
    import configparser
    from configparser import NoOptionError

except:
    from six.moves import configparser
    from six.moves.configparser import NoOptionError


from .settings import *
g_is_already_running = False

from .channel_utilities import write_data_file
from .channel_utilities import string_convert_list
from .channel_utilities import load_data_file
from .channel_utilities import print_data_file
from .channel_utilities import dictionary_to_string_by_line

# When there is an ImportError, means that Package Control is installed instead of PackagesManager,
# or vice-versa. Which means we cannot do nothing as this is only compatible with PackagesManager.
try:
    from PackagesManager.packagesmanager.package_manager import PackageManager
    from PackagesManager.packagesmanager.providers.channel_provider import ChannelProvider

    from PackagesManager.packagesmanager import cmd
    from PackagesManager.packagesmanager.thread_progress import ThreadProgress

except ImportError:
    pass

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


def main(channel_settings):
    log( 2, "Entering on main(0)" )

    channel_thread = GenerateChannelThread(channel_settings)
    channel_thread.start()

    ThreadProgress( channel_thread, "Generating Channel and Repositories files",
            "Channel and repositories files successfully created." )


def unpack_settings(channel_settings):
    global CHANNEL_REPOSITORY_URL
    global DEFAULT_CHANNEL_URL

    global CHANNEL_ROOT_DIRECTORY
    global CHANNEL_FILE_PATH
    global CHANNEL_REPOSITORY_FILE
    global CHANNEL_SETTINGS_PATH

    CHANNEL_REPOSITORY_URL = channel_settings['CHANNEL_REPOSITORY_URL']
    DEFAULT_CHANNEL_URL    = channel_settings['DEFAULT_CHANNEL_URL']

    CHANNEL_ROOT_DIRECTORY  = channel_settings['CHANNEL_ROOT_DIRECTORY']
    CHANNEL_FILE_PATH       = channel_settings['CHANNEL_FILE_PATH']
    CHANNEL_REPOSITORY_FILE = channel_settings['CHANNEL_REPOSITORY_FILE']

    CHANNEL_SETTINGS_PATH = channel_settings['CHANNEL_SETTINGS_PATH']
    # log( 1, "channel_settings: " + dictionary_to_string_by_line( channel_settings ) )


class GenerateChannelThread(threading.Thread):

    def __init__(self, channel_settings):
        threading.Thread.__init__(self)
        self.channel_settings = channel_settings

    def run(self):
        log( 2, "Entering on run(1)" )

        if is_allowed_to_run():
            unpack_settings( self.channel_settings )
            all_packages = load_deafault_channel()

            # print_some_repositories(all_packages)
            repositories, dependencies = get_repositories( all_packages )

            create_channel_file( repositories, dependencies )
            create_repository_file( repositories, dependencies )
            create_ignored_packages()

            global g_is_already_running
            g_is_already_running = False


def create_ignored_packages():
    channelSettings = {}
    userSettings   = sublime.load_settings("Preferences.sublime-settings")

    user_ignored_packages                = userSettings.get("ignored_packages", [])
    channelSettings['packages_to_ignore'] = user_ignored_packages

    write_data_file( CHANNEL_SETTINGS_PATH, channelSettings )


def is_allowed_to_run():
    global g_is_already_running

    if g_is_already_running:
        print( "You are already running a command. Wait until it finishes or restart Sublime Text" )
        return False

    g_is_already_running = True
    return True


def load_deafault_channel():
    package_manager  = PackageManager()
    channel_provider = ChannelProvider( DEFAULT_CHANNEL_URL, package_manager.settings )

    all_packages = {}
    channel_repositories = channel_provider.get_sources()

    for repository in channel_repositories:
        packages = channel_provider.get_packages(repository)
        all_packages.update( packages )

    return all_packages


def create_repository_file(repositories, dependencies):
    repository_file = OrderedDict()
    repository_file['schema_version'] = "3.0.0"

    repository_file['packages']     = repositories
    repository_file['dependencies'] = dependencies

    # print_data_file( CHANNEL_REPOSITORY_FILE )
    write_data_file( CHANNEL_REPOSITORY_FILE, repository_file )


def create_channel_file(repositories, dependencies):
    channel_dictionary = OrderedDict()

    channel_dictionary['repositories'] = []
    channel_dictionary['repositories'].append( CHANNEL_REPOSITORY_URL )

    channel_dictionary['schema_version'] = "3.0.0"
    channel_dictionary['packages_cache'] = OrderedDict()
    channel_dictionary['packages_cache'][CHANNEL_REPOSITORY_URL] = repositories

    channel_dictionary['dependencies_cache'] = OrderedDict()
    channel_dictionary['dependencies_cache'][CHANNEL_REPOSITORY_URL] = dependencies

    # print_data_file( CHANNEL_FILE_PATH )
    write_data_file( CHANNEL_FILE_PATH, channel_dictionary )


def get_repositories(all_packages):
    gitFilePath    = os.path.join( CHANNEL_ROOT_DIRECTORY, '.gitmodules' )
    gitModulesFile = configparser.RawConfigParser()

    repositories = []
    dependencies = []

    gitModulesFile.read( gitFilePath )
    command_line_interface = cmd.Cli( None, True )

    sections       = gitModulesFile.sections()
    sections_count = len( sections )

    index = 0
    log( 1, "Total repositories to parse: " + str( sections_count ) )

    for section in sections:
        url      = gitModulesFile.get( section, "url" )
        path     = gitModulesFile.get( section, "path" )
        upstream = gitModulesFile.get( section, "upstream" )

        user_forker     = get_user_name( url )
        repository_path = os.path.join( CHANNEL_ROOT_DIRECTORY, path )
        release_date    = get_git_date( repository_path, command_line_interface )

        # # For quick testing
        # index += 1
        # if index > 7:
        #     break

        if 'Packages' == path[0:8]:
            release_data    = OrderedDict()
            repository_info = OrderedDict()
            repository_name = os.path.basename( path )

            if repository_name in all_packages:
                repository_info = all_packages[repository_name]
                release_data    = repository_info['releases'][0]

            else:
                repository_info['details']   = url

                release_data['platforms']    = "*"
                release_data['sublime_text'] = ">=3126"

            release_data['date']    = release_date
            release_data['version'] = get_git_version( release_date )

            fix_sublime_text_release( release_data, gitModulesFile, section, repository_info, repositories, dependencies, url )
            tagged_releases = get_old_compatible_versions( release_data, gitModulesFile, section, url, repository_path, command_line_interface )

            ensure_author_name( user_forker, upstream, repository_info )

            tagged_releases.insert( 0, release_data )
            tagged_releases = sort_list_of_dictionaries( tagged_releases )

            repository_info['name']     = repository_name
            repository_info['releases'] = tagged_releases

    return sort_list_of_dictionary( repositories), sort_list_of_dictionary( dependencies )


def fix_sublime_text_release(release_data, gitModulesFile, section, repository_info, repositories, dependencies, url):
    """
        If it has the dependency option, then it:
            1. It is a module dependency only
            2. It is a module dependency and has other dependencies
            3. It is a package and has dependencies

        @param release_data      the dictionary with the current release_data information
        @param gitModulesFile    the current `.gitmodules` configparser interator
        @param section           the section name on the `.gitmodules` file for the current repository information
        @param repository_info   the dictionary with the current repository information
        @param repositories      the dictionary with all repositories
        @param dependencies      the dictionary with all dependencies
        @param url               the main repository url as `github.com/user/repo`
    """
    repository_info['homepage'] = url

    if 'previous_names' not in repository_info:
        repository_info['previous_names'] = []

    if 'description' not in repository_info:
        repository_info['description'] = "No description available."

    if gitModulesFile.has_option( section, "dependency" ):
        dependency_list = string_convert_list( gitModulesFile.get( section, "dependency" ) )

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

    acceptable_version = 3092

    if not is_compatible_version( release_data['sublime_text'], acceptable_version ):
        release_data['sublime_text'] = ">=" +  str( acceptable_version )


def get_old_compatible_versions(default_release_data, gitModulesFile, section, url, repository_path, command_line_interface):
    """
        Check for the existence of the `tags` section on the `gitModulesFile` iterator and add the
        correct for the listed olde compatible versions.

        The old compatible versions are git tags as `3143` which is the last Sublime Text version
        where the submodule was compatible with. For example, on Sublime Text development build
        3147, the package `Notepad++ Color Scheme` stopped working completely:
            1. https://github.com/SublimeTextIssues/Core/issues/1983)

        However the fix for build 3147 also broke completely the package for Sublime Text stable
        build 3143. Hence, we must to create a tag named 3143 which targets the last commit which is
        working for build 3143, then when some user using the stable build 3143 installs the
        Notepad++, they must install the one from the tag `3143`, and not the one from the master
        branch, which has the latest fixes for build development build 3147.

        @param others                   @see the function fix_sublime_text_release()
        @param repository_path          absolute path the the repository to retrieve the tag data
        @param command_line_interface   a command line object to run the git command

        @return a list of dictionary releases created, otherwise a empty list if not tags exists
    """
    greatest_tag    = get_version_number( default_release_data['sublime_text'] )
    tagged_releases = []

    if gitModulesFile.has_option( section, "tags" ):
        tags_list = string_convert_list( gitModulesFile.get( section, "tags" ) )

        for tag in tags_list:
            tag_interger = int( tag )

            release_data = OrderedDict()
            tag_date     = get_git_tag_date(repository_path, command_line_interface, tag)

            release_data['platforms']    = "*"
            release_data['sublime_text'] = "<=%s" % tag

            if greatest_tag < tag_interger:
                greatest_tag = tag_interger
                default_release_data['sublime_text'] = ">" + tag

            release_data['url']     = get_tag_download_url( url, tag )
            release_data['date']    = tag_date
            release_data['version'] = get_git_tag_version( tag_date, tag )

            tagged_releases.append( release_data )

    return tagged_releases


def get_version_number(sublime_version_text):
    number_match = re.match('.+(\d+)$',  sublime_version_text)

    if number_match:
        return int( number_match.group( 1 ) )

    return 0


def is_compatible_version(release_version, acceptable_version):
    """
        Returns True when the `release_version` is compatible with the minimum acceptable version
        `acceptable_version`.
    """

    if release_version == '*':
        return True

    min_version = float("-inf")
    max_version = float("inf")

    range_match      = re.match('(\d+)\s*-\s*(\d+)$', release_version)
    less_than        = re.match('<(\d+)$',  release_version)
    greater_than     = re.match('>(\d+)$',  release_version)
    less_or_equal    = re.match('<=(\d+)$', release_version)
    greater_or_equal = re.match('>=(\d+)$', release_version)

    if greater_than:
        min_version = int( greater_than.group( 1 ) ) + 1

    elif greater_or_equal:
        min_version = int( greater_or_equal.group( 1 ) )

    elif less_than:
        max_version = int( less_than.group( 1 ) ) - 1

    elif less_or_equal:
        max_version = int( less_or_equal.group( 1 ) )

    elif range_match:
        min_version = int( range_match.group( 1 ) )
        max_version = int( range_match.group( 2 ) )

    else:
        return False

    if min_version < acceptable_version or max_version < acceptable_version:
        return False

    return True


def sort_list_of_dictionaries(list_of_dictionaries):
    sorted_dictionaries = []

    for dictionary in list_of_dictionaries:
        sorted_dictionaries.append( sort_dictionary( dictionary ) )

    return sorted_dictionaries

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


def get_user_name(url, regular_expression="github\.com\/(.+)/(.+)", allow_recursion=True):
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


def get_tag_download_url(url, tag):
    return url.replace("//github.com/", "//codeload.github.com/") + "/zip/%s" % tag


def get_git_date(repository_path, command_line_interface):
    """
        Get timestamp of the last commit in git repository
        https://gist.github.com/bitrut/1494315
    """
    # command = shlex.split( "git log -1 --date=iso" )
    command = shlex.split( "git log -1 --pretty=format:%ci" )

    output = command_line_interface.execute( command, repository_path )
    return output[0:19]


def get_git_tag_date(repository_path, command_line_interface, tag):
    """
        Get timestamp of the specified tag in git repository
        https://gist.github.com/bitrut/1494315
    """
    # command = shlex.split( "git log -1 --date=iso" )
    command = shlex.split( "git log -1 --pretty=format:%ci {}".format( tag ) )

    output = command_line_interface.execute( command, repository_path )
    return output[0:19]


def get_git_version(release_date):
    """
        Get timestamp of the last commit in git repository
        https://gist.github.com/bitrut/1494315
    """
    return release_date.replace("-", ".")[0:10]


def get_git_tag_version(tag_date, tag):
    """
        Get timestamp of the last commit in git repository
        https://gist.github.com/bitrut/1494315
    """
    tag_date = tag_date.replace("-", ".")[0:10]
    return tag + "." + tag_date[:4] + tag_date[5:]


def print_some_repositories(all_packages):
    index = 1

    for package in all_packages:
        index += 1

        if index > 10:
            break

        log( 1, "" )
        log( 1, "package: %-20s" %  str( package ) + json.dumps( all_packages[package], indent=4 ) )

