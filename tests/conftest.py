"""Shared pytest fixtures for gitlab-ci-lint tests."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from gitlab_ci_lint.linter import GitLabCILinter


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_fixtures_dir(fixtures_dir: Path) -> Path:
    """Return path to valid fixtures directory."""
    return fixtures_dir / "valid"


@pytest.fixture
def invalid_fixtures_dir(fixtures_dir: Path) -> Path:
    """Return path to invalid fixtures directory."""
    return fixtures_dir / "invalid"


@pytest.fixture
def edge_case_fixtures_dir(fixtures_dir: Path) -> Path:
    """Return path to edge case fixtures directory."""
    return fixtures_dir / "edge_cases"


@pytest.fixture
def valid_yaml_content() -> str:
    """Return minimal valid GitLab CI YAML as string."""
    return """
stages:
  - build

build:
  stage: build
  script: echo "hello"
"""


@pytest.fixture
def valid_yaml_with_needs() -> str:
    """Return valid GitLab CI YAML with needs."""
    return """
stages:
  - build
  - test

build:
  stage: build
  script: echo "build"

test:
  stage: test
  needs: [build]
  script: echo "test"
"""


@pytest.fixture
def valid_yaml_with_extends() -> str:
    """Return valid GitLab CI YAML with extends."""
    return """
stages:
  - build

.template:
  script: echo "base"

build:
  stage: build
  extends: .template
"""


@pytest.fixture
def linter() -> GitLabCILinter:
    """Return fresh linter instance."""
    return GitLabCILinter()


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_yaml_file(tmp_path: Path):
    """Factory fixture to create temporary YAML files."""

    def _create(content: str, name: str = "test.yml") -> Path:
        file_path = tmp_path / name
        file_path.write_text(content)
        return file_path

    return _create
