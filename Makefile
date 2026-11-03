# Developer shortcuts. Run `make help`.
IMAGE ?= student-portal:local
PORT  ?= 8080

.PHONY: help install lint test run docker-build docker-run docker-smoke k8s-render

help:            ## Show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install:         ## Create .venv and install dev dependencies
	python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt

lint:            ## Ruff lint + format check
	ruff check . && ruff format --check .

test:            ## Run unit tests with coverage
	pytest

run:             ## Run locally with Flask dev server (SQLite)
	FLASK_APP="app:create_app()" flask run --port $(PORT) --debug

docker-build:    ## Build the container image
	docker build --build-arg APP_VERSION=local -t $(IMAGE) .

docker-run:      ## Run the container on http://localhost:$(PORT)
	docker run --rm -p $(PORT):8080 $(IMAGE)

docker-smoke:    ## Build, start, probe and stop the container
	docker rm -f sis-smoke >/dev/null 2>&1 || true
	docker run -d --name sis-smoke -p 127.0.0.1:$(PORT):8080 $(IMAGE)
	sleep 4; curl -fsS http://127.0.0.1:$(PORT)/healthz; echo
	curl -fsS http://127.0.0.1:$(PORT)/ | grep -o "Welcome to the Student Portal"
	docker rm -f sis-smoke >/dev/null

k8s-render:      ## Render the manifests Argo CD will apply
	kubectl kustomize k8s/
