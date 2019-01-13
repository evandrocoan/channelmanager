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
# Copyright (C) 2017-2019 Evandro Coan <https://github.com/evandrocoan>
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
import shutil

import re
import datetime
import textwrap

from collections import OrderedDict
from distutils.version import LooseVersion


# Relative imports in Python 3
# https://stackoverflow.com/questions/16981921/relative-imports-in-python-3
try:
    from . import settings as g_settings

except( ImportError, ValueError):
    import settings as g_settings


BASE_FILE_FOLDER          = os.path.join( g_settings.PACKAGE_ROOT_DIRECTORY, "all", "channel_manager", "base_file" )
UPGRADE_SESSION_FILE      = os.path.join( g_settings.PACKAGE_ROOT_DIRECTORY, "all", "last_session.json" )
LAST_SUBLIME_TEXT_SECTION = "last_sublime_text_version"


def assert_path(*args):
    """
        Import a module from a relative path
        https://stackoverflow.com/questions/279237/import-a-module-from-a-relative-path
    """
    module = os.path.realpath( os.path.join( *args ) )
    if module not in sys.path:
        sys.path.append( module )


try:
    from package_control.download_manager import downloader
    from package_control.package_manager import PackageManager

except ImportError:

    try:
        from PackagesManager.package_control.download_manager import downloader
        from PackagesManager.package_control.package_manager import PackageManager

    except ImportError:
        PackageManager = None


# Allow using this file on the website where the sublime module is unavailable
try:
    import sublime

except ImportError:
    sublime = None


try:
    import debug_tools

except ImportError:
    # Import the debugger. It will fail when `debug_tools` is inside a `.sublime-package`,
    # however, this is only meant to be used on the Development version, when `debug_tools` is
    # unpacked at the loose packages folder as a git submodule.
    assert_path( os.path.join( os.path.dirname( g_settings.PACKAGE_ROOT_DIRECTORY ), 'debugtools', 'all' ) )

from debug_tools import getLogger
from debug_tools.third_part import load_data_file
from debug_tools.third_part import write_data_file


# Debugger settings: 0 - disabled, 127 - enabled
log = getLogger( 127, __name__ )


def is_dependency(package_name, repositories_dictionary):
    """
        Return by default True to stop the installation as the package not was not found on the
        `channel.json` repository file
    """
    if package_name in repositories_dictionary:
        package_dicitonary = repositories_dictionary[package_name]
        return "load_order" in package_dicitonary

    log( 1, "Warning: The package name `%s` could not be found on the repositories_dictionary!" % package_name )
    return True


def is_package_dependency(package_name, dependencies, packages):
    """
        Return by default True to stop the uninstallation as the package not was not found on the
        `channel.json` repository file
    """
    if package_name in dependencies:
        return True

    if package_name in packages:
        return False

    log( 1, "Warning: The package name `%s` could not be found on the repositories_dictionary!" % package_name )
    return True


def load_repository_file(channel_repository_file, load_dependencies=True):
    repositories_dictionary = load_data_file( channel_repository_file )

    packages_list = repositories_dictionary.get( 'packages', [] )
    last_packages_dictionary = {}

    if load_dependencies:
        dependencies_list = repositories_dictionary.get( 'dependencies', [] )
        packages_list.extend( dependencies_list )

    for package in packages_list:
        last_packages_dictionary[package['name']] = package

    return last_packages_dictionary


def get_installed_packages(exclusion_list=[], list_default_packages=False, list_dependencies=False):

    if PackageManager:
        packages        = []
        package_manager = PackageManager()

        if list_default_packages:
            packages.extend( package_manager.list_default_packages() )
            packages.extend( ["Default", "User"] )

        if list_dependencies:
            packages.extend( package_manager.list_dependencies() )

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


