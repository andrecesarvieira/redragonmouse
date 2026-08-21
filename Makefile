.PHONY: run test setup rpm

run:
	python3 run.py

test:
	python3 -m unittest discover -s tests -v

setup:
	bash scripts/setup-fedora.sh

rpm:
	bash scripts/build-rpm.sh
