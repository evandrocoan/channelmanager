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
# Studio Channel, assist the user on the Channel Studio upgrade
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
import textwrap

from .channel_utilities import wrap_text
from .channel_utilities import InstallationCancelled

from debug_tools import getLogger

# Debugger settings: 0 - disabled, 127 - enabled
log = getLogger( 127, __name__ )

g_installation_type = "Upgrade Wizard"


def main(packages_to_install, packages_to_uninstall, channel_installer):
    log( 2, "Entering..." )
    unpack_settigns( packages_to_install, packages_to_uninstall, channel_installer )

    run_the_installation_wizard()
    log( 2, "Exiting..." )


def run_the_installation_wizard():
    sublime_dialog = show_program_description()
    log( 2, "sublime_dialog: %s", sublime_dialog )

    if sublime_dialog == sublime.DIALOG_YES:
        g_channelInstaller.setupInstaller()
        g_channelInstaller._ask_user_for_which_packages_to_install( PACKAGES_TO_INSTALL )

        g_channelInstaller.setupUninstaller()
        g_channelInstaller._ask_user_for_which_packages_to_install( PACKAGES_TO_UNINSTALL )

        run_the_installation_wizard()

    elif sublime_dialog == sublime.DIALOG_NO:
        return

    elif sublime_dialog == sublime.DIALOG_CANCEL:
        # When pressing escape key, it returns to DIALOG_CANCEL
        if show_goodbye_message():
            run_the_installation_wizard()

        else:
            raise InstallationCancelled( "The user cancelled the %s." % g_installation_type )

    else:
        log(1, "Error: The option `%s` is a invalid return value from `sublime.yes_no_cancel_dialog`!", sublime_dialog )


def show_program_description():
    ok_button_text = "Edit upgrade"
    no_button_text = "Start upgrade"

    lines = [ "Welcome to the {channel} {wizard}.".format( channel=CHANNEL_PACKAGE_NAME, wizard=g_installation_type ), "", ]

    def format_packages_list(packages_list, maximum_length=500):
        length = 0
        contents = []

        for index, name in enumerate( packages_list ):
            contents.append( "%s. %s" % ( index + 1, name ) )
            length += len( contents[-1] )

            if length > maximum_length:
                remaining = len( packages_list ) - index - 1
                if remaining > 0: contents.append( "and more {} packages!".format( remaining ) )
                break

        return ", ".join( contents )

    if len( PACKAGES_TO_INSTALL ):
        lines.append( "The main {channel} upstream has added the following new packages: ".format( channel=CHANNEL_PACKAGE_NAME ) )
        lines.append( format_packages_list( PACKAGES_TO_INSTALL ) )
        lines.append( "" )

    if len( PACKAGES_TO_UNINSTALL ):
        lines.append( "The main {channel} upstream has removed the following installed packages: ".format( channel=CHANNEL_PACKAGE_NAME ) )
        lines.append( format_packages_list( PACKAGES_TO_UNINSTALL ) )
        lines.append( "" )

    if len( PACKAGES_TO_UNINSTALL ) < 1 and len( PACKAGES_TO_INSTALL ) < 1:
        lines.append( wrap_text( """\
                You removed all upgrade changes. If you would like the undo this, cancel the
                {wizard} and restart Sublime Text. Otherwise, hit the `{ok_button}` button to
                confirm the operation changes.
            """.format( wizard=g_installation_type, ok_button=no_button_text ) ) )

    else:
        global g_isFirstTime

        if g_isFirstTime:
            lines.append( wrap_text( """\
                    If you would like to remove packages from the upgrade list, choose the
                    `{ok_button}` button. Otherwise, choose the `{no_button}` button to start the
                    upgrade process.
                """.format( ok_button=ok_button_text, no_button=no_button_text) ) )

        else:
            lines.append( wrap_text( """\
                    If you would like revert your changes to the {wizard} package's list, just
                    cancel the {wizard} and restart Sublime Text. Then, on next time you start
                    Sublime Text, you will be able to start picking up packages again.
                """.format( wizard=g_installation_type ) ) )

        g_isFirstTime = False

    return sublime.yes_no_cancel_dialog( "\n".join( lines ), ok_button_text, no_button_text )


def show_goodbye_message():
    ok_button_text = "Go back"
    no_button_text = "Skip this upgrade"

    lines = \
    [
        wrap_text( """\
        Do you want to cancel the {channel_name} {wizard}?

        If you would like to upgrade the {channel_name}, hit the `{ok_button}` button to go back and
        try again. Otherwise, hit the `Cancel` button to follow the {wizard} next time Sublime Text
        starts.

        If you would like to ignore this upgrade, hit the `{no_button}` button.
        """.format( ok_button=ok_button_text, no_button=no_button_text,
                wizard=g_installation_type, channel_name=CHANNEL_PACKAGE_NAME ) ),
    ]

    sublime_dialog = sublime.yes_no_cancel_dialog( "\n".join( lines ), ok_button_text, no_button_text )

    if sublime_dialog == sublime.DIALOG_YES:
        return True

    elif sublime_dialog == sublime.DIALOG_NO:
        g_channelSettings['CHANNEL_UPGRADE_SKIP'] = True

    elif sublime_dialog == sublime.DIALOG_CANCEL:
        # When pressing escape key, it returns to DIALOG_CANCEL
        pass

    else:
        log(1, "Error: The option `%s` is a invalid return value from `sublime.yes_no_cancel_dialog`!", sublime_dialog )

    return False


def unpack_settigns(packages_to_install, packages_to_uninstall, channel_installer):
    global g_isFirstTime
    global g_channelSettings
    global g_channelInstaller
    global CHANNEL_PACKAGE_NAME

    global PACKAGES_TO_INSTALL
    global PACKAGES_TO_UNINSTALL

    g_isFirstTime = True

    g_channelInstaller   = channel_installer
    g_channelSettings    = g_channelInstaller.channelSettings
    CHANNEL_PACKAGE_NAME = g_channelSettings['CHANNEL_PACKAGE_NAME']

    PACKAGES_TO_INSTALL   = packages_to_install
    PACKAGES_TO_UNINSTALL = packages_to_uninstall

