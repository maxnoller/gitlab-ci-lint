# Test Suite Design: gitlab-ci-lint

## Executive Summary

This document outlines a comprehensive test strategy for the `gitlab-ci-lint` CLI tool. The tool validates `.gitlab-ci.yml` files offline using JSON schema validation and semantic checks.

---

## 1. Current State Analysis

### 1.1 Source Files Inventory

| File | Responsibility | Complexity |
|------|----------------|------------|
| `src/gitlab_ci_lint/cli.py` | Click CLI with text/JSON output | Low |
| `src/gitlab_ci_lint/linter.py` | Core orchestration: YAML parse, schema validate, semantic checks | Medium |
| `src/gitlab_ci_lint/semantic.py` | Semantic validation functions | High |
| `src/gitlab_ci_lint/schema/__init__.py` | Schema loading with caching | Low |

### 1.2 Existing Test Coverage

**Location**: `tests/test_linter.py` (7 tests)

| Test | What It Covers | Level |
|------|---------------|-------|
| `test_valid_simple_file` | Happy path file linting | Integration |
| `test_invalid_yaml_syntax` | YAML parse error handling | Integration |
| `test_invalid_schema` | Schema validation error | Integration |
| `test_invalid_needs_reference` | `needs` semantic check | Integration |
| `test_invalid_extends_reference` | `extends` semantic check | Integration |
| `test_circular_extends` | Circular `extends` detection | Integration |
| `test_lint_string_valid` | String-based linting API | Integration |

**Existing Fixtures**: 5 YAML files in `tests/fixtures/`

### 1.3 Coverage Gaps Identified

| Gap | Risk | Priority |
|-----|------|----------|
| CLI layer completely untested | High - user-facing entry point | P0 |
| `check_stages()` function untested | Medium - validates stage ordering | P1 |
| Error message content not asserted | Medium - user experience | P1 |
| Edge cases in semantic functions | Medium - correctness | P1 |
| Schema loading/caching untested | Low - simple code | P2 |
| JSON output format untested | Medium - API contract | P1 |
| File not found handling | Low - basic error | P2 |
| Empty/malformed YAML edge cases | Medium - robustness | P1 |

### 1.4 Quality Issues in Existing Tests

1. **Missing error message assertions**: Tests check `is_valid` but not error content
2. **No parametrization**: Similar tests could be combined
3. **No CLI tests**: The primary user interface is untested
4. **Limited edge case coverage**: Only happy path and one failure mode per area
5. **No conftest.py**: Missing shared fixtures

---

## 2. Test Architecture Design

### 2.1 Recommended Directory Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── fixtures/                      # Test data files
│   ├── valid/                     # Valid YAML files
│   │   ├── minimal.yml
│   │   ├── with_stages.yml
│   │   ├── with_needs.yml
│   │   ├── with_extends.yml
│   │   └── full_featured.yml
│   ├── invalid/                   # Invalid YAML files
│   │   ├── yaml_syntax_error.yml
│   │   ├── schema/
│   │   │   ├── unknown_property.yml
│   │   │   ├── wrong_type.yml
│   │   │   └── missing_script.yml
│   │   └── semantic/
│   │       ├── needs_unknown_job.yml
│   │       ├── extends_unknown.yml
│   │       ├── circular_extends_simple.yml
│   │       ├── circular_extends_chain.yml
│   │       └── stage_undefined.yml
│   └── edge_cases/
│       ├── empty.yml
│       ├── only_comments.yml
│       └── unicode_job_names.yml
├── unit/                          # Unit tests (pure functions)
│   └── test_semantic.py
├── integration/                   # Integration tests (module boundaries)
│   ├── test_linter.py
│   └── test_schema.py
└── e2e/                          # End-to-end tests (CLI)
    └── test_cli.py
```

### 2.2 Test Portfolio Allocation

| Layer | Files | Purpose | Run Frequency |
|-------|-------|---------|---------------|
| **Unit** | `test_semantic.py` | Validate pure semantic functions in isolation | Every commit |
| **Integration** | `test_linter.py`, `test_schema.py` | Validate component interactions | Every commit |
| **E2E** | `test_cli.py` | Validate CLI contract and output formats | Every commit |

### 2.3 Fixture Strategy

**Shared fixtures in `conftest.py`**:

```python
import pytest
from pathlib import Path
from click.testing import CliRunner
from gitlab_ci_lint.linter import GitLabCILinter


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


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
def linter() -> GitLabCILinter:
    """Return fresh linter instance."""
    return GitLabCILinter()


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_yaml_file(tmp_path):
    """Factory fixture to create temporary YAML files."""
    def _create(content: str, name: str = "test.yml") -> Path:
        file_path = tmp_path / name
        file_path.write_text(content)
        return file_path
    return _create
