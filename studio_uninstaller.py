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
import time
import shutil
import zipfile
import tempfile

import io
import json
import shlex
import stat
import threading
import contextlib


from .settings import *
g_is_already_running = False

from .studio_installer import get_installed_packages
from .studio_installer import unique_list_join

from .studio_utilities import load_data_file
from .studio_utilities import write_data_file
from .studio_utilities import string_convert_list
from .studio_utilities import get_main_directory

from PackagesManager.packagesmanager import cmd
from PackagesManager.packagesmanager.download_manager import downloader

from PackagesManager.packagesmanager.package_manager import PackageManager
from PackagesManager.packagesmanager.thread_progress import ThreadProgress
from PackagesManager.packagesmanager.package_disabler import PackageDisabler
from PackagesManager.packagesmanager.commands.remove_package_command import RemovePackageThread


# Import the debugger
from debug_tools import Debugger

# Debugger settings: 0 - disabled, 127 - enabled
log = Debugger( 127, os.path.basename( __file__ ) )

log( 2, "..." )
log( 2, "..." )
log( 2, "Debugging" )
log( 2, "CURRENT_DIRECTORY_: " + CURRENT_DIRECTORY )


def main(channel_settings):
    """
        Before calling this installer, the `Package Control` user settings file, must have the
        Studio Channel file set before the default channel key `channels`.

        Also the current `Package Control` cache must be cleaned, ensuring it is downloading and
        using the Studio Channel repositories/channel list.
    """
    log( 2, "Entering on %s main(0)" % CURRENT_PACKAGE_NAME )

    installer_thread = StartUninstallStudioThread( channel_settings )
    installer_thread.start()


def unpack_settings(channel_settings):
    global STUDIO_INSTALLATION_SETTINGS
    global PACKAGES_TO_UNINSTALL_FIRST

    global STUDIO_MAIN_DIRECTORY

    STUDIO_INSTALLATION_SETTINGS = channel_settings['STUDIO_INSTALLATION_SETTINGS']
    PACKAGES_TO_UNINSTALL_FIRST  = reversed( channel_settings['PACKAGES_TO_INSTALL_LAST'] )

    STUDIO_MAIN_DIRECTORY = channel_settings['STUDIO_MAIN_DIRECTORY']


class StartUninstallStudioThread(threading.Thread):

    def __init__(self, channel_settings):
        threading.Thread.__init__(self)
        self.channel_settings = channel_settings

    def run(self):
        """
            Python thread exit code
            https://stackoverflow.com/questions/986616/python-thread-exit-code
        """

        if is_allowed_to_run():
            unpack_settings(self.channel_settings)

            uninstaller_thread = UninstallStudioFilesThread()
            uninstaller_thread.start()

            ThreadProgress( uninstaller_thread, 'Uninstalling Sublime Text Studio Packages',
                    'Sublime Text Studio %s was successfully installed.' )

            uninstaller_thread.join()
            check_uninstalled_packages()

        global g_is_already_running
        g_is_already_running = False


def is_allowed_to_run():
    global g_is_already_running

    if g_is_already_running:
        print( "You are already running a command. Wait until it finishes or restart Sublime Text" )
        return False

    g_is_already_running = True
    return True


class UninstallStudioFilesThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        log( 2, "Entering on %s run(1)" % self.__class__.__name__ )

        global g_channel_manager_settings
        global g_not_found_packages

        g_not_found_packages       = []
        g_channel_manager_settings = load_data_file( STUDIO_INSTALLATION_SETTINGS )

        uninstall_packages()
        # uninstall_files()
        # uninstall_folders()
        # restore_ignored_packages()


def uninstall_packages():
    package_manager       = PackageManager()
    package_disabler      = PackageDisabler()
    packages_to_uninstall = unique_list_join( PACKAGES_TO_UNINSTALL_FIRST, g_channel_manager_settings['packages_to_uninstall'] )

    current_index      = 0
    git_packages_count = len( packages_to_uninstall )

    packages     = set( package_manager.list_packages() + get_installed_packages() )
    dependencies = set( package_manager.list_dependencies() )

    uninstall_default_package( packages )

    for package in packages_to_uninstall:
        is_dependency = is_package_dependency( package, dependencies, packages )

        current_index += 1
        log( 1, "\n\nUninstalling %d of %d: %s (%s)" % ( current_index, git_packages_count, str( package ), str( is_dependency ) ) )

        if is_dependency is None:
            log( 1, "Package %s was not found on the system, skipping uninstallation." % package )
            g_not_found_packages.append( package )
            continue

        package_disabler.disable_packages( package, "remove" )
        thread = RemovePackageThread( package_manager, package )

        thread.start()
        thread.join()


def uninstall_default_package(packages):

    if 'Default' in packages:
        log( 1, "\n\nUninstalling Default Packages files..." )
        default_packages_path = os.path.join( STUDIO_MAIN_DIRECTORY, "Packages", "Default" )

        packages.remove('Default')
        files_installed = g_channel_manager_settings['default_packages_files']

        for file in files_installed:
            file_path = os.path.join( default_packages_path, file )

            if os.path.exists( file_path ):
                os.remove( file_path )


def is_package_dependency(package, dependencies, packages):
    """
        None when the package is not found.
    """
    if package in dependencies:
        return True

    if package in packages:
        return False

    return None


def check_uninstalled_packages():
    """
        Display warning when the uninstallation process is finished or ask the user to restart
        Sublime Text to finish the uninstallation.

        Compare the current uninstalled packages list with required packages to uninstall, and if
        they differ, attempt to uninstall they again for some times. If not successful, stop trying
        and warn the user.
    """
    studioSettings         = sublime.load_settings(STUDIO_INSTALLATION_SETTINGS)
    packageControlSettings = sublime.load_settings("Package Control.sublime-settings")

    # installed_packages =


if __name__ == "__main__":
    main()


def plugin_loaded():
    global STUDIO_INSTALLATION_SETTINGS
    STUDIO_INSTALLATION_SETTINGS = os.path.join( get_main_directory( CURRENT_DIRECTORY ),
            "Packages", "User", CURRENT_PACKAGE_NAME + ".sublime-settings" )

    # main()
    check_uninstalled_packages()

