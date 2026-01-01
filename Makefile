.PHONY: test test-verbose test-watch install help

help:
	@echo "Available commands:"
	@echo "  make test         - Run tests (short output)"
	@echo "  make test-verbose - Run tests with verbose output"
	@echo "  make install      - Install dependencies"
	@echo "  make help         - Show this help message"

test:
	poetry run pytest

test-verbose:
	poetry run pytest -v

test-watch:
	poetry run pytest-watch

install:
	poetry install
