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
# Channel Manager Main, Create and maintain channel files
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

import sublime
import sublime_plugin

import os
import sys
import json
import threading

import re
import shlex
import subprocess
import configparser

from collections import OrderedDict
from distutils.version import LooseVersion


from .settings import CURRENT_DIRECTORY
from .settings import CURRENT_PACKAGE_NAME

g_is_already_running = False

from .channel_utilities import write_data_file
from .channel_utilities import string_convert_list
from .channel_utilities import load_data_file
from .channel_utilities import print_data_file
from .channel_utilities import get_dictionary_key
from .channel_utilities import dictionary_to_string_by_line
from .channel_utilities import remove_only_if_exists
from .channel_utilities import load_repository_file

# When there is an ImportError, means that Package Control is installed instead of PackagesManager,
# or vice-versa. Which means we cannot do nothing as this is only compatible with PackagesManager.
try:
    from PackagesManager.packagesmanager.package_manager import PackageManager
    from PackagesManager.packagesmanager.providers.channel_provider import ChannelProvider

    from PackagesManager.packagesmanager import cmd
    from PackagesManager.packagesmanager.thread_progress import ThreadProgress
    from PackagesManager.packagesmanager.show_quick_panel import show_quick_panel

except ImportError:
    pass


# How to reload a Sublime Text dependency?
# https://github.com/randy3k/AutomaticPackageReloader/issues/12
sublime_plugin.reload_plugin( "estimated_time_left" )

from python_debug_tools import Debugger
from estimated_time_left import sequence_timer
from estimated_time_left import progress_info
from estimated_time_left import CurrentUpdateProgress


# Debugger settings: 0 - disabled, 127 - enabled
log = Debugger( 127, os.path.basename( __file__ ) )

#log.log_to_file( "Debug.txt" )
#log.clear_log_file()

# log( 2, "..." )
# log( 2, "..." )
# log( 2, "Debugging" )
# log( 2, "CURRENT_DIRECTORY: " + CURRENT_DIRECTORY )


def main(channel_settings, command="all"):
    global set_progress
    log( 2, "Entering on main(2) %s" % ( str( command ) ) )

    channel_thread = GenerateChannelThread( channel_settings, command )
    channel_thread.start()

    set_progress = CurrentUpdateProgress( "Generating Channel and Repositories files" )
    ThreadProgress( channel_thread, set_progress, "Channel and repositories files successfully created." )


def unpack_settings(channel_settings):
    global CHANNEL_REPOSITORY_URL
    global DEFAULT_CHANNEL_URL

    global CHANNEL_ROOT_DIRECTORY
    global CHANNEL_FILE_PATH
    global CHANNEL_REPOSITORY_FILE

    CHANNEL_REPOSITORY_URL = channel_settings['CHANNEL_REPOSITORY_URL']
    DEFAULT_CHANNEL_URL    = channel_settings['DEFAULT_CHANNEL_URL']

    CHANNEL_ROOT_DIRECTORY  = channel_settings['CHANNEL_ROOT_DIRECTORY']
    CHANNEL_FILE_PATH       = channel_settings['CHANNEL_FILE_PATH']
    CHANNEL_REPOSITORY_FILE = channel_settings['CHANNEL_REPOSITORY_FILE']

    # log( 1, "channel_settings: " + dictionary_to_string_by_line( channel_settings ) )