def look_for_invalid_packages(channel_settings, installed_packages):
    look_for_invalid_default_ignored_packages( installed_packages )

    look_for_invalid_development_ignored_packages( channel_settings, installed_packages, "FORBIDDEN_PACKAGES" )
    look_for_invalid_development_ignored_packages( channel_settings, installed_packages, "PACKAGES_TO_INSTALL_EXCLUSIVELY" )
    look_for_invalid_development_ignored_packages( channel_settings, installed_packages, "PACKAGES_TO_IGNORE_ON_DEVELOPMENT" )
    look_for_invalid_development_ignored_packages( channel_settings, installed_packages, "PACKAGES_TO_NOT_INSTALL_STABLE" )
    look_for_invalid_development_ignored_packages( channel_settings, installed_packages, "PACKAGES_TO_NOT_INSTALL_DEVELOPMENT" )

    look_for_inconsistent_ignored_packages( channel_settings )


def look_for_invalid_default_ignored_packages(installed_packages):
    user_settings    = sublime.load_settings( "Preferences.sublime-settings" )
    ignored_packages = user_settings.get( "ignored_packages", [] )

    for package_name in ignored_packages:

        if package_name not in installed_packages:
            log( 1, "Warning: The package `%s` on your User `ignored_packages` setting was not found installed!" % package_name )


def look_for_invalid_development_ignored_packages(channel_settings, installed_packages, setting_name):
    ignored_packages = channel_settings[setting_name]

    for package_name in ignored_packages:

        if package_name not in installed_packages:
            log( 1, "%s Warning: The package `%s` on the `%s` setting was found not installed!" % (
                    channel_settings['CHANNEL_PACKAGE_NAME'], package_name, setting_name ) )


def look_for_inconsistent_ignored_packages(channel_settings):
    user_settings = sublime.load_settings( "Preferences.sublime-settings" )
    user_ignored_packages = user_settings.get( "ignored_packages", [] )
    channel_ignored_packages = channel_settings["PACKAGES_TO_IGNORE_ON_DEVELOPMENT"]

    def message1(package_name):
        log( 1, "Warning: The package `%s` was not found on PACKAGES_TO_IGNORE_ON_DEVELOPMENT!" % package_name )

    def message2(package_name):
        log( 1, "Warning: The package `%s` was not found on your Packages/User ignored_packages!" % package_name )

    def call_message(from_list, to_list, message):

        # If the `to_list` has no elements, then we should not attempt to match otherwise we would
        # produce a bunch of non-existent warnings when the PACKAGES_TO_INSTALL_EXCLUSIVELY setting
        # is used
        if to_list:

            for package_name in from_list:

                if package_name not in to_list:
                    message(package_name)

    call_message(user_ignored_packages, channel_ignored_packages, message1)
    call_message(channel_ignored_packages, user_ignored_packages, message2)


def run_channel_setup(channel_settings, channel_package_file):
    channel_package_directory = channel_package_file.replace( ".sublime-package", "" )

    channel_package_name = os.path.basename( channel_package_directory )
    channel_directory    = get_main_directory( channel_package_directory )

    if channel_package_name not in channel_settings['FORBIDDEN_PACKAGES']:
        channel_settings['FORBIDDEN_PACKAGES'].append( channel_package_name )

    channel_settings['INSTALLER_TYPE']    = ""
    channel_settings['INSTALLATION_TYPE'] = ""

    channel_settings['FORBIDDEN_PACKAGES'].sort()
    channel_settings['PACKAGES_TO_INSTALL_EXCLUSIVELY'].sort()
    channel_settings['PACKAGES_TO_IGNORE_ON_DEVELOPMENT'].sort()
    channel_settings['PACKAGES_TO_NOT_INSTALL_STABLE'].sort()
    channel_settings['PACKAGES_TO_NOT_INSTALL_DEVELOPMENT'].sort()

    user_folder = os.path.join( channel_directory, "Packages", "User" )
    channel_settings['CHANNEL_INSTALLATION_DETAILS'] = os.path.join( user_folder, channel_package_name + ".json" )

    channel_settings['USER_FOLDER_PATH']   = user_folder
    channel_settings['USER_SETTINGS_FILE'] = "Preferences.sublime-settings"
    channel_settings['CHANNEL_PACKAGE_METADATA'] = os.path.join( "Packages", channel_package_name, "package-metadata.json" )

    channel_settings['CHANNEL_PACKAGE_NAME']    = channel_package_name
    channel_settings['CHANNEL_ROOT_DIRECTORY']  = channel_directory
    channel_settings['TEMPORARY_FOLDER_TO_USE'] = "__channel_temporary_directory"

    generate_channel_files( channel_package_name, channel_package_directory, channel_package_file )


