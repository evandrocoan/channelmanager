# Sublime Text Channel Manager

The plugin `channel_manager.py` creates the files `channel.json` and `repository.json` based on the
`.gitmodules` file on the Sublime Text Data folder (the folder at `Packages/../`).

To call it, you can open the command palette and type `Studio Channel: Generate Channel File`. See
the following threads for more information about the `Package Control` channel and repository files:

1. https://packagecontrol.io/docs/dependencies  DOCS - Dependencies
1. https://packagecontrol.io/docs/channels_and_repositories Channels and Repositories
1. https://github.com/wbond/package_control/issues/1089 Package dependencies (install dependent sublime packages)
1. https://forum.sublimetext.com/t/dependencies-in-package-control-3/14646 Dependencies in Package Control 3
1. https://github.com/wbond/package_control/issues/1070 [Meta] What to do when a dependency update includes breaking changes?
1. https://forum.sublimetext.com/t/modules-dependencies-best-practices/21037 Modules + Dependencies : Best Practices?

ChannelManager is dependency which manages the packages installed by git as submodules. It allows to
create the channel files required by Package Control to list and install packages. Currently I
implemented to different bundle of package bounded by `.gitmodules` files. The
[StudioChannel](https://github.com/evandrocoan/SublimeStudioChannel) and the
[AmxxSimpleIDE](https://github.com/evandrocoan/SublimeTextAmxxSimpleIDE).

The channel creation is based on the existence of a
[.gitmodules](https://git-scm.com/docs/gitmodules) file on the root of your Sublime Text Data
folder. For example, at the portable version of Sublime Text the folder structure would look like
this:
```java
$ tree
.
├── .git
│   ├── COMMIT_EDITMSG
|   ...
├── .gitmodules
├── Cache
│   ├── ActionScript
│   │   └── ActionScript.sublime-syntax.cache
|   ...
├── Installed Packages
│   ├── 0_package_control_loader.sublime-package
│   ├── Amxx Pawn.sublime-package
│   ...
├── KEEPME
|   ...
└── Packages
    ├── amxmodx
    │   ├── amxx.sublime-settings
    ...
```

The contents of the file `.gitmodules` follow the requirements by
[.gitmodules](https://git-scm.com/docs/gitmodules), but also including new keys used to generate the
channel files. Currently there are implemented the following keys:
```java
[submodule "Packages/Notepad++ Color Scheme"]
    path = Packages/Notepad++ Color Scheme
    url = https://github.com/evandrocoan/SublimeNotepadPlusPlusTheme
    upstream =
    dependency = PythonDebugTools, regex
    tags = 3144, 3147
```
The keys `dependency` and `tags` are comma separate lists of `dependencies` a package has. If the
dependency key start with number like in `dependency = 50, PythonDebugTools, regex`, it would mean
that the package `Packages/Notepad++ Color Scheme` would be a dependency, which requires as
dependency the dependencies `PythonDebugTools` and `regex`.

As well it would just be `dependency = 50`, then it would mean it is a dependency which has the
loading order set as `50`. You can learn more about dependencies reading [Package Control, Docs:
Dependencies](https://packagecontrol.io/docs/dependencies).

The `upstream` can be empty or not present if you would like to. It used to set your repository
`upstream` when the project is a fork of some another project. For example, let us suppose you like
the project `https://github.com/evandrocoan/SublimeNotepadPlusPlusTheme` and created a fork of it on
Github. Now, instead of installing the original package from `evandrocoan`, you installed your fork,
from your address `https://github.com/my_user_name/SublimeNotepadPlusPlusTheme`.

Hence, if you would like to receive updates from the upstream
`https://github.com/evandrocoan/SublimeNotepadPlusPlusTheme`, you can set the key `upstream`
pointing to the `upstream` of the original package at
`https://github.com/evandrocoan/SublimeNotepadPlusPlusTheme`. Therefore, your settings file would
look like:
```java
[submodule "Packages/Notepad++ Color Scheme"]
    path = Packages/Notepad++ Color Scheme
    url = https://github.com/my_user_name/SublimeNotepadPlusPlusTheme
    upstream = https://github.com/evandrocoan/SublimeNotepadPlusPlusTheme
    dependency = PythonDebugTools, regex
    tags = 3144, 3147
```

Sadly currently this feature is not implemented yet. However, the `upstream` key is used by the
plugin `submodules_manager.py`, which runs by the command line with the argument `-f`. The
`submodules_manager.py` provides some commands which are not available from Sublime Text due they
being too longo commands to run. Moreover is proper to use a dedicated shell for them. You can see
the available options for the `submodules_manager.py` by running it:
```java
$ python3 submodules_manager.py
[submodules_manager.py] 10:05:26  548163    3795 Entering on main(0) None
[submodules_manager.py] 10:05:26  548507     344 ( print_command_line_arguments ) len(sys.argv): 1
[submodules_manager.py] 10:05:26  548638     131 ( print_command_line_arguments ) arg: submodules_manager.py
usage: submodules_manager.py [-h] [-a] [-b] [-f] [-p]

Update Sublime Text Studio

optional arguments:
  -h, --help        show this help message and exit
  -a, --all         Generate all assets
  -b, --backstroke  Check all backstroke registered repositories updates with
                    their upstream. The backstroke URLs are now in a separate
                    file on: Local/Backstroke.gitmodules
  -f, --find-forks  Find all repositories forks, fetch their branches and
                    clean the duplicated branches. The upstream data in on the
                    `.gitmodules` file on: Sublime Text `Data` folder
  -p, --pull        Perform a git pull from the remote repositories
```

Lastly, the `tags` key indicate the remote tags and the version of Sublime they are aimed to be
used. For example, `tags = 3144, 3147` indicates the repository `Notepad++ Color Scheme` has the
following git tags called `3144` and `3147`.

Settings tags like this is useful when a package has ceased working for old build of Sublime Text.
For example, on Sublime Text development build 3147, the package `Notepad++ Color Scheme` stopped
working completely: [CoreIssue$1983](https://github.com/SublimeTextIssues/Core/issues/1983) however
the fix for build 3147 also broke completely the package for Sublime Text stable build 3144. Hence,
we must to create a tag which targets the last commit which is working for build 3144. Hence when
some user using the stable build 3144 installs the `Notepad++ Color Scheme`, they must install the
one from the tag `3144`, and not the one from the master branch, which has the latest fixes for
build development build 3147.

This happens because currently the channel generation is limited to setting the download link to the
repository master branch. Still not implemented the checking for each submodule for the latest tag
available, then then properly setting the download URL pointing to the last tag. Still also to do
automatic tagging of the latest release package is working for Sublime Text, however this seems not
much required to be done as should be only a few exceptions for when a packages stops working for
some build of Sublime Text.


## How to Build a Channel

The original purpose of the channel is to be small, something like just a few hundred of packages.
However, you can scale up, if you do not actually install everything as a git submodule. The channel
can in also be installed at once, including all its packages. That means, if you have big channel
like with 1000 packages, you can call the channel installer, and those 1000 packages are going to be
installed in your Sublime Text.

The installer provides two installation alternatives. The Development Version and the Stable
Version. By installing the Stable Version, all the packages in your channel are going to be
installed, except the one listed in the `settings.json` file. Then, for example, you can have as
much as 1000 packages in your channel, but list 960 of them by their names at the `settings.json`.
Hence only 40 packages are going to be installed when the channel installer run.

However, this is only true if the user is installing the Stable Version of the channel. The
Development Version will clone by `git` all the 1000 packages and then add the 960 packages listed
on the `settings.json` file to the user `ignored_packages` settings. Currently the `settings.json`
file is generated based on your `ignored_packages` settings, i.e., it copies all the packages you
have set on your `ignored_packages` settings and add them to the `settings.json`.

This was designed like that because the original goal of this is to be just a small channel for a
few packages you always install, or are developing. However, if you wish to scale up build very
large, channels you can change easily change this behavior by including the `ignored_packages`
manually or from another source other than the user settings `ignored_packages`, or just deciding
not to use the channel installer to install the channel packages and just pick they one by one, as
you usually do with the default `Package Control` channel.


1. Install Sublime Text portable version, you can download it at:
   [https://www.sublimetext.com/3](https://www.sublimetext.com/3)

1. Open your Sublime Text loose `Packages` folder by going the menu `Preferences -> Browse
   Packages...` Now open a command line you the folder which just opened:

   <details>
   <p>

   ![Opening Linux Command Line](http://i.imgur.com/VA4zC7F.gif)
   </p>
   </details><br>

   <details>
   <p>

   ![Opening Windows Command Line](http://i.imgur.com/iYwE4IO.gif)
   </p>
   </details><br>

1. Use your command line and go to the parent folder of your `Packages` folder, and create a git
   repository, which will hold/tie together all the packages available in you channel. For example:
   ```bash
   cd ..
   git init
   printf "# Main Repository\n\nFor my channel packages." > README.md
   git add README.md
   git commit -m "Added README.md"
   git remote add origin https://github.com/user/main_repository
   ```

1. Now your `Main Repository` is set up, use the same command line to install the Packages you want
   to add to your channel and adding them as git submodules to the main repository. For example:
   ```bash
   git clone --recursive https://github.com/jisaacks/GitGutter "Packages/GitGutter"
   git submodule add -- https://github.com/jisaacks/GitGutter "Packages/GitGutter"
   git commit -m "Added the first package to my channel."
   ```

1. Now your `.gitmodules` file was created by git. It should look like this:
   ```java
   [submodule "Packages/GitGutter"]
       path = Packages/GitGutter
       url = https://github.com/jisaacks/GitGutter
   ```

   With this you can customize your file adding the required information to build up the channel.
   Let us start by adding the keys for the `ChannelManager` installer & uninstaller:
   ```java
   [submodule "Packages/GitGutter"]
       path = Packages/GitGutter
       url = https://github.com/jisaacks/GitGutter

   [submodule "Packages/ChannelManager"]
       path = Packages/ChannelManager
       url = https://github.com/evandrocoan/SublimeChannelManager
       upstream =
       dependency = 50, PythonDebugTools
   ```

   The packages `ChannelManager` is responsible for generating the channel files, installing and
   uninstalling them. As it is set on the `.gitmodules` file, it defines itself as being a
   dependency with load order of `50` and requiring another dependency called `PythonDebugTools`.
   You can read more about the dependency load order on [Package Control, Docs:
   Dependencies](https://packagecontrol.io/docs/dependencies)

   As it is a dependency you could just skip it, i.e., not add this entry to your `.gitmodules` file
   as `Package Control` would install it when you requires it on the actual package which provides
   the commands. However, if you do not add it you cannot use all the features available because
   currently it is dependent on submodules and Package Control cannot clone the submodules together
   yet. Therefore, cannot use the features dependent on the submodules as the `find_forks` command.

   But also, you can add `ChannelManager` to enforce the policy of development, adding
   `ChannelManager` here allow you to easily edit its code, fix bugs or improve whatever is it doing
   as you already have a full git repository at hand, you just need to change the remote to a new
   repository or for a fork of yours at GitHub.

   Therefore as you may notice, I skipped the addition of the dependency `PythonDebugTools` as it is
   not dependent on git submodules and there is not much room for improvement or changes on it.
   However if you like you can also add it as a package. You just need to add the following entry to
   your `.gitmodules`:
   ```java
   [submodule "Packages/GitGutter"]
       path = Packages/GitGutter
       url = https://github.com/jisaacks/GitGutter

   [submodule "Packages/ChannelManager"]
       path = Packages/ChannelManager
       url = https://github.com/evandrocoan/SublimeChannelManager
       upstream =
       dependency = 50, PythonDebugTools

   [submodule "Packages/PythonDebugTools"]
       path = Packages/PythonDebugTools
       url = https://github.com/evandrocoan/PythonDebugTools
       upstream =
       dependency = 50
   ```

1. Now you added the basics, you may notice we were not adding them as `git submodules` by the
   commands `git clone --recursive repo_url` and `git submodule add -- repo_url
   "Packages/package_name"`. Moreover you can or cannot do so if you like. The `ChannelManager` only
   requires to the file `.gitmodules` to exists in the pre-configured location, which we are about
   do to. Other than that, you do not need to have a parent repository which holds a valid
   `.gitmodules` file by your `git` client.

   However it is advised and nice to have a parent repository which validly by `git` ties together
   all the packages, because you can in only open place manage all your packages and easily create
   commits, pulls, pushes, etc. On this picture we can see some of this integration by a `git client
   Graphic Interface`:

   ![git client Graphic Interface](https://i.imgur.com/Q3DngpF.png)

   To create the channel you need the configuration loader for the dependency `ChannelManager`. This
   would be a Sublime Text Package which requires the `ChannelManager` as a dependency and call its
   installer, uninstaller and command available passing the configuration required by the
   `ChannelManager` dependency to run its operations.

   This is a



## Commands

It provides the following commands on command palette. Note these commands only works if you
installed the Development Version of the channel:

1. **StudioChannel: Generate Channel File** Creates the files `channel.json`, `repositories.json`
   and `settings.json`. The file `channel.json` and `repositories.json` are the same file as the
   Package Control's [channel_v3.json](https://packagecontrol.io/channel_v3.json) file.

   The file `settings.json` is used to save additional settings for the channel. Currently it only
   list the default ignored packages which are set when you use the Development Version, instead of
   the Stable Version of the channel. You can read more about them at [Package Control, Docs:
   Channels and Repositories](https://packagecontrol.io/docs/channels_and_repositories)

1. **StudioChannel: Run Backstroke Requests** Backstroke is a Github bot to keep repository forks up
   to date with their upstream. Therefore, if you setup your own list of Backstroke URLs, you can
   run this command to ping all your URLs, so their upstreams are checked whether there are some
   missing updates.

1. **StudioChannel: Pull & Rebase all Packages** Walk through all git repositories and perform the
   `git pull --rebase` command, i.e., fetch the updates from the origin and merge the changes by
   rebase.

1. **StudioChannel: Pull & Rebase all Upstreams** (Not Yet Implemented) Walk through all git
   repositories and perform `git remote add upstream_url`, checkout on the specified remove branch,
   and do a git merge with the upstream contents.

   This is not yet implemented, it should require a new settings entry key on the `.gitmodules` to
   set which one should be the remove branch used to checkout to do the merge. Otherwise, if the
   setting is not set/present, the default branch would be used.

1. **StudioChannel: Update Default Packages** Run the script `copy_default_package.py` which
   unpack_settings the `Default.sublime-package` at the on the `Packages/../` folder, i.e., on the
   folder which the Sublime Text loose packages are, not inside it. This command automatically runs
   when you install a new version of Sublime Text, therefore the command is only here when you want
   to force it to override the current files.


## Installation Notes

1. Currently it has the problem of showing up this error box randomly. This may or may not happen
   when you run the installer:

    ![Error Box](https://i.imgur.com/WppRKNt.png)

    This happens at this moments:
    ```
    ignored packages updated to: ["Vintage", "Uncrustify", ..., AdvancedNewFile", "AlignTab"]
    reloading settings Packages/User/Preferences.sublime-settings
    ignored packages updated to: ["Vintage"]
    ignored packages updated to: ["Vintage", "Uncrustify", ..., AdvancedNewFile", "AlignTab"]
    reloading settings Packages/User/Preferences.sublime-settings
    ignored packages updated to: ["Vintage"]
    ignored packages updated to: ["Vintage", "Uncrustify", ..., AdvancedNewFile", "AlignTab"]
    reloading settings Packages/User/Preferences.sublime-settings
    ignored packages updated to: ["Vintage"]
    ignored packages updated to: ["Vintage", "Uncrustify", ..., AdvancedNewFile", "AlignTab"]
    reloading settings Packages/User/Preferences.sublime-settings
    ignored packages updated to: ["Vintage"]
    ignored packages updated to: ["Vintage", "Uncrustify", ..., AdvancedNewFile", "AlignTab"]
    reloading settings Packages/User/Preferences.sublime-settings
    ignored packages updated to: ["Vintage"]
    ignored packages updated to: ["Vintage", "Uncrustify", ..., AdvancedNewFile", "AlignTab"]
    reloading settings Packages/User/Preferences.sublime-settings
    reloading settings Packages/User/Preferences.sublime-settings

        It appears a package is trying to ignore itself, causing a loop.
        Please resolve by removing the offending ignored_packages setting.
    ```

    I am not sure what is setting the `ignored_packages` setting to `["Vintage"]`, that is why I wrote
    this function:
    ```python
    def add_packages_to_ignored_list(packages_list):
        """
            Something, somewhere is setting the ignored_packages list to `["Vintage"]`. Then ensure we
            override this ************.
        """
        ignored_packages = g_user_settings.get( "ignored_packages", [] )
        unique_list_append( ignored_packages, packages_list )

        for interval in range( 0, 27 ):
            g_user_settings.set( "ignored_packages", ignored_packages )
            sublime.save_settings( USER_SETTINGS_FILE )

            time.sleep(0.1)
    ```
    Perhaps `Package Control` is doing it, as this error showed up in a vanilla install only with
    `Package Control` installed. The problem seems random and does not to happens every time you run
    the channel installer.

1. This error also may or may not show up when you run the installer:

    ![Error while loading PyV8 binary](https://i.imgur.com/elyZJ9A.png)

    ```
    emmet.pyv8loader: Unable to download packages list. HTTP error 403 downloading
    https://api.github.com/repos/emmetio/pyv8-binaries/contents.
    error: Error while loading PyV8 binary: exit code 1
    Try to manually install PyV8 from
    https://github.com/emmetio/pyv8-binaries
    ```

    It seems it cannot always download the `pyv8-binaries` as the GitHub may be throttling your
    connection as you just downloaded a lot of contents. So, you can try to manually download the
    contents at [pyv8-binaries](https://github.com/emmetio/pyv8-binaries) or just wait another hour
    and restart Sublime Text, so the package can download the contents by itself.


___
## Synced Side Bar Watcher

The plugin `synced_side_bar_watcher.py` creates the command `synced_side_bar_reveal_in_side_bar`,
to replace the default context menu command `SyncedSideBarRevealInSideBar`.

[forum#22753](https://forum.sublimetext.com/t/solved-how-to-add-remove-a-default-menu-entry-when-a-x-package-is-isnt-enabled-installed/22753) How to add/remove a default menu entry when a X package is/isn’t enabled/installed?



___
## Studio Installer

The plugin `studio_installer.py` performs the installation of the [Sublime Text
Studio](https://github.com/evandrocoan/SublimeTextStudio) packages by the `Package Control` when
installing the normal version, or by `git` when installing the development version of the `Sublime
Text Studio`.



___
## Submodules Manager

The package `submodules_manager.py` run several operations based on the `.gitmodules` file on the
Sublime Text Data folder (the folder at `Packages/../`) and `Backstroke.gitmodules` file on the
Sublime Text Data folder (the folder at `Packages/../Local`). Here is a sample of the structure of
both files:

**.gitmodules**
```shell
[submodule "Packages/Better CoffeeScript"]
	path = Packages/Better CoffeeScript
	url = https://github.com/evandrocoan/sublime-better-coffeescript
	upstream = https://github.com/aponxi/sublime-better-coffeescript
[submodule "Packages/BufferScroll"]
	path = Packages/BufferScroll
	url = https://github.com/evandrocoan/BufferScroll
	upstream = https://github.com/titoBouzout/BufferScroll
	dependency = PythonDebugTools
```

**Backstroke.gitmodules**
```shell
[submodule "Packages"]
url = https://github.com/evandrocoan/Packages
upstream = https://github.com/sublimehq/Packages
backstroke = https://backstroke.us/_48c38b8a08174b2d82221f7

[submodule "Packages/ANSIescape"]
url = https://github.com/evandrocoan/SublimeANSI
upstream = https://github.com/aziz/SublimeANSI
backstroke = https://backstroke.us/_2d82221f793d50c2f75952c
```



___
## License

All files in this repository, i.e., excluding its `git submodules` and the files which include its
own license header, are released under GNU General Public License v3.0 or the latest version
available on http://www.gnu.org/licenses/gpl.html

For more information see:

1. The [LICENSE](LICENSE) file for the GPL v3.0 license
1. The website https://www.gnu.org/licenses/gpl-3.0.en.html


