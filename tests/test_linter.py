import pytest

from gitlab_ci_lint.linter import GitLabCILinter


@pytest.fixture
def linter():
    return GitLabCILinter()


class TestYAMLParsing:
    def test_invalid_yaml(self, linter: GitLabCILinter):
        content = "invalid: yaml: content:"
        errors = linter.lint(content)
        assert len(errors) == 1
        assert "YAML parsing error" in errors[0]

    def test_empty_file(self, linter: GitLabCILinter):
        errors = linter.lint("")
        assert len(errors) == 1
        assert "empty" in errors[0].lower()


class TestSchemaValidation:
    def test_valid_minimal(self, linter: GitLabCILinter):
        content = """
stages:
  - build

build-job:
  stage: build
  script:
    - echo "Hello"
"""
        errors = linter.lint(content)
        assert errors == []

    def test_invalid_artifact_type(self, linter: GitLabCILinter):
        content = """
job:
  script: echo test
  artifacts:
    path: "should-be-paths-array"
"""
        errors = linter.lint(content)
        assert len(errors) >= 1


class TestSemanticChecks:
    def test_invalid_needs_reference(self, linter: GitLabCILinter):
        content = """
stages:
  - build
  - test

build-job:
  stage: build
  script: echo build

test-job:
  stage: test
  needs: ["nonexistent-job"]
  script: echo test
"""
        errors = linter.lint(content)
        assert any("nonexistent-job" in e for e in errors)

    def test_invalid_stage_reference(self, linter: GitLabCILinter):
        content = """
stages:
  - build

deploy-job:
  stage: deploy
  script: echo deploy
"""
        errors = linter.lint(content)
        assert any("deploy" in e and "stage" in e for e in errors)

    def test_invalid_extends_reference(self, linter: GitLabCILinter):
        content = """
job:
  extends: .nonexistent-template
  script: echo test
"""
        errors = linter.lint(content)
        assert any(".nonexistent-template" in e for e in errors)