def generate_channel_files(channel_package_name, channel_package_directory, channel_package_file):

    if not channel_package_file.endswith( ".sublime-package" ):
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

        if not compare_text_with_file( text, destine_file ):

            with open( destine_file, "w", newline='\n', encoding='utf-8' ) as file:
                file.write( text )


def _configure_channel_menu_file(channel_package_name, channel_package_directory):
    pascal_case_name = convert_to_pascal_case( channel_package_name )
    snake_case_name  = convert_to_snake_case( pascal_case_name )

    # Use the extension `.js` instead of `sublime-menu` to not allow Sublime Text load the template file
    base_file, destine_file = _get_base_and_destine_paths( "Main.json", "Main.sublime-menu", channel_package_directory )

    with open( base_file, "r", encoding='utf-8' ) as file:
        text = file.read()
        text = text.replace( "MyBrandNewChannel", channel_package_name )
        text = text.replace( "my_brand_new_channel", snake_case_name )

        if not compare_text_with_file( text, destine_file ):

            with open( destine_file, "w", newline='\n', encoding='utf-8' ) as file:
                file.write( text )


def _configure_channel_commands_file(channel_package_name, channel_package_directory):
    pascal_case_name = convert_to_pascal_case( channel_package_name )
    snake_case_name  = convert_to_snake_case( pascal_case_name )

    # Use the extension `.js` instead of `sublime-menu` to not allow Sublime Text load the template file
    base_file, destine_file = _get_base_and_destine_paths( "Default.json", "Default.sublime-commands", channel_package_directory )

    with open( base_file, "r", encoding='utf-8' ) as file:
        text = file.read()
        text = text.replace( "MyBrandNewChannel", channel_package_name )
        text = text.replace( "my_brand_new_channel", snake_case_name )

        if not compare_text_with_file( text, destine_file ):

            with open( destine_file, "w", newline='\n', encoding='utf-8' ) as file:
                file.write( text )


def compare_text_with_file(input_text, file):
    """
        Return `True` when the provided text and the `file` contents are equal.
    """

    if os.path.exists( file ):

        with open( file, "r", encoding='utf-8' ) as file:
            text = file.read()
            return input_text == text


def print_all_variables_for_debugging(dictionary):
    dictionary_lines = dictionary_to_string_by_line( dictionary )
    log( 1, "\nImporting %s settings... \n%s" % ( str(datetime.datetime.now())[0:19], dictionary_lines ) )


def print_data_file(file_path):
    channel_dictionary = load_data_file( file_path )
    log( 1, "channel_dictionary: " + json.dumps( channel_dictionary, indent=4, sort_keys=True ) )


def print_failed_repositories(failed_repositories):

    if len( failed_repositories ) > 0:
        sublime.active_window().run_command( "show_panel", {"panel": "console", "toggle": False} )

        log.newline( count=2 )
        log( 1, "The following repositories failed their commands..." )

    for package_name in failed_repositories:
        log( 1, "Package: %s" % ( package_name ) )


def add_item_if_not_exists(list_to_append, item):

    if item not in list_to_append:
        list_to_append.append( item )


def add_path_if_not_exists(list_to_add, path):

    if path != "." and path != "..":
        add_item_if_not_exists( list_to_add, path )


def add_git_folder_by_file(file_relative_path, git_folders):
    match = re.search( "\.git", file_relative_path )

    if match:
        git_folder_relative = file_relative_path[:match.end(0)]

        if git_folder_relative not in git_folders:
            git_folders.append( git_folder_relative )


def sort_dictionary(dictionary):
    return OrderedDict( sorted( dictionary.items() ) )


