luftdaten.info flashing tool
============================

Binary builds
-------------

Our main target is having working prebuilt binaries for users to simply
download and run, to avoid all the setup below.

### Linux
Currently Linux builds require *Python 3.6* (but 3.7 seems to work fine as
well), GNU make and Qt Linguist tools. Following packages should suffice on
Ubuntu:

    sudo apt install qttools5-dev-tools python3.6 make

Then, to install python dependencies and build the binary use:

    make deps dist

### Windows

Currently Windows builds require *Python 3.6* installed system-wide and added to
`%PATH%`.

To install python and cygwin dependencies and build everything use
`deploy\windows-build.bat` batch script.

### MacOS
Currently MacOS builds require *Python 3.6*, `dmgbuild` tool (`pip3 install
dmgbuild`) and Qt SDK installed (just the "Qt >
5... > macOS" part in installer) with following added to $PATH:

    export PATH="$HOME/Qt/5.11.1/clang_64/bin:/Library/Frameworks/Python.framework/Versions/3.6/bin:$PATH"

Then just install dependencies and build everything using:

    make deps dmg

### Binary build debugging

In case an error occurs in early stages of application startup, user will be
presented with a "Failed to execute script luftdaten-tool.exe" message. In order
to see actual source of that error, `console` flag in `luftdaten-tool.spec` can
be switched to `True`. In Windows this will make application output a proper
stack trace to `cmd` popup.

Development
-----------

Both build & runtime requirements are defined in `requirements.txt` file. In
order to install these use the following command:

    pip install -r requirements.txt

To manage dynamic UI and translation binaries generation we use a very simple
GNU make-based build system.

To simply build everything needed to run `luftdaten-tool.py` run:

    make

To build and run use:

    make run

To remove all build artifacts use:

    make clean

All requirements are set up using wildcards, so, in theory, `Makefile` shouldn't
need much changes in near future.

Translations
------------

In order to rebuild `*.ts` files use:

    make i18n-update