```

---

## 3. Detailed Test Specifications

### 3.1 Unit Tests: `tests/unit/test_semantic.py`

#### 3.1.1 `get_jobs()` Function

| Test Case | Input | Expected |
|-----------|-------|----------|
| Extract regular jobs | `{"build": {...}, "test": {...}}` | `{"build": {...}, "test": {...}}` |
| Filter out global keywords | `{"stages": [...], "build": {...}, "variables": {...}}` | `{"build": {...}}` |
| Filter dot-prefixed templates | `{".template": {...}, "build": {...}}` | `{"build": {...}}` |
| Handle empty config | `{}` | `{}` |
| Handle only global keys | `{"stages": [], "variables": {}}` | `{}` |

```python
@pytest.mark.parametrize("config,expected_jobs", [
    ({"build": {"script": "echo"}}, {"build"}),
    ({"stages": ["test"], "build": {"script": "echo"}}, {"build"}),
    ({".template": {"script": "echo"}, "build": {"script": "echo"}}, {"build"}),
    ({}, set()),
    ({"default": {}, "workflow": {}}, set()),
])
def test_get_jobs(config, expected_jobs):
    from gitlab_ci_lint.semantic import get_jobs
    assert set(get_jobs(config).keys()) == expected_jobs
```

#### 3.1.2 `check_needs()` Function

| Test Case | Scenario | Expected Errors |
|-----------|----------|-----------------|
| Valid needs references | Job A needs Job B, both exist | `[]` |
| Unknown job in needs | Job references non-existent job | `["needs unknown job"]` |
| Empty needs array | `needs: []` | `[]` |
| Needs with dict syntax | `needs: [{job: "build"}]` | Valid or error depending on existence |
| Needs with optional:true | Optional job doesn't exist | `[]` (should pass) |
| Multiple needs errors | Several invalid references | Multiple error messages |
| Self-reference in needs | Job needs itself | Error |

#### 3.1.3 `check_stages()` Function

| Test Case | Scenario | Expected Errors |
|-----------|----------|-----------------|
| Valid stage assignment | Job uses defined stage | `[]` |
| Undefined stage | Job uses stage not in `stages:` | `["uses undefined stage"]` |
| Default stages | No `stages:` key, jobs use `build`/`test`/`deploy` | `[]` |
| Custom stages only | Custom stages defined, job uses default | Error |

#### 3.1.4 `check_extends()` Function

| Test Case | Scenario | Expected Errors |
|-----------|----------|-----------------|
| Valid extends | Job extends `.template` that exists | `[]` |
| Unknown template | Extends non-existent template | `["extends unknown job"]` |
| Multiple extends | `extends: [.a, .b]` both exist | `[]` |
| Multiple extends one missing | `extends: [.a, .missing]` | Error for missing |
| Extends regular job | Extends non-template job | `[]` (valid in GitLab) |

#### 3.1.5 `check_circular_extends()` Function

| Test Case | Scenario | Expected Errors |
|-----------|----------|-----------------|
| No extends | No jobs use extends | `[]` |
| Simple chain | A -> B -> C (no cycle) | `[]` |
| Self-reference | A extends A | `["circular extends"]` |
| Two-node cycle | A extends B, B extends A | `["circular extends"]` |
| Three-node cycle | A -> B -> C -> A | `["circular extends"]` |
| Diamond (no cycle) | A -> B, A -> C, B -> D, C -> D | `[]` |

### 3.2 Integration Tests: `tests/integration/test_linter.py`

#### 3.2.1 `GitLabCILinter.lint()` Method

| Test Case | Input | Expected |
|-----------|-------|----------|
| Valid minimal config | `stages: [build]\nbuild:\n  script: echo` | `is_valid=True, errors=[]` |
| Valid complex config | Full-featured YAML | `is_valid=True` |
| YAML syntax error | `foo: [bar` (unclosed bracket) | `is_valid=False`, error contains "YAML" |
| Schema validation error | Unknown property | `is_valid=False`, error indicates property |
| Semantic error (needs) | Invalid needs reference | `is_valid=False`, specific error |
| Semantic error (stages) | Undefined stage | `is_valid=False`, specific error |
| Semantic error (extends) | Missing template | `is_valid=False`, specific error |
| Multiple errors | Several issues | All errors reported |
| Empty string | `""` | `is_valid=False` or handle gracefully |
| Non-dict YAML | `"just a string"` | `is_valid=False`, meaningful error |

```python
@pytest.mark.parametrize("yaml_content,expected_error_substring", [
    ("foo: [", "YAML"),
    ("build:\n  scrip: echo", "scrip"),  # typo, schema error
    ("build:\n  script: echo\n  needs: [missing]", "missing"),
])
def test_lint_invalid_yaml(linter, yaml_content, expected_error_substring):
    result = linter.lint(yaml_content)
    assert not result.is_valid
    assert any(expected_error_substring in err for err in result.errors)
```

#### 3.2.2 `GitLabCILinter.lint_file()` Method

| Test Case | Input | Expected |
|-----------|-------|----------|
| Valid file | Path to valid YAML | `is_valid=True` |
| Invalid file | Path to invalid YAML | `is_valid=False` with errors |
| Non-existent file | Path that doesn't exist | Graceful error handling |
| Not a file (directory) | Path to directory | Graceful error handling |
| Permission denied | Unreadable file | Graceful error handling |

### 3.3 E2E Tests: `tests/e2e/test_cli.py`

#### 3.3.1 Basic CLI Invocation

| Test Case | Command | Expected Exit Code | Output Contains |
|-----------|---------|-------------------|-----------------|
| Help flag | `--help` | 0 | Usage information |
| Valid file | `<valid.yml>` | 0 | Success indicator |
| Invalid file | `<invalid.yml>` | Non-zero | Error details |
| Non-existent file | `missing.yml` | Non-zero | File not found message |

#### 3.3.2 Output Formats

| Test Case | Command | Expected |
|-----------|---------|----------|
| Default (text) format - valid | `<valid.yml>` | Human-readable success |
| Default (text) format - invalid | `<invalid.yml>` | Human-readable errors |
| JSON format - valid | `--format json <valid.yml>` | Valid JSON with success |
| JSON format - invalid | `--format json <invalid.yml>` | Valid JSON with errors |

```python
import json

def test_cli_valid_file_text_output(cli_runner, temp_yaml_file, valid_yaml_content):
    from gitlab_ci_lint.cli import cli
    yaml_file = temp_yaml_file(valid_yaml_content)
    result = cli_runner.invoke(cli, [str(yaml_file)])
    assert result.exit_code == 0


def test_cli_json_output_structure(cli_runner, temp_yaml_file, valid_yaml_content):
    from gitlab_ci_lint.cli import cli
    yaml_file = temp_yaml_file(valid_yaml_content)
    result = cli_runner.invoke(cli, ["--format", "json", str(yaml_file)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, dict)
```

---

## 4. Edge Cases and Boundary Conditions

### 4.1 YAML Edge Cases

| Case | Example | Expected Behavior |
|------|---------|-------------------|
| Empty file | 0 bytes | Clear error message |
| Only YAML comments | `# comment only` | Error or valid empty |
| Unicode in job names | `build_日本語` | Handle correctly |
| Anchors and aliases | `&anchor` / `*anchor` | Resolved before validation |
| Multi-document YAML | `---\n...\n---` | First document or error |
| Duplicate keys | Same job name twice | YAML parser behavior |
| Null values | `script: ~` | Schema validation |

### 4.2 GitLab CI Semantic Edge Cases

| Case | Scenario | Expected |
|------|----------|----------|
| Hidden jobs (`.name`) | Only hidden jobs defined | Valid (they're templates) |
| `trigger:` jobs | Child pipeline triggers | May not have `script` |
| `include:` directive | External file inclusion | Not resolved (out of scope) |
| DAG without stages | Only `needs:`, no `stages:` | Valid in GitLab |

---

## 5. Test Data Requirements

### 5.1 New Fixture Files Needed

**Valid configurations** (`tests/fixtures/valid/`):

1. `minimal.yml` - Bare minimum valid config
2. `with_stages.yml` - Custom stages defined and used
3. `with_needs_dag.yml` - DAG using needs
4. `with_extends_chain.yml` - Multi-level extends inheritance
5. `full_featured.yml` - Uses all major features
6. `only_templates.yml` - Only `.hidden` template jobs

**Invalid configurations** (`tests/fixtures/invalid/`):

1. `yaml_unclosed_bracket.yml` - Syntax error
2. `yaml_bad_indent.yml` - Indentation error
3. `schema_unknown_key.yml` - Unknown property
4. `schema_wrong_type.yml` - Wrong type for property
5. `needs_nonexistent.yml` - Needs unknown job
6. `extends_missing.yml` - Extends non-existent template
7. `extends_circular_self.yml` - Self-extending job
8. `extends_circular_chain.yml` - A->B->C->A cycle
9. `stage_undefined.yml` - Uses undefined stage

### 5.2 Inline Test Data

For unit tests, prefer inline YAML strings over files:

```python
VALID_MINIMAL = """
stages:
  - build

build:
  stage: build
  script: echo "hello"
"""

NEEDS_UNKNOWN_JOB = """
stages:
  - build
  - test

build:
  stage: build
  script: echo "build"

test:
  stage: test
  script: echo "test"
  needs:
    - nonexistent_job
"""
```

---

## 6. Implementation Priorities

### Phase 1: Foundation (P0)

1. Create `tests/conftest.py` with shared fixtures
2. Add CLI tests (`tests/e2e/test_cli.py`) - currently zero coverage
3. Reorganize existing tests into `tests/integration/`

### Phase 2: Coverage Expansion (P1)

1. Unit tests for all `semantic.py` functions (`tests/unit/test_semantic.py`)
2. Parametrize existing integration tests
3. Add error message content assertions
4. Create comprehensive fixture files
5. Test `check_stages()` function (currently untested)

### Phase 3: Edge Cases (P2)

1. Edge case YAML files
2. File system error handling tests
3. Schema loading and caching tests
4. Large file / performance tests (optional)

---

## 7. Test Configuration

### 7.1 pytest Configuration (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = [
    "-v",
    "--strict-markers",
    "-ra",
]
markers = [
    "slow: marks tests as slow",
    "e2e: end-to-end tests",
]
```

### 7.2 Coverage Configuration

```toml
[tool.coverage.run]
source = ["src/gitlab_ci_lint"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
]
fail_under = 80
```

---

## 8. Metrics and Goals

### 8.1 Coverage Targets

| Module | Current (Est.) | Target |
|--------|---------------|--------|
| `cli.py` | 0% | 90% |
| `linter.py` | ~60% | 95% |
| `semantic.py` | ~40% | 95% |
| `schema/__init__.py` | 0% | 80% |
| **Overall** | ~30% | 85% |

### 8.2 Test Count Targets

| Category | Current | Target |
|----------|---------|--------|
| Unit tests | 0 | 25+ |
| Integration tests | 7 | 20+ |
| E2E tests | 0 | 10+ |
| **Total** | 7 | 55+ |

---

## 9. Key Code Paths to Test

### 9.1 `linter.py` Code Paths

```
lint(content: str)
├── yaml.safe_load() -> YAMLError -> return error
├── isinstance(config, dict) check -> False -> return error
├── jsonschema.validate() -> ValidationError -> collect errors
├── check_stages() -> collect errors
├── check_needs() -> collect errors
├── check_extends() -> collect errors
├── check_circular_extends() -> collect errors
└── return LintResult

lint_file(path: Path)
├── path.read_text() -> Exception -> handle error
└── lint(content)
```

### 9.2 `semantic.py` Code Paths

```
check_needs(config)
├── get_jobs(config) -> jobs dict
├── For each job with 'needs':
│   ├── needs is list of strings -> check each exists
│   └── needs is list of dicts -> extract 'job' key, check
└── return errors

check_stages(config)
├── Get defined stages (or defaults: [build, test, deploy])
├── For each job with 'stage':
│   └── Check stage in defined stages
└── return errors

check_extends(config)
├── For each item with 'extends':
│   ├── extends is string -> check exists
│   └── extends is list -> check each exists
└── return errors

check_circular_extends(config)
├── Build extends graph
├── DFS for cycles
└── return errors if cycle found
```

---

## 10. Summary

This test design provides a comprehensive strategy to increase test coverage from approximately 30% to 85%+, with focus on:

1. **CLI testing** - Currently the biggest gap (0% coverage)
2. **Semantic validation edge cases** - Complex logic needs thorough testing
3. **Error message quality** - Ensure user-facing errors are helpful
4. **Parametrized tests** - Reduce duplication, increase scenarios

The recommended approach prioritizes integration tests at module boundaries while using unit tests for the complex semantic validation logic where isolation helps verify correctness.