def sort_dictionaries_on_list(list_of_dictionaries):
    sorted_dictionaries = []

    for dictionary in list_of_dictionaries:
        sorted_dictionaries.append( sort_dictionary( dictionary ) )

    return sorted_dictionaries


def sort_list_of_dictionaries(list_of_dictionaries):
    """
        How do I sort a list of dictionaries by values of the dictionary in Python?
        https://stackoverflow.com/questions/72899/how-do-i-sort-a-list-of-dictionaries-by-values-of-the-dictionary-in-python

        case-insensitive list sorting, without lowercasing the result?
        https://stackoverflow.com/questions/10269701/case-insensitive-list-sorting-without-lowercasing-the-result
    """
    sorted_dictionaries = sort_dictionaries_on_list( list_of_dictionaries )
    return sorted( sorted_dictionaries, key=lambda k: k['name'].lower() )


def is_directory_empty(directory_path):
    """
        How to check to see if a folder contains files using python 3
        https://stackoverflow.com/questions/25675352/how-to-check-to-see-if-a-folder-contains-files-using-python-3
    """
    is_empty = False

    try:
        os.rmdir( directory_path )

    except OSError:
        is_empty = True

    return is_empty


def remove_if_exists(items_list, item):

    if item in items_list:
        items_list.remove( item )


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


def remove_git_folder(default_git_folder, parent_folder=None):
    log( 1, "remove_git_folder, default_git_folder: %s" % str( default_git_folder ) )
    shutil.rmtree( default_git_folder, ignore_errors=True, onerror=_delete_read_only_file )

    if parent_folder:
        folders_not_empty = []
        recursively_delete_empty_folders( parent_folder, folders_not_empty )

        if len( folders_not_empty ) > 0:
            log( 1, "The installed default_git_folder `%s` could not be removed because is it not empty." % default_git_folder )
            log( 1, "Its files contents are: " + str( os.listdir( default_git_folder ) ) )


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
        "%-50s: %s" % ( variable_name, dictionary[variable_name] )
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
    current_version = int( sublime.version() )
    last_session = load_data_file( UPGRADE_SESSION_FILE )

    section = last_session.get( LAST_SUBLIME_TEXT_SECTION, {} )
    last_version = section.get( caller_indentifier, 0 )

    section[caller_indentifier] = current_version
    last_session[LAST_SUBLIME_TEXT_SECTION] = section

    if last_version != current_version:
        write_data_file( UPGRADE_SESSION_FILE, last_session, 0 )

    return last_version < current_version


def is_channel_upgraded(channel_settings):
    package_version = ""

    try:
        packageChannelSettings = load_data_file( channel_settings['CHANNEL_PACKAGE_METADATA'], log_level=0, exceptions=True )
        package_version = packageChannelSettings.get( 'version', "" )

    except Exception as error:
        log( 1, "Skipping channel upgrade as could not load `package-metadata.json` due: %s", error )

        write_data_file( os.path.join( os.path.dirname( sublime.packages_path() ), channel_settings['CHANNEL_PACKAGE_METADATA'] ),
            {
                "dependencies": [],
                "description": "No description available.",
                "platforms": "*",
                "sublime_text": ">3114",
                "url": "https://github.com/evandrocoan/StudioChannel",
                "version": "0.0.0"
            }
        )
        return False

    userChannelSettings = load_data_file( channel_settings['CHANNEL_INSTALLATION_DETAILS'] )
    user_version = userChannelSettings.get( 'current_version' )

    try:

        if not user_version:
            raise Exception( "There is no old version available for update checking." )

        return LooseVersion( package_version ) > LooseVersion( user_version )

    except Exception:
        log.exception( "Error: Could not check for the channel upgrade: `%s` - `%s`", package_version, user_version )

        userChannelSettings['current_version'] = "0.0.0"
        write_data_file( channel_settings['CHANNEL_INSTALLATION_DETAILS'], userChannelSettings )

    return False


class NoPackagesAvailable(Exception):

    def __init__(self, message=""):
        super().__init__( message )


class InstallationCancelled(Exception):

    def __init__(self, message=""):
        super().__init__( message )