class GenerateChannelThread(threading.Thread):

    def __init__(self, channel_settings, command="all"):
        threading.Thread.__init__(self)
        self.command          = command
        self.channel_settings = channel_settings

    def run(self):
        log( 2, "Entering on run(1)" )

        if is_allowed_to_run():
            global g_failed_repositories

            unpack_settings( self.channel_settings )
            g_failed_repositories = []

            all_packages      = load_deafault_channel()
            last_channel_file = load_repository_file( CHANNEL_REPOSITORY_FILE )

            # print_some_repositories( all_packages )
            if self.command == "all":
                repositories, dependencies = create_repositories_list( all_packages, last_channel_file )
                self.save_log_file( repositories, dependencies )

            elif self.command == "git_tag":
                self.repositories_list = ["Select this fist item to start the updating... (0 items selected)"]
                self.last_channel_file = last_channel_file

                for package_name in last_channel_file:
                    self.repositories_list.append( package_name )

                self.exclusion_flag   = " (excluded)"
                self.last_picked_item = 0

                self.last_excluded_items = 0
                show_quick_panel( sublime.active_window(), self.repositories_list, self.on_done )

            elif self.command == "git_tag_all":
                index = 0
                repositories_count = len( last_channel_file )

                for package_name, pi in sequence_timer( last_channel_file, info_frequency=0 ):
                    index += 1

                    if not g_is_already_running:
                        raise ImportError( "Stopping the process as this Python module was reloaded!" )

                    # # For quick testing
                    # if index > 5:
                    #     break

                    progress = progress_info( pi, set_progress )
                    log( 1, "{:s} Processing {:3d} of {:d} repositories... {:s}".format( progress, index, repositories_count, package_name ) )

                    last_dictionary = get_dictionary_key( last_channel_file, package_name, {} )
                    update_repository( last_dictionary, package_name )

                repositories, dependencies = split_repositories_and_depencies( last_channel_file )
                self.save_log_file( repositories, dependencies )

            else:
                log( 1, "Invalid command: " + str( self.command ) )

    def save_log_file(self, repositories, dependencies):
        """
            @param repositories  a list of all repositories
            @param dependencies  a list of all dependencies
        """
        log.insert_empty_line( 1 )

        create_channel_file( repositories, dependencies )
        create_repository_file( repositories, dependencies )

        print_failed_repositories()

        sublime.active_window().run_command( "show_panel", {"panel": "console", "toggle": False} )
        free_mutex_lock()

    def on_done(self, picked_index):

        if picked_index < 0:
            free_mutex_lock()
            return

        if picked_index == 0:

            if self.get_total_items_selected() < 1:
                show_quick_panel( sublime.active_window(), self.repositories_list, self.on_done )

            else:
                thread = threading.Thread( target=self.on_done_async )
                thread.start()

        else:

            if picked_index <= self.last_picked_item:
                picked_package = self.repositories_list[picked_index]

                if picked_package.endswith( self.exclusion_flag ):
                    self.last_excluded_items -= 1
                    self.repositories_list[picked_index] = picked_package.strip( self.exclusion_flag )

                else:
                    self.last_excluded_items += 1
                    self.repositories_list[picked_index] = picked_package + self.exclusion_flag

            else:
                self.last_picked_item += 1

            self.update_start_item_name()
            self.repositories_list.insert( 1, self.repositories_list.pop( picked_index ) )
            show_quick_panel( sublime.active_window(), self.repositories_list, self.on_done )

    def update_start_item_name(self):
        self.repositories_list[0] = "Start Updating... (%d items selected)" % ( self.get_total_items_selected() )

    def get_total_items_selected(self):
        return self.last_picked_item - self.last_excluded_items

    def on_done_async(self):
        save_items = False
        log.insert_empty_line( 1 )

        for package_index, pi in sequence_timer( range( 1, self.last_picked_item + 1 ), info_frequency=0 ):
            package_name = self.repositories_list[package_index]

            progress = progress_info( pi, set_progress )
            log( 1, "{:s} Processing {:3d} of {:d} repositories... {:s}".format( progress, package_index, self.last_picked_item, package_name ) )

            if package_name.endswith( self.exclusion_flag ):
                continue

            save_items = True
            last_dictionary = get_dictionary_key( self.last_channel_file, package_name, {} )
            update_repository( last_dictionary, package_name )

        if save_items:
            repositories, dependencies = split_repositories_and_depencies( self.last_channel_file )
            self.save_log_file( repositories, dependencies )


def free_mutex_lock():
    global g_is_already_running
    g_is_already_running = False


def split_repositories_and_depencies(repositories_dictionary):
    packages_list     = []
    dependencies_list = []

    for package_name in repositories_dictionary:
        package_dicitonary             = repositories_dictionary[package_name]
        package_dicitonary['releases'] = sort_dictionaries_on_list( package_dicitonary['releases'] )

        if "load_order" in package_dicitonary:
            dependencies_list.append( package_dicitonary )

        else:
            packages_list.append( package_dicitonary )

    return sort_list_of_dictionary( packages_list), sort_list_of_dictionary( dependencies_list )


