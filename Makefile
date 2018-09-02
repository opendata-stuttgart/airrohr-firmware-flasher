UI_FILES = $(wildcard gui/*.ui)
TS_FILES = $(wildcard i18n/*.ts)
PY_FILES = $(wildcard *.py) $(wildcard gui/*.py)

UI_COMPILED = $(UI_FILES:.ui=.py)
TS_COMPILED = $(TS_FILES:.ts=.qm)

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

dist: all
	$(PY) -m PyInstaller -y luftdaten-tool.spec

deps:
	$(PY) -m pip install -U -r requirements.txt

i18n-update:
	@for f in $(TS_FILES) ; do \
		pylupdate5 *.py gui/*.py -ts $$f -verbose; \
	done
