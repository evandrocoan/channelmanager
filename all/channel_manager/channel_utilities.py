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
# Channel Manager Utilities, functions to be used by the common tasks
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
import json
import stat

import re
import time
import datetime
import textwrap

from collections import OrderedDict
from distutils.version import LooseVersion


# Relative imports in Python 3
# https://stackoverflow.com/questions/16981921/relative-imports-in-python-3
try:
    from . import settings

except( ImportError, ValueError):
    import settings


BASE_FILE_FOLDER          = os.path.join( settings.CURRENT_PACKAGE_ROOT_DIRECTORY, "all", "channel_manager", "base_file" )
UPGRADE_SESSION_FILE      = os.path.join( settings.CURRENT_PACKAGE_ROOT_DIRECTORY, "all", "last_sublime_upgrade.channel-manager" )
LAST_SUBLIME_TEXT_SECTION = "last_sublime_text_version"

# print_python_envinronment()
def assert_path(module):
    """
        Import a module from a relative path
        https://stackoverflow.com/questions/279237/import-a-module-from-a-relative-path
    """
    if module not in sys.path:
        sys.path.append( module )


# Allow using this file on the website where the sublime module is unavailable
try:
    import sublime
    import configparser

    try:
        from package_control.download_manager import downloader
        from package_control.package_manager import PackageManager

    except ImportError:

        try:
            from PackagesManager.packagesmanager.download_manager import downloader
            from PackagesManager.packagesmanager.package_manager import PackageManager

        except ImportError:
            PackageManager = None

    from python_debug_tools import Debugger

    # Debugger settings: 0 - disabled, 127 - enabled
    log = Debugger( 127, os.path.basename( __file__ ) )

except ImportError:
    sublime = None

    # Import the debugger. It will fail when `PythonDebugTools` is inside a `.sublime-package`,
    # however, this is only meant to be used on the Development version, when `PythonDebugTools` is
    # unpacked at the loose packages folder as a git submodule.
    assert_path( os.path.join( os.path.dirname( settings.CURRENT_PACKAGE_ROOT_DIRECTORY ), 'PythonDebugTools/all' ) )
    from python_debug_tools import Debugger


def write_data_file(file_path, channel_dictionary):
    """
        Python - json without whitespaces
        https://stackoverflow.com/questions/16311562/python-json-without-whitespaces
    """
    log( 1, "Writing to the data file: " + str( file_path ) )

    with open( file_path, 'w', newline='\n', encoding='utf-8' ) as output_file:
        json.dump( channel_dictionary, output_file, indent=4, separators=(',', ': ') )


def load_data_file(file_path, wait_on_error=True):
    """
        Attempt to read the file some times when there is a value error. This could happen when the
        file is currently being written by Sublime Text.
    """
    channel_dictionary = {}

    if os.path.exists( file_path ):
        error = None
        maximum_attempts = 10

        while maximum_attempts > 0:

            try:
                with open( file_path, 'r', encoding='utf-8' ) as data_file:
                    return json.load( data_file )

            except ValueError as error:
                log( 1, "Error: maximum_attempts %d, %s (%s)" % ( maximum_attempts, error, file_path ) )
                maximum_attempts -= 1

                if wait_on_error:
                    time.sleep( 0.1 )

        if maximum_attempts < 1:
            raise ValueError( "file_path: %s" % ( file_path ) )

    else:
        if sublime:

            try:
                packages_start = file_path.find( "Packages" )
                packages_relative_path = file_path[packages_start:].replace( "\\", "/" )

                log( 1, "load_data_file, packages_relative_path: " + str( packages_relative_path ) )
                resource_bytes = sublime.load_binary_resource( packages_relative_path )

                return json.loads( resource_bytes.decode('utf-8') )

            except IOError as error:
                log( 1, "Error on load_data_file(1), the file '%s' does not exists! %s" % ( file_path, error ) )

        else:
            log( 1, "Error on load_data_file(1), the file '%s' does not exists!" % file_path )

    return channel_dictionary


def load_repository_file(channel_repository_file, load_dependencies=True):
    repositories_dictionary = load_data_file( channel_repository_file )

    packages_list = get_dictionary_key( repositories_dictionary, 'packages', {} )
    last_packages_dictionary = {}

    if load_dependencies:
        dependencies_list = get_dictionary_key( repositories_dictionary, 'dependencies', {} )
        packages_list.extend( dependencies_list )

    for package in packages_list:
        last_packages_dictionary[package['name']] = package

    return last_packages_dictionary


