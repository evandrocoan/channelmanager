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
# Studio Channel, assist the user on the Channel Studio installation
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
import time

import textwrap
import threading

g_is_already_running = False
from . import settings as g_settings

from channel_manager import channel_installer
from channel_manager.channel_utilities import wrap_text
from channel_manager.channel_utilities import load_data_file
from channel_manager.channel_utilities import write_data_file
from channel_manager.channel_utilities import get_dictionary_key
from channel_manager.channel_utilities import upcase_first_letter

# When there is an ImportError, means that Package Control is installed instead of PackagesManager,
# or vice-versa. Which means we cannot do nothing as this is only compatible with PackagesManager.
try:
    from package_control import cmd
    from package_control.thread_progress import ThreadProgress
    from package_control.package_manager import clear_cache

except ImportError:
    from PackagesManager.package_control import cmd
    from PackagesManager.package_control.thread_progress import ThreadProgress
    from PackagesManager.package_control.package_manager import clear_cache


from debug_tools import getLogger

# Debugger settings: 0 - disabled, 127 - enabled
log = getLogger( 127, os.path.basename( __file__ ) )

# log( 2, "..." )
# log( 2, "..." )
# log( 2, "Debugging" )
# log( 2, "PACKAGE_ROOT_DIRECTORY: " + g_settings.PACKAGE_ROOT_DIRECTORY )


g_version_to_install     = ""
g_installation_command   = "Run Installation Wizard"
g_uninstallation_command = "Run Uninstallation Wizard"

g_link_wrapper  = textwrap.TextWrapper( initial_indent="    ", width=80, subsequent_indent="    " )
g_is_to_go_back = False


def main(channel_settings):
    log( 2, "Entering on %s main(0)" % g_settings.CURRENT_PACKAGE_NAME )

    wizard_thread = StartInstallationWizardThread( channel_settings )
    wizard_thread.start()


class StartInstallationWizardThread(threading.Thread):

    def __init__(self, channel_settings):
        threading.Thread.__init__(self)
        self.channel_settings = channel_settings

    def run(self):
        """
            Python thread exit code
            https://stackoverflow.com/questions/986616/python-thread-exit-code
        """

        if is_allowed_to_run():
            unpack_settigns( self.channel_settings )
            wizard_thread = InstallationWizardThread()

            wizard_thread.start()
            ThreadProgress( wizard_thread, 'Running the %s Installation Wizard...' % CHANNEL_PACKAGE_NAME,
                    'The %s Installation Wizard finished.' % CHANNEL_PACKAGE_NAME )

            wizard_thread.join()
            # check_uninstalled_packages()

        global g_is_already_running
        g_is_already_running = False


class InstallationWizardThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        log( 2, "Entering on %s run(1)" % self.__class__.__name__ )
        run_the_installation_wizard()


def run_the_installation_wizard(step=1):
    step = update_step( step, 1 )

    if step in [ 2, 3, 4 ] or show_program_description():
        step = update_step( step, 2 )

        if step in [ 3, 4 ] or show_license_agreement()[0]:
            step = update_step( step, 3 )

            if step in [ 4 ] or select_stable_or_developent_version()[0]:
                step = update_step( step, 4 )

                if show_installation_confirmation()[0]:
                    start_the_installation_process()

                else:

                    if is_to_go_back( step ):
                        return

                    if show_goodbye_message():
                        run_the_installation_wizard( 4 )

            else:

                if is_to_go_back( step ):
                    return

                if show_goodbye_message():
                    run_the_installation_wizard( 3 )

        else:

            if is_to_go_back( step ):
                return

            if show_goodbye_message():
                run_the_installation_wizard( 2 )

    else:

        # We cannot go back from the first step
        if show_goodbye_message():
            run_the_installation_wizard( 1 )


def update_step(step, level):

    if step < level:
        return level

    return step


def is_to_go_back(step):
    global g_is_to_go_back

    if g_is_to_go_back:
        g_is_to_go_back = False

        log( 2, "is_to_go_back, step: " + str( step ) )
        run_the_installation_wizard( step - 1 )
        return True

    return False


def calculate_next_step( sublime_dialog ):
    global g_is_to_go_back

    if sublime_dialog == sublime.DIALOG_NO:
        g_is_to_go_back = True
        return False, True

    if sublime_dialog == sublime.DIALOG_YES:
        g_is_to_go_back = False
        return True, False

    return False, False


