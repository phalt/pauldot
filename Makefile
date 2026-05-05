help:
	@echo Developer commands for pauldot
	@echo
	@grep -E '^[ .a-zA-Z_-]+:.*? ## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*? ## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo

install:  ## Install requirements ready for development
	uv sync

format:  ## Format the code
	uv run ruff format .
	uv run ruff check --fix .

lint:  ## Run the linter
	uv run ruff check .

test:  ## Run tests
	uv run pytest

clean:  ## Clear cache files and build outputs
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf dist/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
