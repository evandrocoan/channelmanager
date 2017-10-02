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

import os
import sys
import zipfile

import io
import threading
import contextlib


# https://stackoverflow.com/questions/14087598/python-3-importerror-no-module-named-configparser
try:
    import configparser
    from configparser import NoOptionError

except:
    from six.moves import configparser
    from six.moves.configparser import NoOptionError


def assert_path(module):
    """
        Import a module from a relative path
        https://stackoverflow.com/questions/279237/import-a-module-from-a-relative-path
    """
    if module not in sys.path:
        sys.path.append( module )


CURRENT_DIRECTORY = os.path.dirname( os.path.realpath( __file__ ) )
CHANNEL_SETTINGS  = CURRENT_DIRECTORY + ".sublime-settings"

# Do not try to install this own package and the Package Control, as they are currently running
PACKAGES_TO_IGNORE = [ "Package Control", os.path.basename( CURRENT_DIRECTORY ) ]

# print( "CURRENT_DIRECTORY: " + CURRENT_DIRECTORY )
assert_path( os.path.join( os.path.dirname( CURRENT_DIRECTORY ), 'PythonDebugTools/all' ) )
assert_path( os.path.join( os.path.dirname( CURRENT_DIRECTORY ), "Package Control" ) )


from .channel_manager import string_convert_list

from package_control import cmd
from package_control.download_manager import downloader

from package_control.package_manager import PackageManager
from package_control.thread_progress import ThreadProgress
from package_control.commands.advanced_install_package_command import AdvancedInstallPackageThread


# Import the debugger
from debug_tools import Debugger

# Debugger settings: 0 - disabled, 127 - enabled
log = Debugger( 127, os.path.basename( __file__ ) )

log( 2, "..." )
log( 2, "..." )
log( 2, "Debugging" )
log( 2, "CURRENT_DIRECTORY:     " + CURRENT_DIRECTORY )


def main(command="stable"):
    log( 2, "Entering on main(0)" )

    global STUDIO_MAIN_URL
    global STUDIO_MAIN_DIRECTORY

    STUDIO_MAIN_URL       = "https://github.com/evandrocoan/SublimeTextStudio"
    STUDIO_MAIN_DIRECTORY = os.path.dirname( sublime.packages_path() )

    log( 2, "STUDIO_MAIN_URL:       " + STUDIO_MAIN_URL )
    log( 2, "STUDIO_MAIN_DIRECTORY: " + STUDIO_MAIN_DIRECTORY )

    installer_thread = CopyFilesThread( True if command == "development" else False )
    installer_thread.start()

    ThreadProgress( installer_thread, 'Installing Sublime Text Studio %s Packages' % command,
            'Sublime Text Studio %s was successfully installed.' % command )


class CopyFilesThread(threading.Thread):

    def __init__(self, is_development_install):
        threading.Thread.__init__(self)
        self.is_development_install = is_development_install

    def run(self):
        log( 2, "Entering on run(1)" )
        command_line_interface = cmd.Cli( None, True )

        git_executable_path = command_line_interface.find_binary( "git.exe" if os.name == 'nt' else "git" )
        log( 2, "run, git_executable_path: " + str( git_executable_path ) )

        if self.is_development_install:
            clone_sublime_text_studio( command_line_interface, git_executable_path )

        install_modules( command_line_interface, git_executable_path, self.is_development_install )


def clone_sublime_text_studio(command_line_interface, git_executable_path):
    """
        Clone the main repository `https://github.com/evandrocoan/SublimeTextStudio`
        and install it on the Sublime Text Data folder.
    """
    main_git_folder = os.path.join( STUDIO_MAIN_DIRECTORY, ".git" )

    if os.path.exists( main_git_folder ):
        raise ValueError("The folder '%s' already exists. You already has some custom studio git installation." % main_git_folder)


def install_modules(command_line_interface, git_executable_path, is_development_install):
    log( 2, "PACKAGES_TO_IGNORE: " + str( PACKAGES_TO_IGNORE ) )

    if is_development_install:
        clone_submodules( command_line_interface, git_executable_path )

    else:
        git_modules_url  = get_git_modules_url()
        git_modules_file = download_text_file( git_modules_url )
        git_packages     = get_git_modules_packages( git_modules_file )

        log( 2, "git_packages: " + str( git_packages ) )
        install_sublime_packages( git_packages )

    set_default_settings()


