luftdaten.info flashing tool
============================

Binary builds
-------------

Our main target is having working prebuilt binaries for users to simply
download and run, to avoid all the setup below.

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
