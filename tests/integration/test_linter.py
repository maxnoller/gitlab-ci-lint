"""Integration tests for GitLabCILinter."""

from pathlib import Path

import pytest

from gitlab_ci_lint.linter import GitLabCILinter


class TestLintString:
    """Tests for GitLabCILinter.lint() method with string input."""

    def test_valid_minimal_config(self, linter: GitLabCILinter, valid_yaml_content: str):
        """Valid minimal config should return no errors."""
        errors = linter.lint(valid_yaml_content)
        assert errors == []

    def test_valid_complex_config(self, linter: GitLabCILinter, valid_fixtures_dir: Path):
        """Valid complex config should return no errors."""
        content = (valid_fixtures_dir / "full_featured.yml").read_text()
        errors = linter.lint(content)
        assert errors == []

    def test_yaml_syntax_error(self, linter: GitLabCILinter):
        """YAML syntax error should be reported."""
        content = "foo: [bar"  # unclosed bracket
        errors = linter.lint(content)
        assert len(errors) == 1
        assert "YAML" in errors[0]

    def test_schema_validation_error(self, linter: GitLabCILinter):
        """Schema validation error should be reported."""
        content = """
job:
  script: echo test
  artifacts:
    paths: "should-be-array"
"""
        errors = linter.lint(content)
        assert len(errors) >= 1
        # Should mention the invalid property

    def test_semantic_error_needs(self, linter: GitLabCILinter):
        """Semantic error for invalid needs reference should be reported."""
        content = """
stages:
  - build
  - test

build:
  stage: build
  script: echo build

test:
  stage: test
  needs: [nonexistent]
  script: echo test
"""
        errors = linter.lint(content)
        assert any("nonexistent" in e for e in errors)

    def test_semantic_error_stages(self, linter: GitLabCILinter):
        """Semantic error for undefined stage should be reported."""
        content = """
stages:
  - build

deploy:
  stage: deploy
  script: echo deploy
"""
        errors = linter.lint(content)
        assert any("deploy" in e and "stage" in e for e in errors)

    def test_semantic_error_extends(self, linter: GitLabCILinter):
        """Semantic error for missing template should be reported."""
        content = """
stages:
  - build

build:
  stage: build
  extends: .missing
  script: echo build
"""
        errors = linter.lint(content)
        assert any(".missing" in e for e in errors)

    def test_multiple_errors(self, linter: GitLabCILinter):
        """Multiple errors should all be reported."""
        content = """
stages:
  - build

job1:
  stage: build
  needs: [missing1]
  script: echo

job2:
  stage: build
  extends: .missing2
  script: echo
"""
        errors = linter.lint(content)
        assert len(errors) >= 2
        assert any("missing1" in e for e in errors)
        assert any(".missing2" in e for e in errors)

    def test_empty_string(self, linter: GitLabCILinter):
        """Empty string should be handled gracefully."""
        errors = linter.lint("")
        assert len(errors) == 1
        assert "empty" in errors[0].lower() or "invalid" in errors[0].lower()

    def test_non_dict_yaml(self, linter: GitLabCILinter):
        """YAML that parses to non-dict should be handled gracefully."""
        errors = linter.lint("- just\n- a\n- list")
        assert len(errors) == 1
        assert "invalid" in errors[0].lower() or "dict" in errors[0].lower()

    def test_scalar_yaml(self, linter: GitLabCILinter):
        """Scalar YAML should be handled gracefully."""
        errors = linter.lint("just a string")
        assert len(errors) == 1


