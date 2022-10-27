PATH := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PYTHON3 := .venv/bin/python3

.PHONY: test
test:
	UPSET_VERBOSITY=1 UPSET_INTERACTION=0 PYTHONPATH=$${PYTHONPATH}:"$(PATH)/src" $(PYTHON3) -m unittest discover -s tests -v