def update_repository(last_dictionary, package_name):
    log( 1, "Updating repository... %s" % ( str( package_name ) ) )

    command_line_interface = cmd.Cli( None, True )
    absolute_path = os.path.join( CHANNEL_ROOT_DIRECTORY, "Packages", package_name )

    git_tag, date_tag, release_date = get_last_tag_fixed( absolute_path, last_dictionary, command_line_interface, True )
    release_data = last_dictionary['releases'][0]

    release_data['date']    = release_date
    release_data['version'] = date_tag
    release_data['url']     = release_data['url'].replace( release_data['git_tag'], git_tag )

    # Only push the new tag, if it is not created yet.
    if release_data['git_tag'] != git_tag:
        release_data['git_tag'] = git_tag

        command = "git push origin %s" % git_tag
        command_line_interface.execute( shlex.split( command ), absolute_path, live_output=True, short_errors=True )


def print_failed_repositories():

    if len( g_failed_repositories ) > 0:
        log.insert_empty_line( 1 )
        log.insert_empty_line( 1 )
        log( 1, "The following repositories failed their commands..." )

    for command, repository in g_failed_repositories:
        log( 1, "Command: %s (%s)" % ( command, repository ) )


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


def create_repositories_list(all_packages, last_channel_file):
    gitFilePath    = os.path.join( CHANNEL_ROOT_DIRECTORY, '.gitmodules' )
    gitModulesFile = configparser.RawConfigParser()

    repositories = []
    dependencies = []

    gitModulesFile.read( gitFilePath )
    command_line_interface = cmd.Cli( None, False )

    sections       = gitModulesFile.sections()
    sections_count = count_package_sections( gitModulesFile, sections )

    index = 0
    log( 1, "Total repositories to parse: " + str( sections_count ) )

    for section, pi in sequence_timer( sections, info_frequency=0 ):
        repository = Repository( gitModulesFile, section )

        if not g_is_already_running:
            raise ImportError( "Stopping the process as this Python module was reloaded!" )

        # # For quick testing
        # if index > 3:
        #     break

        if 'Packages' == repository.path[0:8]:
            index += 1

            progress = progress_info( pi, set_progress )
            log( 1, "{:s} Processing {:3d} of {:d} repositories... {:s}".format( progress, index, sections_count, repository.path ) )

            if repository.name in all_packages:
                repository.info = all_packages[repository.name]

            else:
                repository.info['details'] = repository.url

            repository.release_data['platforms']    = "*"
            repository.release_data['sublime_text'] = ">=3126"

            # Must to be called after setting `release_data{}`
            repository.setVersioningTag( last_channel_file, command_line_interface )
            fix_sublime_text_release( repository, repositories, dependencies )

            user_forker = get_user_name( repository.url )
            repository.ensureAuthorName( user_forker )

            # Must to be called after `setVersioningTag()`
            tagged_releases = repository.getOldCompatibleVersions( command_line_interface )
            tagged_releases.insert( 0, repository.release_data )
            tagged_releases = sort_dictionaries_on_list( tagged_releases )

            repository.info['name']     = repository.name
            repository.info['releases'] = tagged_releases

    return sort_list_of_dictionary( repositories), sort_list_of_dictionary( dependencies )


