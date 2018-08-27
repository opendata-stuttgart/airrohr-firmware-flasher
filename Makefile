UI_FILES = $(wildcard gui/*.ui)
TS_FILES = $(wildcard i18n/*.ts)
PY_FILES = $(wildcard *.py) $(wildcard gui/*.py)

UI_COMPILED = $(UI_FILES:.ui=.py)
TS_COMPILED = $(TS_FILES:.ts=.qm)

%.py: %.ui
	pyuic5 $< > $@

%.qm: %.ts
	lrelease $<

all: $(UI_COMPILED) $(TS_COMPILED)

clean:
	rm $(UI_COMPILED)
	rm $(TS_COMPILED)

run: all
	python3 luftdaten-tool.py

i18n-update:
	@for f in $(TS_FILES) ; do \
		pylupdate5 *.py gui/*.py -ts $$f -verbose; \
	done