def get_installed_packages(list_default_packages=False, exclusion_list=[]):

    if PackageManager:
        packages        = []
        package_manager = PackageManager()

        if list_default_packages:
            packages.extend( package_manager.list_default_packages() )

        packages.extend( package_manager.list_packages() )
        return list( set( packages ) - set( exclusion_list ) )

    else:
        raise ImportError( "You can only use the Sublime Text API inside Sublime Text." )


def get_git_modules_url(channel_root_url):
    return channel_root_url.replace( "//github.com/", "//raw.githubusercontent.com/" ) + "/master/.gitmodules"


def download_text_file( git_modules_url ):
    settings = {}
    downloaded_contents = None

    with downloader( git_modules_url, settings ) as manager:
        downloaded_contents = manager.fetch( git_modules_url, 'Error downloading git_modules_url: ' + git_modules_url )

    return downloaded_contents.decode('utf-8')


def string_convert_list( comma_separated_list ):

    if comma_separated_list:
        return [ dependency.strip() for dependency in comma_separated_list.split(',') ]

    return []


def get_main_directory(current_directory):
    possible_main_directory = os.path.normpath( os.path.dirname( os.path.dirname( current_directory ) ) )

    if sublime:
        sublime_text_packages = os.path.normpath( os.path.dirname( sublime.packages_path() ) )

        if possible_main_directory == sublime_text_packages:
            return possible_main_directory

        else:
            return sublime_text_packages

    return possible_main_directory


def run_channel_setup(channel_settings, channel_package_name, channel_package_directory):
    channel_directory = get_main_directory( channel_package_directory )

    user_folder = os.path.join( channel_directory, "Packages", "User" )
    channel_settings['CHANNEL_INSTALLATION_DETAILS'] = os.path.join( user_folder, channel_package_name + ".json" )

    channel_settings['USER_FOLDER_PATH']   = user_folder
    channel_settings['USER_SETTINGS_FILE'] = "Preferences.sublime-settings"

    channel_settings['CHANNEL_PACKAGE_NAME']    = channel_package_name
    channel_settings['CHANNEL_ROOT_DIRECTORY']  = channel_directory
    channel_settings['TEMPORARY_FOLDER_TO_USE'] = "__channel_temporary_directory"

    if os.path.exists( os.path.join( channel_package_directory, "settings.py" ) ):
        generate_channel_files( channel_package_name, channel_package_directory )


def generate_channel_files(channel_package_name, channel_package_directory):
    _configure_channel_menu_file( channel_package_name, channel_package_directory )
    _configure_channel_runner_file( channel_package_name, channel_package_directory )
    _configure_channel_commands_file( channel_package_name, channel_package_directory )


def convert_to_pascal_case(input_string):
    """
        how to replace multiple characters in a string?
        https://stackoverflow.com/questions/21859203/how-to-replace-multiple-characters-in-a-string
    """
    clean_string = re.sub( '[=+-:*?"<>|]', ' ', input_string )
    return ''.join( word[0].upper() + word[1:] if len( word ) else word for word in clean_string.split() )


def convert_to_snake_case(pascal_case_name):
    """
        Elegant Python function to convert CamelCase to snake_case?
        https://stackoverflow.com/questions/1175208/elegant-python-function-to-convert-camelcase-to-snake-case
    """
    first_substitution = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', pascal_case_name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', first_substitution).lower()


def _get_base_and_destine_paths(base_file_name, destine_file_name, channel_package_directory):
    base_file    = os.path.join( BASE_FILE_FOLDER, base_file_name )
    destine_file = os.path.join( channel_package_directory, destine_file_name )
    return base_file, destine_file


def _configure_channel_runner_file(channel_package_name, channel_package_directory):
    pascal_case_name = convert_to_pascal_case( channel_package_name )
    base_file, destine_file = _get_base_and_destine_paths( "commands.py", "commands.py", channel_package_directory )

    with open( base_file, "r", encoding='utf-8' ) as file:
        text = file.read()
        text = text.replace( "MyBrandNewChannel", pascal_case_name )

        with open( destine_file, "w", newline='\n', encoding='utf-8' ) as file:
            file.write( text )