def show_goodbye_message():
    ok_button_text = "Return to the wizard"
    ask_later_text = "Ask me later"

    lines = \
    [
        wrap_text( """\
        Thank you for looking to install the {channel_name}, but as you do not agree with its usage
        license and completed the installation wizard, the {channel_name} need to be uninstalled as
        it does nothing else useful for you.

        If you want to consider installing it, click on the button `{ok_button}` to go back and try
        again. Otherwise click on the `Cancel` button and then uninstall the {channel_name} package.

        If you wish to install the {installation_type} later, you can go to the menu `Preferences ->
        Packages -> {channel_name}` and select the option `{installation_type}`, to run this
        Installer Wizard again. Or select the button `{ask_later}` to show this Wizard on the next
        time you start Sublime Text.

        If you wish to install the {channel_name} later, after uninstalling it, you can just install
        this package again.
        """.format( ok_button=ok_button_text, ask_later=ask_later_text, installation_type=g_installation_command,
                channel_name=CHANNEL_PACKAGE_NAME ) ),
    ]

    channelDetailsPath = g_channelSettings['CHANNEL_INSTALLATION_DETAILS']

    channelDetails = load_data_file( channelDetailsPath )
    sublime_dialog = sublime.yes_no_cancel_dialog( "\n".join( lines ), ok_button_text, ask_later_text )

    if sublime_dialog == sublime.DIALOG_YES:
        return True

    elif sublime_dialog == sublime.DIALOG_NO:
        channelDetails['automatically_show_installation_wizard'] = True

    else:
        channelDetails['automatically_show_installation_wizard'] = False

    write_data_file( channelDetailsPath, channelDetails )
    return False


def show_program_description():
    g_link_wrapper.width = 71

    lines = \
    [
        wrap_text( """\
        Thank you for choosing %s.

        This is a channel of packages for Sublime Text's Package Control, which replace and install
        some of the packages by a forked/alternative version. i.e., custom modification of them. You
        can find this list of packages to be installed on channel on the following addresses:
        """ % CHANNEL_PACKAGE_NAME ),
        "",
        g_link_wrapper.fill( "<%s>" % g_channelSettings['CHANNEL_ROOT_URL'] ),
        g_link_wrapper.fill( "<%s>" % g_channelSettings['CHANNEL_FILE_URL'] ),
        "",
        wrap_text( """\
        Therefore, this installer will install all Sublime Text Packages listed on the above address,
        however if already there are some of these packages installed, your current version will be
        upgraded to the version used on the fork of the same package.

        This installer will also remove you current installation of Package Control and install
        another forked version of it, which has the name PackagesManager. Now on, when you want to,
        install/manage packages, you should look for `PackagesManager` instead of `Package Control`.
        """ ),
    ]

    return sublime.ok_cancel_dialog( "\n".join( lines ), "Next" )