class TestLintFile:
    """Tests for GitLabCILinter.lint_file() method."""

    def test_valid_file(self, linter: GitLabCILinter, valid_fixtures_dir: Path):
        """Valid file should return no errors."""
        file_path = valid_fixtures_dir / "minimal.yml"
        errors = linter.lint_file(str(file_path))
        assert errors == []

    def test_invalid_file(self, linter: GitLabCILinter, invalid_fixtures_dir: Path):
        """Invalid file should return errors."""
        file_path = invalid_fixtures_dir / "needs_nonexistent.yml"
        errors = linter.lint_file(str(file_path))
        assert len(errors) >= 1
        assert any("nonexistent" in e for e in errors)

    def test_nonexistent_file(self, linter: GitLabCILinter):
        """Non-existent file should return graceful error."""
        errors = linter.lint_file("/nonexistent/path/file.yml")
        assert len(errors) == 1
        assert "could not read" in errors[0].lower() or "no such file" in errors[0].lower()

    def test_directory_instead_of_file(self, linter: GitLabCILinter, tmp_path: Path):
        """Passing a directory should return graceful error."""
        errors = linter.lint_file(str(tmp_path))
        assert len(errors) == 1

    def test_temp_yaml_file(self, linter: GitLabCILinter, temp_yaml_file):
        """Test with temp_yaml_file factory fixture."""
        content = """
stages:
  - build

build:
  stage: build
  script: echo hello
"""
        file_path = temp_yaml_file(content)
        errors = linter.lint_file(str(file_path))
        assert errors == []


class TestLintValidFixtures:
    """Test all valid fixture files to ensure they validate correctly."""

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "minimal.yml",
            "with_stages.yml",
            "with_needs_dag.yml",
            "with_extends_chain.yml",
            "full_featured.yml",
            "only_templates.yml",
        ],
    )
    def test_valid_fixture_files(
        self, linter: GitLabCILinter, valid_fixtures_dir: Path, fixture_name: str
    ):
        """Each valid fixture file should produce no errors."""
        file_path = valid_fixtures_dir / fixture_name
        errors = linter.lint_file(str(file_path))
        assert errors == [], f"Expected no errors for {fixture_name}, got: {errors}"


class TestLintInvalidFixtures:
    """Test all invalid fixture files to ensure they report errors."""

    def test_yaml_unclosed_bracket(self, linter: GitLabCILinter, invalid_fixtures_dir: Path):
        """YAML syntax error should be caught."""
        errors = linter.lint_file(str(invalid_fixtures_dir / "yaml_unclosed_bracket.yml"))
        assert len(errors) >= 1
        assert any("yaml" in e.lower() for e in errors)

    def test_needs_nonexistent(self, linter: GitLabCILinter, invalid_fixtures_dir: Path):
        """Invalid needs reference should be caught."""
        errors = linter.lint_file(str(invalid_fixtures_dir / "needs_nonexistent.yml"))
        assert len(errors) >= 1
        assert any("nonexistent" in e for e in errors)

    def test_extends_missing(self, linter: GitLabCILinter, invalid_fixtures_dir: Path):
        """Missing template in extends should be caught."""
        errors = linter.lint_file(str(invalid_fixtures_dir / "extends_missing.yml"))
        assert len(errors) >= 1
        assert any(".nonexistent-template" in e for e in errors)

    def test_extends_circular_self(self, linter: GitLabCILinter, invalid_fixtures_dir: Path):
        """Self-extending job should be caught."""
        errors = linter.lint_file(str(invalid_fixtures_dir / "extends_circular_self.yml"))
        assert len(errors) >= 1
        assert any("circular" in e.lower() for e in errors)

    def test_stage_undefined(self, linter: GitLabCILinter, invalid_fixtures_dir: Path):
        """Undefined stage should be caught."""
        errors = linter.lint_file(str(invalid_fixtures_dir / "stage_undefined.yml"))
        assert len(errors) >= 1
        assert any("deploy" in e for e in errors)


class TestEdgeCases:
    """Test edge case fixture files."""

    def test_empty_file(self, linter: GitLabCILinter, edge_case_fixtures_dir: Path):
        """Empty file should be handled gracefully."""
        errors = linter.lint_file(str(edge_case_fixtures_dir / "empty.yml"))
        assert len(errors) >= 1

    def test_only_comments(self, linter: GitLabCILinter, edge_case_fixtures_dir: Path):
        """File with only comments should be handled gracefully."""
        errors = linter.lint_file(str(edge_case_fixtures_dir / "only_comments.yml"))
        assert len(errors) >= 1  # Empty/null config

    def test_unicode_job_names(self, linter: GitLabCILinter, edge_case_fixtures_dir: Path):
        """Unicode in job names should be handled correctly."""
        errors = linter.lint_file(str(edge_case_fixtures_dir / "unicode_job_names.yml"))
        # This should either pass or fail gracefully depending on schema support
        # The important thing is no crash
        assert isinstance(errors, list)