def set_default_settings():
    userSettings   = sublime.load_settings("Preferences.sublime-settings")
    studioSettings = sublime.load_settings(CHANNEL_SETTINGS)

    studio_ignored_packages = []
    user_ignored_packages   = userSettings.get("ignored_packages", [])
    packages_to_ignore      = studioSettings.get("packages_to_ignored", [])

    for package in packages_to_ignore:

        if package not in user_ignored_packages:
            user_ignored_packages.append(package)
            studio_ignored_packages.append(package)

    userSettings.set("ignored_packages", user_ignored_packages)
    studioSettings.set("ignored_packages", studio_ignored_packages)

    sublime.save_settings("Preferences.sublime-settings")
    sublime.save_settings(CHANNEL_SETTINGS)


def install_sublime_packages(git_packages):
    """
        python multithreading wait till all threads finished
        https://stackoverflow.com/questions/11968689/python-multithreading-wait-till-all-threads-finished

        There is a bug with the AdvancedInstallPackageThread thread which trigger several errors of:

        "It appears a package is trying to ignore itself, causing a loop.
        Please resolve by removing the offending ignored_packages setting."

        When trying to install several package at once, then here I am installing them one by one.
    """
    # Package Control: Advanced Install Package
    # https://github.com/wbond/package_control/issues/1191
    # thread = AdvancedInstallPackageThread( git_packages )
    # thread.start()
    # thread.join()

    log( 2, "PACKAGES_TO_IGNORE: " + str( PACKAGES_TO_IGNORE ) )
    package_manager = PackageManager()

    for package, is_dependency in git_packages:
        log( 1, "\nInstalling: %s (%s)" % ( str( package ), str( is_dependency ) ) )

        if package not in PACKAGES_TO_IGNORE:
            package_manager.install_package( package, is_dependency )


def get_git_modules_packages( git_modules_file ):
    """
        python ConfigParser: read configuration from string
        https://stackoverflow.com/questions/27744058/python-configparser-read-configuration-from-string
    """
    packages = []
    gitModulesFile = configparser.RawConfigParser()

    index = 0
    gitModulesFile.readfp( io.StringIO( git_modules_file ) )

    for section in gitModulesFile.sections():
        # # For quick testing
        # index += 1
        # if index > 4:
        #     break

        path = gitModulesFile.get( section, "path" )
        log( 2, "path: " + path )

        if 'Packages' == path[0:8]:
            submodule_absolute_path = os.path.join( STUDIO_MAIN_DIRECTORY, path )
            # log( 4, "submodule_absolute_path: " + submodule_absolute_path )

            if not os.path.isdir( submodule_absolute_path ):
                packages.append( ( os.path.basename( path ), is_dependency( gitModulesFile, section ) ) )

    return packages


def is_dependency(gitModulesFile, section):

    if gitModulesFile.has_option( section, "dependency" ):
        dependency_list = string_convert_list( gitModulesFile.get( section, "dependency" ) )

        if len( dependency_list ) > 0:

            try:
                int( dependency_list[0] )
                return True

            except ValueError:
                return False

    return False


def get_git_modules_url():
    return STUDIO_MAIN_URL.replace("//github.com/", "//raw.githubusercontent.com/") + "/master/.gitmodules"


def download_text_file( git_modules_url ):
    settings = {}
    downloaded_contents = None

    with downloader( git_modules_url, settings ) as manager:
        downloaded_contents = manager.fetch( git_modules_url, 'Error downloading git_modules_url: ' + git_modules_url )

    return downloaded_contents.decode('utf-8')


def clone_submodules(command_line_interface, git_executable_path):
    gitFilePath    = os.path.join( STUDIO_MAIN_DIRECTORY, '.gitmodules' )
    gitModulesFile = configparser.RawConfigParser()

    index = 0
    gitModulesFile.read( gitFilePath )

    for section in gitModulesFile.sections():
        url  = gitModulesFile.get( section, "url" )
        path = gitModulesFile.get( section, "path" )

        # For quick testing
        index += 1
        if index > 3:
            break

        package_name = os.path.basename( path )
        log( 1, "\nInstalling: %s" % ( package_name ) )

        if package_name not in PACKAGES_TO_IGNORE:

            if 'Packages' == path[0:8]:
                submodule_absolute_path = os.path.join( STUDIO_MAIN_DIRECTORY, path )

                if not os.path.isdir( submodule_absolute_path ):
                    command = shlex.split( '"%s" clone --recursive "%s" "%s"', git_executable_path, url, path )
                    output  = command_line_interface.execute( command, cwd=STUDIO_MAIN_DIRECTORY )

                    log( 1, output )


def check_installed_packages():
    studioSettings         = sublime.load_settings(CHANNEL_SETTINGS)
    packageControlSettings = sublime.load_settings("Package Control.sublime-settings")

    # installed_packages =


if __name__ == "__main__":
    main()


def plugin_loaded():
    # main()
    check_installed_packages()