def get_last_tag_fixed(absolute_path, last_dictionary, command_line_interface, force_tag_creation=False):
    """
        This is a entry point to do some batch operation on each git submodule. We can temporarily
        insert the code we want to run with `command_line_interface` and remove later.

        @param force_tag_creation if True, the tag will be created and also push the created tag to origin.
    """
    release_date = get_git_date( absolute_path, command_line_interface )
    date_tag     = get_git_version( release_date )
    git_tag      = get_git_latest_tag( absolute_path, command_line_interface )

    # # Delete all local tags not present on the remote
    # # https://stackoverflow.com/questions/1841341/remove-local-tags-that-are-no-longer
    # command = shlex.split( 'git fetch --prune origin "+refs/tags/*:refs/tags/*"' )
    # output  = command_line_interface.execute( command, absolute_path, short_errors=True )
    # log( 1, "output: " + str( output ) )

    if force_tag_creation:

        # If it does not exists, it means this is the first time and there was not previous data
        if 'releases' in last_dictionary:
            release_data  = last_dictionary['releases'][0]
            last_date_tag = release_data['version']

            if "master" == git_tag:

                if create_git_tag( absolute_path, "1.0.0", command_line_interface ):
                    git_tag = "1.0.0"

            # if LooseVersion( date_tag ) > LooseVersion( last_date_tag ):
            if True:
                next_git_tag, is_incremented, unprefixed_tag = increment_patch_version( git_tag, force_tag_creation )
                current_tags = get_current_cummit_tags( absolute_path, command_line_interface )

                if len( current_tags ) > 0:
                    tags_list = current_tags.split( "\n" )

                    log( 1, "Error: The current HEAD commit already has the following tags(s): %s" % str( current_tags ) )
                    log.insert_empty_line( 1 )

                    # For now, disable all tag prefixes, i.e., tags which are not strictly "0.0.0",
                    # because we cannot handle repositories which have a tag prefix for each
                    # platforms as Linux and Windows. Then we create a unified tag which is based
                    # on the current master branch.
                    if next_git_tag != unprefixed_tag or len( tags_list ) > 1:
                        delete_tags_list( absolute_path, tags_list, command_line_interface )

                        # We will skip the current tag and create the next available
                        if create_git_tag( absolute_path, unprefixed_tag, command_line_interface ):
                            git_tag = unprefixed_tag
                            log.insert_empty_line( 1 )

                else:

                    if next_git_tag != unprefixed_tag:

                        if create_git_tag( absolute_path, unprefixed_tag, command_line_interface ):
                            git_tag = unprefixed_tag

                    else:

                        if is_incremented:

                            if create_git_tag( absolute_path, next_git_tag, command_line_interface ):
                                git_tag = next_git_tag

                        else:
                            log( 1, "Error: The tag `%s` could not be incremented for the package: %s" % ( next_git_tag, absolute_path ) )
                            g_failed_repositories.append( ("", absolute_path) )

    return git_tag, date_tag, release_date


def delete_tags_list(absolute_path, tags_list, command_line_interface):
    tags_count   = len( tags_list )
    remote_index = 0

    for tag, pi in sequence_timer( tags_list, info_frequency=0 ):
        remote_index += 1

        progress = progress_info( pi )
        log( 1, "Cleaning tag {:3d} of {:d} ({:s}): {:<20s} {:s}".format(
                remote_index, tags_count, progress, tag, os.path.basename( absolute_path ) ) )

        command_line_interface.execute(
            shlex.split( "git tag -d %s" % ( tag ) ),
            absolute_path,
            live_output=True,
            short_errors=True
        )

        command_line_interface.execute(
            shlex.split( "git push origin :refs/tags/%s" % ( tag ) ),
            absolute_path,
            live_output=True,
            short_errors=True
        )


def get_current_cummit_tags(absolute_path, command_line_interface):
    command = shlex.split( "git tag -l --points-at HEAD" )
    output = command_line_interface.execute( command, absolute_path, short_errors=True )

    return str( output )


def increment_patch_version(git_tag, force_tag_creation=False):
    """
        Increments tags on the form `0.0.0`.

        @return new_tag_name       the new incremented tag if it was incremented, or the original
                                   value or some other valid value otherwise.

        @return is_incremented     False, when the tag was not incremented, True otherwise.
    """
    # log( 2, "Incrementing %s (%s)" % ( str( git_tag ), str( force_tag_creation ) ) )

    # if the tag is just an integer, it should be a Sublime Text build as 3147
    try:
        if int( git_tag ) > 3000:
            return git_tag, False, git_tag

        else:
            raise ValueError( "The git_tag %s is not an Sublime Text 3 build." % git_tag )

    except ValueError:
        pass

    fixed_tag, matched_tag = fix_semantic_version( git_tag )
    matches = re.search( "(\d+)\.(\d+)\.(\d+)", fixed_tag )

    if matches:
        fixed_tag = "%s.%s.%s" % ( matches.group(1), matches.group(2), str( int( matches.group(3) ) + 1 ) )
        return git_tag.replace( matched_tag, fixed_tag ), True, fixed_tag

    log( 1, "Warning: Could not increment the git_tag: " + str( git_tag ) )

    if force_tag_creation:
        return "1.0.0", True, "1.0.0"

    return "master", False, "master"