def show_license_agreement():
    is_to_go_back = False
    active_window = sublime.active_window()
    can_continue  = [False]

    active_window_panel  = active_window.active_panel()
    g_link_wrapper.width = 71

    initial_input   = "Type Here"
    user_input_text = [initial_input]
    agrement_text   = "i did read and agree"

    input_panel_question_answer       = [None]
    input_panel_question_confirmation = [None]

    lines = \
    [
        wrap_text( """\
        Welcome to the %s Installation Wizard. The installed packages by this wizard, in addition to
        each one own license, are distributed under the following conditions for its usage and
        installation:

        ALL THE SOFTWARES, PACKAGES, PLUGINS, SETTINGS, DOCUMENTATION, EVERYTHING ELSE, ARE PROVIDED
        \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
        THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
        NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
        CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

        On the following addresses you can find the list and links for all distributed contents by
        this installer, which these conditions above applies to, and their respective software
        license:
        """ % CHANNEL_PACKAGE_NAME ),
        "",
        g_link_wrapper.fill( "<%s#License>" % g_channelSettings['CHANNEL_ROOT_URL'] ),
        g_link_wrapper.fill( "<%s>" % g_channelSettings['CHANNEL_FILE_URL'] ),
        "",
        wrap_text( """\
        Did you read and agree with these conditions for using these softwares, packages, plugins,
        documentations, everything else provided? If you not agree with it, click on the `Cancel`
        button, instead of the `Next` button.

        If you do agree with these conditions, type the following phrase on the input panel which is
        open at the bottom of your Sublime Text window and then click on the `Next` button to
        proceed to the next step:
        """ ),
        "",
        g_link_wrapper.fill( agrement_text ),
    ]

    def restore_last_actived_panel():

        if active_window_panel:
            sublime.active_window().run_command( "show_panel", {"panel": active_window_panel, "toggle": False} )

    def not_confirmed_correctly(is_to_show_typed_input=True):
        active_window.run_command( "hide_panel" )
        restore_last_actived_panel()

        typed_text = "" if not is_to_show_typed_input else """\
                You typed: {input_text}

                You did not typed you agree with the {channel_name} license as required when you
                agree with the license, on the input panel at your Sublime Text window.
                """.format( input_text=user_input_text[0], channel_name=CHANNEL_PACKAGE_NAME )

        sublime.message_dialog( wrap_text( """\
                {typed_text}
                Please, click in `Cancel` instead of `Next` on the next message dialog, if you do
                not agree with the
                {channel_name} license.
                """.format( channel_name=CHANNEL_PACKAGE_NAME, typed_text=typed_text ) ) )

    def did_the_user_agreed(answer):
        user_input_text[0] = answer
        return answer.replace(".", "").replace(",", "").strip(" ").replace("  ", " ").lower() == agrement_text

    def on_done(answer, is_final_confirmation=True):

        if did_the_user_agreed( answer ):
            input_panel_question_answer[0] = True

            if is_final_confirmation:
                restore_last_actived_panel()

                is_re_confirmed = sublime.ok_cancel_dialog( wrap_text( """\
                        Thank you for agreeing with the license, as you typed: `%s`

                        If you did not mean to agree with the license, click on the `Cancel` button,
                        otherwise click on the `OK` button.
                        """ % answer ) )

                if is_re_confirmed:
                    input_panel_question_confirmation[0] = True

                else:
                    input_panel_question_answer[0] = False
                    input_panel_question_confirmation[0] = False

                    not_confirmed_correctly( False )
                    user_input_text[0] = initial_input

                can_continue[0] = True

        else:
            input_panel_question_answer[0] = False

            if is_final_confirmation:
                not_confirmed_correctly()
                can_continue[0] = True

    def on_change(answer):
        on_done(answer, False)

    def on_cancel():
        can_continue[0] = True

    def show_acknowledgment_panel():
        can_continue[0] = False

        widget_view = active_window.show_input_panel(
                "Did you read and agree with these conditions for using these softwares?",
                user_input_text[0], on_done, on_change, on_cancel )

        if user_input_text[0] == initial_input:
            widget_view.run_command( "select_all" )

        # show_input_panel is a non-blocking function, but we can only continue after on_done being called
        while not can_continue[0]:
            time.sleep( 0.5 )

    while True:
        is_yes_answer, is_to_go_back = calculate_next_step( sublime.yes_no_cancel_dialog( "\n".join( lines ), "Next", "Go Back" ) )

        if is_to_go_back \
                or input_panel_question_answer[0] and input_panel_question_confirmation[0] is False:
            break

        if is_yes_answer:
            show_acknowledgment_panel()

        else:
            break

        if input_panel_question_answer[0] and input_panel_question_confirmation[0]:
            break

    restore_last_actived_panel()
    return input_panel_question_answer[0] and is_yes_answer, is_to_go_back


def select_stable_or_developent_version():
    global g_version_to_install

    lines = \
    [
        wrap_text( """\
        {descriptions}
        It is recommended to use both Stable and Development Versions of the {channel_name}. For
        example, while you are at home, use the Development Version as you should have free time to
        work on it, fixing bugs and installing new packages. Elsewhere your are, use the Stable
        Version, because when you are elsewhere you have no time for fixing bugs or testing new
        things. Also because elsewhere you are, not always there will be enough free space required
        by the Development Version.
        """.format( descriptions=g_channelSettings['CHANNEL_VERSIONS_DESCRIPTIONS'],
                channel_name=CHANNEL_PACKAGE_NAME ) ),
    ]

    user_response = sublime.yes_no_cancel_dialog(
            "\n".join( lines ), "Install the Stable Version", "Install the Development Version" )

    if user_response == sublime.DIALOG_YES:
        g_version_to_install = "stable"

    elif user_response == sublime.DIALOG_NO:
        g_version_to_install = "development"

        command_line_interface = cmd.Cli( None, True )
        git_executable_path    = command_line_interface.find_binary( "git.exe" if os.name == 'nt' else "git" )

        if not git_executable_path:
            g_version_to_install = "stable"

            log( 1, "Using the Stable Version instead of the Development Version as a valid `git`"
                    "application could not be found" )

            sublime.message_dialog( wrap_text( """\
                    Sorry, but the `git` application could not be found on your system. Hence the
                    Stable Version will be used instead. If you are sure there is a `git`
                    application installed on your system check your console for error messages.

                    You can also open an issue on the {channel_name} issue tracker at the address:
                    <{root_url}>, Just do not forget to save your Sublime Text Console output, as it
                    recorded everything which happened, and should be very helpful in finding the
                    solution for the problem.
                    """.format( channel_name=CHANNEL_PACKAGE_NAME,
                            root_url=g_channelSettings['CHANNEL_ROOT_URL'] ) ) )

    return user_response != sublime.DIALOG_CANCEL, False