def _configure_channel_menu_file(channel_package_name, channel_package_directory):
    pascal_case_name = convert_to_pascal_case( channel_package_name )
    snake_case_name  = convert_to_snake_case( pascal_case_name )

    # Use the extension `.js` instead of `sublime-menu` to not allow Sublime Text load the template file
    base_file, destine_file = _get_base_and_destine_paths( "Main.js", "Main.sublime-menu", channel_package_directory )

    with open( base_file, "r", encoding='utf-8' ) as file:
        text = file.read()

        text = text.replace( "MyBrandNewChannel", channel_package_name )
        text = text.replace( "my_brand_new_channel", snake_case_name )

        with open( destine_file, "w", newline='\n', encoding='utf-8' ) as file:
            file.write( text )


def _configure_channel_commands_file(channel_package_name, channel_package_directory):
    pascal_case_name = convert_to_pascal_case( channel_package_name )
    snake_case_name  = convert_to_snake_case( pascal_case_name )

    # Use the extension `.js` instead of `sublime-menu` to not allow Sublime Text load the template file
    base_file, destine_file = _get_base_and_destine_paths( "Default.js", "Default.sublime-commands", channel_package_directory )

    with open( base_file, "r", encoding='utf-8' ) as file:
        text = file.read()

        text = text.replace( "MyBrandNewChannel", channel_package_name )
        text = text.replace( "my_brand_new_channel", snake_case_name )

        with open( destine_file, "w", newline='\n', encoding='utf-8' ) as file:
            file.write( text )


def print_all_variables_for_debugging(dictionary):
    dictionary_lines = dictionary_to_string_by_line( dictionary )
    log( 1, "\nImporting %s settings... \n%s" % ( str(datetime.datetime.now())[0:19], dictionary_lines ) )


def print_data_file(file_path):
    channel_dictionary = load_data_file( file_path )
    log( 1, "channel_dictionary: " + json.dumps( channel_dictionary, indent=4, sort_keys=True ) )


def print_failed_repositories(failed_repositories):

    if len( failed_repositories ) > 0:
        sublime.active_window().run_command( "show_panel", {"panel": "console", "toggle": False} )

        log.insert_empty_line()
        log.insert_empty_line()
        log( 1, "The following repositories failed their commands..." )

    for package_name in failed_repositories:
        log( 1, "Package: %s" % ( package_name ) )


def get_dictionary_key(dictionary, key, default=None):

    if key in dictionary:
        return dictionary[key]

    return default


def sort_dictionary(dictionary):
    return OrderedDict( sorted( dictionary.items() ) )


def remove_if_exists(items_list, item):

    if item in items_list:
        items_list.remove( item )


def add_item_if_not_exists(list_to_append, item):

    if item not in list_to_append:
        list_to_append.append( item )


def remove_item_if_exists(list_to_remove, item):

    if item in list_to_remove:
        list_to_remove.remove( item )


def safe_remove(path):

    try:
        os.remove( path )

    except Exception as error:
        log( 1, "Failed to remove `%s`. Error is: %s" % ( path, error) )

        try:
            delete_read_only_file(path)

        except Exception as error:
            log( 1, "Failed to remove `%s`. Error is: %s" % ( path, error) )


def remove_only_if_exists(file_path):

    if os.path.exists( file_path ):
        safe_remove( file_path )


def delete_read_only_file(path):
    _delete_read_only_file( None, path, None )


def _delete_read_only_file(action, name, exc):
    """
        shutil.rmtree to remove readonly files
        https://stackoverflow.com/questions/21261132/shutil-rmtree-to-remove-readonly-files
    """
    os.chmod( name, stat.S_IWRITE )
    os.remove( name )


def recursively_delete_empty_folders(root_folder, folders_not_empty=[]):
    """
        Recursively descend the directory tree rooted at top, calling the callback function for each
        regular file.

        Python script: Recursively remove empty folders/directories
        https://www.jacobtomlinson.co.uk/2014/02/16/python-script-recursively-remove-empty-folders-directories/

        @param root_folder           the folder to search on
        @param folders_not_empty     a empty python list to put on the deleted folders paths
    """

    try:
        children_folders = os.listdir( root_folder )

        for child_folder in children_folders:
            child_path = os.path.join( root_folder, child_folder )

            if os.path.isdir( child_path ):
                recursively_delete_empty_folders( child_path, folders_not_empty )

                try:
                    os.removedirs( root_folder )
                    is_empty = True

                except OSError:
                    is_empty = False

                    try:
                        _removeEmptyFolders( root_folder )

                    except:
                        pass

                if not is_empty:
                    folders_not_empty.append( child_path )

        os.rmdir( root_folder )

    except:
        pass


