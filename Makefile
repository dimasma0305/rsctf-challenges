RSCTF ?= rsctf

.PHONY: help list validate matrix

help:
	@echo "rsctf challenge repository commands"
	@echo ""
	@echo "  make list              List the example manifests"
	@echo "  make validate          Validate the repository with the official rsctf CLI"
	@echo "  make matrix            Print the Docker build matrix from the rsctf CLI"

list:
	@find challenges -name challenge.yaml -type f -print | sort

validate:
	$(RSCTF) challenge check --deny-warnings .

matrix:
	$(RSCTF) challenge matrix .
