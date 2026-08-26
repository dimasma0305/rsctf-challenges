PYTHON ?= python3
NODE ?= node
DOCKER ?= docker
RSCTF ?= rsctf
CHECKER_VENV ?= .checker-venv
CHECKER_PYTHON := $(CHECKER_VENV)/bin/python
CHECKER_REQUIREMENTS := \
	challenges/AD/Pwn/attack-defense-service/checker/requirements.txt \
	challenges/AD/Web/self-hosted-service/checker/requirements.txt
CHECKER_STAMP := $(CHECKER_VENV)/.rsctf-example-deps

.PHONY: help list validate validate-platform checker-deps test-fast test-checkers test build-containers test-container-images verify

help:
	@echo "rsctf challenge repository commands"
	@echo ""
	@echo "  make list              List the example manifests"
	@echo "  make validate          Validate manifests and compile Python"
	@echo "  make validate-platform Validate manifests with the official rsctf CLI"
	@echo "  make test-fast         Test provenance and the KotH referee"
	@echo "  make test-checkers     Install pinned checker wheels and test verdicts"
	@echo "  make test              Run every package-free and checker test"
	@echo "  make build-containers  Build all example services and the generator"
	@echo "  make test-container-images  Run built services through Docker health and smoke checks"
	@echo "  make verify            Run tests and build every container"

list:
	@find challenges -name challenge.yaml -type f -print | sort

validate:
	$(NODE) scripts/validate.mjs
	$(PYTHON) -m compileall -q challenges scripts

validate-platform:
	$(RSCTF) challenge check --deny-warnings .

checker-deps: $(CHECKER_STAMP)

$(CHECKER_STAMP): $(CHECKER_REQUIREMENTS)
	@test -x "$(CHECKER_PYTHON)" || $(PYTHON) -m venv "$(CHECKER_VENV)"
	$(CHECKER_PYTHON) -m pip install \
		--disable-pip-version-check \
		--no-input \
		--only-binary=:all: \
		-- \
		pwntools==4.15.0 \
		httpx==0.28.1
	@touch "$(CHECKER_STAMP)"

test-fast:
	$(PYTHON) scripts/container-images.py check
	$(PYTHON) scripts/test-container-discovery.py
	$(NODE) scripts/test-catalog-extension.mjs
	$(PYTHON) scripts/test-koth-observer.py
	$(PYTHON) scripts/test-provenance.py
	$(NODE) scripts/test-provenance-automation.mjs

test-checkers: checker-deps
	$(CHECKER_PYTHON) scripts/test-checkers.py

test: validate test-fast test-checkers

build-containers:
	$(PYTHON) scripts/container-images.py build --docker "$(DOCKER)"

test-container-images:
	$(PYTHON) scripts/container-images.py test --docker "$(DOCKER)"

verify: test test-container-images
