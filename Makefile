UI_FILES = $(wildcard gui/*.ui)
TS_FILES = $(wildcard i18n/*.ts)
PY_FILES = $(wildcard *.py) $(wildcard gui/*.py) $(wildcard luftdatentool/*.py)

UI_COMPILED = $(UI_FILES:.ui=.py)
TS_COMPILED = $(TS_FILES:.ts=.qm)

# python3.6 on Windows is only available as python.exe
ifeq (, $(shell which python3))
PY ?= python
else
PY ?= python3
endif

%.py: %.ui
	pyuic5 $< > $@

%.qm: %.ts
	lrelease $<

all: $(UI_COMPILED) $(TS_COMPILED)

clean:
	rm $(UI_COMPILED)
	rm $(TS_COMPILED)

run: all
	$(PY) luftdaten-tool.py

# Updates all translation files in i18n/ directory
i18n-update: $(UI_COMPILED)
	@for f in $(TS_FILES) ; do \
		pylupdate5 $(PY_FILES) -ts $$f -verbose; \
	done

deps:
	$(PY) -m pip install -U -r requirements.txt

# Here go platform-specific buildsteps
UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Darwin)
PLATFORM_DEPS := assets/logo.icns
assets/logo.icns: assets/logo.png
	deploy/mkicns $<
endif

dist: all $(PLATFORM_DEPS)
	$(PY) -m PyInstaller -y luftdaten-tool.spec

dmg: dist
	dmgbuild -s deploy/dmgbuild_settings.py -D app=dist/Luftdaten.info\ Flashing\ Tool.app "Luftdaten.info Flashing Tool" dist/luftdaten-tool.dmg