def fix_sublime_text_release(repository, repositories, dependencies):
    """
        Add the repository.info to the `packages` or `dependencies` list.

        If it has the dependency option, then it:
            1. It is a module dependency only
            2. It is a module dependency and has other dependencies
            3. It is a package and has dependencies

        @param repository        an object with all the repository related data
        @param repositories      the dictionary with all repositories
        @param dependencies      the dictionary with all dependencies
    """
    minimum_acceptable_version  = 3092
    repository.info['homepage'] = repository.url

    if 'previous_names' not in repository.info:
        repository.info['previous_names'] = []

    if 'description' not in repository.info:
        repository.info['description'] = "No description available."

    if not is_compatible_version( repository.release_data['sublime_text'], minimum_acceptable_version ):
        repository.release_data['sublime_text'] = ">=" +  str( minimum_acceptable_version )

    repository.configureDependenciesFiles( repositories, dependencies )


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


def sort_dictionaries_on_list(list_of_dictionaries):
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


def get_download_url(url, tag):
    url_fixed = url.replace("//github.com/", "//codeload.github.com/") + "/zip/" + tag

    # log( 1, "get_download_url, url_fixed: " + url_fixed )
    return url_fixed


def fix_semantic_version(tag):
    """
        Returns a git tag on the format `0.0.0`.
    """
    regexes = [ ("(\d+)", ".0.0"), ("(\d+\.\d+)", ".0"), ("(\d+\.\d+\.\d+)", "") ]

    for search_data in reversed( regexes ):
        matches = re.search( search_data[0], tag )

        if matches:
            matched_text = tag[matches.start(0):matches.end(0)]
            return matches.group(0) + search_data[1], matched_text

    return tag, tag


def get_git_date(absolute_path, command_line_interface):
    """
        Get timestamp of the last commit in git repository
        https://gist.github.com/bitrut/1494315
    """
    # command = shlex.split( "git log -1 --date=iso" )
    command = shlex.split( "git log -1 --pretty=format:%ci" )
    output  = command_line_interface.execute( command, absolute_path, short_errors=True )

    if output is False:
        g_failed_repositories.append( (command, absolute_path) )
        return "2017-04-13 16:44:14"

    return output[0:19]


def get_git_tag_date(absolute_path, command_line_interface, tag):
    """
        Get timestamp of the specified tag in git repository
        https://gist.github.com/bitrut/1494315
    """
    # command = shlex.split( "git log -1 --date=iso" )
    command = shlex.split( "git log -1 --pretty=format:%ci {}".format( tag ) )
    output  = command_line_interface.execute( command, absolute_path, short_errors=True )

    if output is False:
        g_failed_repositories.append( (command, absolute_path) )

    return output[0:19]


def get_git_latest_tag(absolute_path, command_line_interface):
    """
        Get timestamp of the last commit in git repository
        https://gist.github.com/bitrut/1494315

        Getting latest tag on git repository
        https://gist.github.com/rponte/fdc0724dd984088606b0

        How can I list all tags in my Git repository by the date they were created?
        https://stackoverflow.com/questions/6269927/how-can-i-list-all-tags-in-my-git-repository-by-the-date-they-were-created

        How to sort git tags by version string order of form rc-X.Y.Z.W?
        https://stackoverflow.com/questions/14273531/how-to-sort-git-tags-by-version-string-order-of-form-rc-x-y-z-w/22634649#22634649
    """
    # command = shlex.split( "git log -1 --date=iso" )
    command = shlex.split( "git tag --sort=-creatordate --sort=version:refname" )

    git_tags  = command_line_interface.execute( command, absolute_path, short_errors=True )
    clean_tag = "master"

    if git_tags is False \
            or "warning:" in git_tags \
            or len( git_tags ) < 3:

        log( 1, "Error: Failed getting git tag for the package `%s`, results: %s" % ( absolute_path, git_tags ) )
        g_failed_repositories.append( (command, absolute_path) )

        return clean_tag

    git_tags  = git_tags.split( "\n" )
    clean_tag = git_tags[-1]

    # Takes the latest tag which is numeric on the form `0.0anything` (number.number)
    for index, git_tag in enumerate( git_tags ):

        if re.search( "^(\d+)\.(\d+)(.+)?$", git_tag ):
            clean_tag = git_tag

    return clean_tag