def _removeEmptyFolders(path):

    if not os.path.isdir( path ):
        return

    files = os.listdir( path )

    if len( files ):

        for file in files:
            fullpath = os.path.join( path, file )

            if os.path.isdir( fullpath ):
                _removeEmptyFolders( fullpath )

    os.rmdir( path )


def get_immediate_subdirectories(a_dir):
    """
        How to get all of the immediate subdirectories in Python
        https://stackoverflow.com/questions/800197/how-to-get-all-of-the-immediate-subdirectories-in-python
    """
    return [ name for name in os.listdir(a_dir) if os.path.isdir( os.path.join( a_dir, name ) ) ]


def wrap_text(text):
    return re.sub( r"(?<!\n)\n(?!\n)", " ", textwrap.dedent( text ).strip( " " ) )


def unique_list_join(*lists):
    unique_list = []

    for _list in lists:

        for item in _list:

            if item not in unique_list:
                unique_list.append( item )

    return unique_list


def unique_list_append(a_list, *lists):

    for _list in lists:

        for item in _list:

            if item not in a_list:
                a_list.append( item )


def upcase_first_letter(s):
    return s[0].upper() + s[1:]


def _clean_urljoin(url):

    if url.startswith( '/' ) or url.startswith( ' ' ):
        url = url[1:]
        url = _clean_urljoin( url )

    if url.endswith( '/' ) or url.endswith( ' ' ):
        url = url[0:-1]
        url = _clean_urljoin( url )

    return url


def clean_urljoin(*urls):
    fixed_urls = []

    for url in urls:

        fixed_urls.append( _clean_urljoin(url) )

    return "/".join( fixed_urls )


def dictionary_to_string_by_line(dictionary):
    variables = \
    [
        "%-30s: %s" % ( variable_name, dictionary[variable_name] )
        for variable_name in dictionary.keys()
    ]

    return "%s" % ( "\n".join( sorted( variables ) ) )


def convert_to_unix_path(relative_path):
    relative_path = relative_path.replace( "\\", "/" )

    if relative_path.startswith( "/" ):
        relative_path = relative_path[1:]

    return relative_path


def is_sublime_text_upgraded(caller_indentifier):
    """
        @return True   when it is the fist time this function is called or there is a sublime text
                       upgrade, False otherwise.
    """
    last_version    = 0
    current_version = int( sublime.version() )

    last_section = _open_last_session_data( UPGRADE_SESSION_FILE )
    has_section  = last_section.has_section( LAST_SUBLIME_TEXT_SECTION )

    if has_section:

        if last_section.has_option( LAST_SUBLIME_TEXT_SECTION, caller_indentifier ):
            last_version = int( last_section.getint( LAST_SUBLIME_TEXT_SECTION, caller_indentifier ) )

    else:
        last_section.add_section( LAST_SUBLIME_TEXT_SECTION )

    last_section.set( LAST_SUBLIME_TEXT_SECTION, caller_indentifier, str( current_version ) )
    save_session_data( last_section, UPGRADE_SESSION_FILE )

    return last_version < current_version


def _open_last_session_data(session_file):
    last_section = configparser.ConfigParser( allow_no_value=True )

    if os.path.exists( session_file ):
        last_section.read( session_file )

    return last_section


def save_session_data(last_section, session_file):

    with open( session_file, 'wt', newline='\n', encoding='utf-8' ) as configfile:
        last_section.write( configfile )


def is_channel_upgraded(channel_settings):
    channelSettings     = load_data_file( channel_settings['CHANNEL_REPOSITORY_FILE'] )
    userChannelSettings = load_data_file( channel_settings['CHANNEL_INSTALLATION_DETAILS'] )

    current_version      = get_dictionary_key( channelSettings, 'current_version', '0.0.0' )
    user_current_version = get_dictionary_key( userChannelSettings, 'current_version', '0.0.0' )

    return LooseVersion( current_version ) > LooseVersion( user_current_version )


class NoPackagesAvailable(Exception):

    def __init__(self, message=""):
        super().__init__( message )


class InstallationCancelled(Exception):

    def __init__(self, message=""):
        super().__init__( message )

