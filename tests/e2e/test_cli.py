"""End-to-end tests for the gitlab-ci-lint CLI."""

import json
from pathlib import Path

from click.testing import CliRunner

from gitlab_ci_lint.cli import cli


class TestCLIBasicInvocation:
    """Tests for basic CLI invocation."""

    def test_help_flag(self, cli_runner: CliRunner):
        """Help flag should show usage information."""
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output or "usage:" in result.output.lower()
        assert "files" in result.output.lower()

    def test_valid_file(self, cli_runner: CliRunner, temp_yaml_file, valid_yaml_content: str):
        """Valid file should exit with code 0."""
        yaml_file = temp_yaml_file(valid_yaml_content)
        result = cli_runner.invoke(cli, [str(yaml_file)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower() or "✓" in result.output

    def test_invalid_file(self, cli_runner: CliRunner, temp_yaml_file):
        """Invalid file should exit with non-zero code."""
        content = """
stages:
  - build

build:
  stage: build
  needs: [nonexistent]
  script: echo
"""
        yaml_file = temp_yaml_file(content)
        result = cli_runner.invoke(cli, [str(yaml_file)])
        assert result.exit_code != 0
        assert "nonexistent" in result.output

    def test_nonexistent_file(self, cli_runner: CliRunner):
        """Non-existent file should show error."""
        result = cli_runner.invoke(cli, ["/nonexistent/file.yml"])
        assert result.exit_code != 0

    def test_no_files_provided(self, cli_runner: CliRunner):
        """No files provided should show error or usage."""
        result = cli_runner.invoke(cli, [])
        assert result.exit_code != 0


class TestCLIOutputFormats:
    """Tests for different output formats."""

    def test_text_format_valid(
        self, cli_runner: CliRunner, temp_yaml_file, valid_yaml_content: str
    ):
        """Text format for valid file should show success message."""
        yaml_file = temp_yaml_file(valid_yaml_content)
        result = cli_runner.invoke(cli, [str(yaml_file)])
        assert result.exit_code == 0
        # Should contain success indicator
        assert "valid" in result.output.lower() or "✓" in result.output

    def test_text_format_invalid(self, cli_runner: CliRunner, temp_yaml_file):
        """Text format for invalid file should show human-readable errors."""
        content = """
stages:
  - build

build:
  stage: build
  needs: [missing]
  script: echo
"""
        yaml_file = temp_yaml_file(content)
        result = cli_runner.invoke(cli, [str(yaml_file)])
        assert result.exit_code != 0
        assert "error" in result.output.lower() or "missing" in result.output

    def test_json_format_valid(
        self, cli_runner: CliRunner, temp_yaml_file, valid_yaml_content: str
    ):
        """JSON format for valid file should return valid JSON."""
        yaml_file = temp_yaml_file(valid_yaml_content)
        result = cli_runner.invoke(cli, ["--format", "json", str(yaml_file)])
        assert result.exit_code == 0
        # Should be valid JSON
        data = json.loads(result.output)
        assert isinstance(data, dict)
        # Should have the file path as key
        assert str(yaml_file) in data
        # Should have empty errors for valid file
        assert data[str(yaml_file)] == []

    def test_json_format_invalid(self, cli_runner: CliRunner, temp_yaml_file):
        """JSON format for invalid file should return valid JSON with errors."""
        content = """
stages:
  - build

build:
  stage: build
  needs: [nonexistent]
  script: echo
"""
        yaml_file = temp_yaml_file(content)
        result = cli_runner.invoke(cli, ["--format", "json", str(yaml_file)])
        # Note: exit code may still be non-zero for invalid files
        # The CLI prints "Aborted!" after the JSON, so we need to extract just the JSON part
        # Find the JSON object (everything before "Aborted!")
        output = result.output
        if "Aborted!" in output:
            output = output.split("Aborted!")[0].strip()
        data = json.loads(output)
        assert isinstance(data, dict)
        assert str(yaml_file) in data
        assert len(data[str(yaml_file)]) > 0
        assert any("nonexistent" in err for err in data[str(yaml_file)])


class TestCLIMultipleFiles:
    """Tests for multiple file handling."""

    def test_two_valid_files(self, cli_runner: CliRunner, temp_yaml_file, valid_yaml_content: str):
        """Two valid files should all succeed."""
        file1 = temp_yaml_file(valid_yaml_content, "file1.yml")
        file2 = temp_yaml_file(valid_yaml_content, "file2.yml")
        result = cli_runner.invoke(cli, [str(file1), str(file2)])
        assert result.exit_code == 0

    def test_one_valid_one_invalid(
        self, cli_runner: CliRunner, temp_yaml_file, valid_yaml_content: str
    ):
        """One valid and one invalid file should fail overall."""
        valid_file = temp_yaml_file(valid_yaml_content, "valid.yml")
        invalid_content = """
stages:
  - build

build:
  stage: build
  needs: [missing]
  script: echo
"""
        invalid_file = temp_yaml_file(invalid_content, "invalid.yml")
        result = cli_runner.invoke(cli, [str(valid_file), str(invalid_file)])
        assert result.exit_code != 0

    def test_multiple_files_json_format(
        self, cli_runner: CliRunner, temp_yaml_file, valid_yaml_content: str
    ):
        """Multiple files with JSON format should return all results."""
        file1 = temp_yaml_file(valid_yaml_content, "file1.yml")
        file2 = temp_yaml_file(valid_yaml_content, "file2.yml")
        result = cli_runner.invoke(cli, ["--format", "json", str(file1), str(file2)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert str(file1) in data
        assert str(file2) in data


class TestCLIWithFixtureFiles:
    """Tests using the fixture files."""

    def test_valid_fixtures(self, cli_runner: CliRunner, valid_fixtures_dir: Path):
        """All valid fixture files should pass."""
        valid_files = list(valid_fixtures_dir.glob("*.yml"))
        assert len(valid_files) > 0, "No valid fixture files found"

        for file_path in valid_files:
            result = cli_runner.invoke(cli, [str(file_path)])
            assert result.exit_code == 0, f"Expected {file_path.name} to pass, got: {result.output}"

    def test_invalid_fixtures(self, cli_runner: CliRunner, invalid_fixtures_dir: Path):
        """All invalid fixture files should fail."""
        invalid_files = list(invalid_fixtures_dir.glob("*.yml"))
        assert len(invalid_files) > 0, "No invalid fixture files found"

        for file_path in invalid_files:
            result = cli_runner.invoke(cli, [str(file_path)])
            assert result.exit_code != 0, f"Expected {file_path.name} to fail"


class TestCLIExitCodes:
    """Tests for correct exit codes."""

    def test_success_exit_code(
        self, cli_runner: CliRunner, temp_yaml_file, valid_yaml_content: str
    ):
        """Valid file should exit with code 0."""
        yaml_file = temp_yaml_file(valid_yaml_content)
        result = cli_runner.invoke(cli, [str(yaml_file)])
        assert result.exit_code == 0

    def test_error_exit_code(self, cli_runner: CliRunner, temp_yaml_file):
        """Invalid file should exit with non-zero code."""
        content = "invalid: yaml: content:"
        yaml_file = temp_yaml_file(content)
        result = cli_runner.invoke(cli, [str(yaml_file)])
        assert result.exit_code != 0

    def test_json_valid_exit_code(
        self, cli_runner: CliRunner, temp_yaml_file, valid_yaml_content: str
    ):
        """JSON format with valid file should exit with code 0."""
        yaml_file = temp_yaml_file(valid_yaml_content)
        result = cli_runner.invoke(cli, ["--format", "json", str(yaml_file)])
        assert result.exit_code == 0