def show_installation_confirmation():
    version_to_install = upcase_first_letter( g_version_to_install )

    lines = \
    [
        wrap_text( """\
        You choose to install the {version_to_install} Version. It is recommended to backup your Sublime Text's
        current settings and packages before installing this, either for the Stable or Development
        version.

        Now you got the chance to go and backup everything. No hurries. When you finished your
        backup, you can come back here and click on the `Install Now` button to start now the
        installation process for the {version_to_install} Version. Click on the `Go Back` button if you wish to
        choose another version, or in `Cancel` button if you want give up from installing the
        {channel_name}.

        While the {channel_name} is being installed, either the Stable Version or the Development
        Version, you can follow the installation progress seeing your Sublime Text Console. The
        console will be automatically opened for you when you start the installation process, but
        you can also open it by going on the menu `View -> Show Console (Ctrl+')`.

        When you are monitoring the installation process, you will see several error messages. This
        is expected because while doing the batch installation process, the packages are not able to
        initialize/start properly, hence some of them will throw several errors. Now, once the
        installation process is finished, you will be asked to restart Sublime Text.

        Then, after the restarting Sublime Text, all the installed packages will be finished
        installing by the `PackagesManager` (Package Control fork replacement), which will also ask
        you to restart Sublime Text, when it finish install all missing dependencies.

        If you wish to cancel the installation process while it is going on, you need to restart
        Sublime Text. However not all packages will installed and some can be corrupted or half
        installed. Later on, to finish the installation you will need to run the uninstaller by
        going on the menu `Preferences -> Packages Settings -> {channel_name}` and select the option
        `{uninstallation_command}`. Then later install again the {channel_name}.
        """.format( version_to_install=version_to_install, channel_name=CHANNEL_PACKAGE_NAME,
                uninstallation_command=g_uninstallation_command ) ),
        ]

    return calculate_next_step( sublime.yes_no_cancel_dialog( "\n".join( lines ),  "Install Now", "Go Back" ) )


def start_the_installation_process():
    g_link_wrapper.width = 70

    lines = \
    [
        wrap_text( """\
        The installation process has started. You should be able to see the Sublime Text Console
        opened on your Sublime Text window. If not, you can open it by going on to the menu `View ->
        Show Console (Ctrl+')`.

        If you wish to uninstall the {channel_name}, you can do this by either `PackagesManager
        (Package Control Replacement)` or by going to the menu the menu `Preferences -> Packages
        Settings -> {channel_name}` and select the option `{uninstallation_command}`.

        Even if you just half installed {channel_name}, you can uninstall it with all its files. To
        ensure a correct uninstallation, we create a configuration file on your User folder called
        `{channel_name}.sublime-settings`. This file registers all installed folders, packages and
        files to your Sublime Text. Then it can correctly later remove everything which belongs to
        it. Just do not edit this file add or removing things, as it can make the uninstallation
        delete files which it should not to.

        The installation process should take about 2~5 minutes for the Stable Version and 10~20
        minutes for the Development Version, depending on your Computer Performance. Any problems
        you have with the process you can open issue on the {channel_name} issue tracker at the
        address:
        """.format( channel_name=CHANNEL_PACKAGE_NAME, uninstallation_command=g_uninstallation_command ) ),
        "",
        g_link_wrapper.fill( "<%s/issues>" % g_channelSettings['CHANNEL_ROOT_URL'] ),
        "",
        wrap_text( """\
        Just do not forget to save your Sublime Text Console output, as it recorded everything which
        happened, and should be very helpful in finding the solution for the problem.
        """ ),
    ]

    install_channel()
    sublime.message_dialog( "\n".join( lines ) )


def install_channel():
    add_channel()
    clear_cache()

    g_channelSettings['INSTALLER_TYPE']    = "installation"
    g_channelSettings['INSTALLATION_TYPE'] = g_version_to_install

    channel_installer.main( g_channelSettings, True )


def unpack_settigns(channel_settings):
    global g_channelSettings
    global CHANNEL_PACKAGE_NAME

    g_channelSettings    = channel_settings
    CHANNEL_PACKAGE_NAME = g_channelSettings['CHANNEL_PACKAGE_NAME']


def is_allowed_to_run():
    global g_is_already_running

    if g_is_already_running:
        print( "You are already running a command. Wait until it finishes or restart Sublime Text" )
        return False

    g_is_already_running = True
    return True


def add_channel():
    channel_url = g_channelSettings['CHANNEL_FILE_URL']
    package_control = "Package Control.sublime-settings"

    package_control_settings = sublime.load_settings( package_control )
    channels                 = package_control_settings.get( "channels", [] )

    while channel_url in channels:
        channels.remove( channel_url )

    channels.insert( 0, channel_url )
    package_control_settings.set( "channels", channels )

    log( 1, "Adding %s channel to %s: %s" % ( CHANNEL_PACKAGE_NAME, package_control, str( channels ) ) )
    sublime.save_settings( package_control )


