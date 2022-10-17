PATH := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PYTHON3 := /usr/bin/python3

.PHONY: test
test:
	PYTHONPATH=$(PYTHONPATH):"$(PATH)/src" $(PYTHON3) -m unittest discover -s tests -v
