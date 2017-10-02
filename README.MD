# Sublime Text Studio


Manages the packages installed.



___
## Synced Side Bar Watcher

The package `synced_side_bar_watcher.py` creates the command `synced_side_bar_reveal_in_side_bar`,
to replace the default context menu command `SyncedSideBarRevealInSideBar`.

[forum#22753](https://forum.sublimetext.com/t/solved-how-to-add-remove-a-default-menu-entry-when-a-x-package-is-isnt-enabled-installed/22753) How to add/remove a default menu entry when a X package is/isn’t enabled/installed?



___
## Channel Manager

The package `channel_manager.py` creates the files `channel.json` and `repository.json` based on the
`.gitmodules` file on the Sublime Text Data folder (the folder at `Packages/../`).

To call it, you can open the command palette and type `Studio Channel: Generate Channel File`. See
the following threads for more information about the `Package Control` channel and repository files:

1. https://packagecontrol.io/docs/dependencies  DOCS - Dependencies
1. https://packagecontrol.io/docs/channels_and_repositories Channels and Repositories
1. https://github.com/wbond/package_control/issues/1089 Package dependencies (install dependent sublime packages)
1. https://forum.sublimetext.com/t/dependencies-in-package-control-3/14646 Dependencies in Package Control 3
1. https://github.com/wbond/package_control/issues/1070 [Meta] What to do when a dependency update includes breaking changes?
1. https://forum.sublimetext.com/t/modules-dependencies-best-practices/21037 Modules + Dependencies : Best Practices?



___
## Studio Installer

The `studio_installer.py` performs the installation of the [Sublime Text
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