def create_git_tag(absolute_path, new_tag_name, command_line_interface):
    command = shlex.split( "git tag %s" % new_tag_name )
    output = command_line_interface.execute( command, absolute_path, short_errors=True )

    if output is False:
        log( 1, "Error: Failed creating git tag `%s` for the package `%s`, results: %s" % ( new_tag_name, absolute_path, output ) )

        g_failed_repositories.append( (command, absolute_path) )
        return False

    log( 1, "Creating git tag `%s` for the package `%s`, results: %s" % ( new_tag_name, absolute_path, output ) )
    return True


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
    tag_date      = tag_date.replace("-", ".")[0:10]
    patch_version = tag_date[5:].replace(".", "")

    return tag + "." + tag_date[:4] + "." + patch_version


def count_package_sections(gitModulesFile, sections):
    sections_count = 0

    for section in sections:
        path = gitModulesFile.get( section, "path" )

        if 'Packages' == path[0:8]:
            sections_count += 1

    return sections_count


def print_some_repositories(all_packages):
    index = 1

    for package in all_packages:
        index += 1

        if index > 10:
            break

        log( 1, "" )
        log( 1, "package: %-20s" %  str( package ) + json.dumps( all_packages[package], indent=4 ) )


class Repository():
    """
        Holds the information required by a Package Control Package or Dependency.
    """
    def __init__(self, gitModulesFile, section):
        # the main repository url as `github.com/user/repo`
        self.url = gitModulesFile.get( section, "url" )

        # the section name on the `.gitmodules` file for the current repository information
        self.section = section

        # the current `.gitmodules` configparser interator
        self.gitModulesFile = gitModulesFile

        if gitModulesFile.has_option( section, "upstream" ):
            self.upstream = gitModulesFile.get( section, "upstream" )

        else:
            self.upstream = ""

        # the dictionary with the current release_data and repository information
        self.info         = OrderedDict()
        self.release_data = OrderedDict()

        # relative path the the repository
        self.path = os.path.normpath( gitModulesFile.get( section, "path" ) )
        self.name = os.path.basename( self.path )

        # absolute path the the repository
        self.absolute_path = os.path.join( CHANNEL_ROOT_DIRECTORY, self.path )

        # the dictionary with the current  information
        self._setDependenciesList()

    def _setDependenciesList(self):
        self.load_order          = None
        self.isPackageDependency = False

        if self.gitModulesFile.has_option( self.section, "dependency" ):
            self.dependency_list = string_convert_list( self.gitModulesFile.get( self.section, "dependency" ) )

            if len( self.dependency_list ) > 0:

                try:
                    self.load_order = int( self.dependency_list[0] )

                    self.isPackageDependency = True
                    del self.dependency_list[0]

                except ValueError:
                    pass

        else:
            self.dependency_list = []

    def getDependenciesCount(self):
        return len( self.dependency_list )

    def getDependenciesList(self):
        return self.dependency_list

    def getSupposedUrl(self):
        return get_download_url( self.url, self.release_data['git_tag'] )

    def setVersioningTag(self, last_channel_file, command_line_interface):
        last_dictionary = get_dictionary_key( last_channel_file, self.name, {} )
        git_tag, date_tag, release_date = get_last_tag_fixed( self.absolute_path, last_dictionary, command_line_interface )

        self.release_data['date']    = release_date
        self.release_data['version'] = date_tag
        self.release_data['git_tag'] = git_tag

    def ensureAuthorName(self, user_forker):

        if 'authors' not in self.info:

            if len( self.upstream ) > 20:
                original_author      = get_user_name( self.upstream )
                self.info['authors'] = [ original_author ]

            else:
                # If there is not upstream set, then it is your own package (user_forker)
                self.info['authors'] = [user_forker]

        if user_forker not in self.info['authors']:
            self.info['authors'].append( "Forked by " + user_forker )

    def getOldCompatibleVersions(self, command_line_interface):
        """
            Check for the existence of the `tags` section on the `gitModulesFile` iterator and add the
            correct for the listed old compatible versions.

            The old compatible versions are git tags as `3143` which is the last Sublime Text version
            where the submodule was compatible with. For example, on Sublime Text development build
            3147, the package `Notepad++ Color Scheme` stopped working completely:
                1. https://github.com/SublimeTextIssues/Core/issues/1983)

            However the fix for build 3147 also broke completely the package for Sublime Text stable
            build 3143. Hence, we must to create a tag named 3143 which targets the last commit which is
            working for build 3143, then when some user using the stable build 3143 installs the
            Notepad++, they must install the one from the tag `3143`, and not the one from the master
            branch, which has the latest fixes for build development build 3147.

            @return a list of dictionary releases created, otherwise a empty list if not tags exists
        """
        greatest_tag    = get_version_number( self.release_data['sublime_text'] )
        tagged_releases = []

        if self.gitModulesFile.has_option( self.section, "tags" ):
            tags_list = string_convert_list( self.gitModulesFile.get( self.section, "tags" ) )

            for tag in tags_list:
                tag_interger = int( tag )

                release_data = OrderedDict()
                tag_date     = get_git_tag_date( self.absolute_path, command_line_interface, tag )

                release_data['platforms']    = "*"
                release_data['sublime_text'] = "<=%s" % tag

                if greatest_tag < tag_interger:
                    greatest_tag = tag_interger
                    self.release_data['sublime_text'] = ">" + tag

                release_data['url']     = get_download_url( self.url, tag )
                release_data['date']    = tag_date
                release_data['version'] = get_git_tag_version( tag_date, tag )

                tagged_releases.append( release_data )

        return tagged_releases

    def configureDependenciesFiles(self, repositories, dependencies):
        dependencies_json_path  = os.path.join( CHANNEL_ROOT_DIRECTORY, self.path, "dependencies.json" )
        sublime_dependency_path = os.path.join( CHANNEL_ROOT_DIRECTORY, self.path, ".sublime-dependency" )

        if self.isPackageDependency:
            self._addToDependenciesList( dependencies )
            self._createSublimeDependencyFile( sublime_dependency_path )

        else:
            self._addToRepositoriesList( repositories )
            # self._deleteSublimeDependencyFile( sublime_dependency_path )

        if self.getDependenciesCount() > 0:
            self.release_data['dependencies'] = self.dependency_list
            self._createDependenciesJson( dependencies_json_path )

        # else:
        #     self._deleteDependenciesJson( dependencies_json_path )

    def _deleteSublimeDependencyFile(self, sublime_dependency_path):
        remove_only_if_exists( sublime_dependency_path )

    def _createSublimeDependencyFile(self, sublime_dependency_path):

        with open( sublime_dependency_path, "w", newline='\n' ) as text_file:
            text_file.write( "%d\n" % self.load_order )

    def _deleteDependenciesJson(self, dependencies_json_path):
        remove_only_if_exists( dependencies_json_path )

    def _createDependenciesJson(self, dependencies_json_path):
        dependencies_json = {}
        platforms_versions_dependencies = [("*", "*", self.dependency_list)]

        for platform, sublime_version, dependency_list in platforms_versions_dependencies:
            dependencies_json[platform] = {sublime_version: dependency_list}

        write_data_file( dependencies_json_path, dependencies_json )

    def _addToDependenciesList(self, dependencies):
        """
            Add the `repository` to the `dependencies` list.
        """
        self.info['issues']     = self.url + "/issues"
        self.info['load_order'] = self.load_order

        self.release_data['url']  = self.getSupposedUrl()
        self.release_data['base'] = self.url
        self.release_data['tags'] = True

        dependencies.append( self.info )

    def _addToRepositoriesList(self, repositories):
        """
            Add the `repository` to the `repositories` list.
        """
        self.release_data['url'] = self.getSupposedUrl()
        repositories.append( self.info )

