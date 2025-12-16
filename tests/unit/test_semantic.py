"""Unit tests for semantic validation functions."""

import pytest

from gitlab_ci_lint.semantic import (
    check_circular_extends,
    check_extends,
    check_needs,
    check_stages,
    get_jobs,
)


class TestGetJobs:
    """Tests for get_jobs() function."""

    @pytest.mark.parametrize(
        "config,expected_jobs",
        [
            # Regular job extraction
            ({"build": {"script": "echo"}}, {"build"}),
            # Filter out global keywords
            ({"stages": ["test"], "build": {"script": "echo"}}, {"build"}),
            # Filter dot-prefixed templates
            ({".template": {"script": "echo"}, "build": {"script": "echo"}}, {"build"}),
            # Empty config
            ({}, set()),
            # Only reserved keywords
            ({"default": {}, "workflow": {}, "variables": {}}, set()),
            # Multiple jobs
            (
                {"build": {"script": "a"}, "test": {"script": "b"}, "deploy": {"script": "c"}},
                {"build", "test", "deploy"},
            ),
            # Mix of jobs, templates, and keywords
            (
                {
                    "stages": ["build"],
                    ".template": {"script": "t"},
                    "build": {"script": "b"},
                    "variables": {"FOO": "bar"},
                },
                {"build"},
            ),
            # Non-dict values are excluded
            ({"build": {"script": "echo"}, "some_string": "value"}, {"build"}),
        ],
    )
    def test_get_jobs(self, config: dict, expected_jobs: set):
        """Test that get_jobs correctly extracts job definitions."""
        assert set(get_jobs(config).keys()) == expected_jobs


class TestCheckNeeds:
    """Tests for check_needs() function."""

    def test_valid_needs_reference(self):
        """Jobs with valid needs references should not produce errors."""
        config = {
            "stages": ["build", "test"],
            "build": {"stage": "build", "script": "echo"},
            "test": {"stage": "test", "script": "echo", "needs": ["build"]},
        }
        errors = check_needs(config)
        assert errors == []

    def test_unknown_job_in_needs(self):
        """Referencing unknown job in needs should produce error."""
        config = {
            "stages": ["build", "test"],
            "build": {"stage": "build", "script": "echo"},
            "test": {"stage": "test", "script": "echo", "needs": ["nonexistent"]},
        }
        errors = check_needs(config)
        assert len(errors) == 1
        assert "nonexistent" in errors[0]
        assert "test" in errors[0]

    def test_empty_needs_array(self):
        """Empty needs array should not produce errors."""
        config = {
            "stages": ["build"],
            "build": {"stage": "build", "script": "echo", "needs": []},
        }
        errors = check_needs(config)
        assert errors == []

    def test_needs_with_dict_syntax(self):
        """Needs with dict syntax {job: name} should work."""
        config = {
            "stages": ["build", "test"],
            "build": {"stage": "build", "script": "echo"},
            "test": {"stage": "test", "script": "echo", "needs": [{"job": "build"}]},
        }
        errors = check_needs(config)
        assert errors == []

    def test_needs_with_dict_syntax_nonexistent(self):
        """Needs with dict syntax referencing nonexistent job should error."""
        config = {
            "stages": ["build", "test"],
            "build": {"stage": "build", "script": "echo"},
            "test": {"stage": "test", "script": "echo", "needs": [{"job": "missing"}]},
        }
        errors = check_needs(config)
        assert len(errors) == 1
        assert "missing" in errors[0]

    def test_multiple_needs_errors(self):
        """Multiple invalid needs should produce multiple errors."""
        config = {
            "stages": ["build"],
            "build": {"stage": "build", "script": "echo", "needs": ["missing1", "missing2"]},
        }
        errors = check_needs(config)
        assert len(errors) == 2
        assert any("missing1" in e for e in errors)
        assert any("missing2" in e for e in errors)

    def test_needs_with_project_ignored(self):
        """Needs with project key (cross-project) should not be validated locally."""
        config = {
            "stages": ["build"],
            "build": {
                "stage": "build",
                "script": "echo",
                "needs": [{"project": "other/project", "job": "external-job"}],
            },
        }
        errors = check_needs(config)
        assert errors == []

    def test_no_needs_in_config(self):
        """Jobs without needs should not produce errors."""
        config = {
            "stages": ["build"],
            "build": {"stage": "build", "script": "echo"},
        }
        errors = check_needs(config)
        assert errors == []


class TestCheckStages:
    """Tests for check_stages() function."""

    def test_valid_stage_assignment(self):
        """Jobs using defined stages should not produce errors."""
        config = {
            "stages": ["build", "test", "deploy"],
            "build-job": {"stage": "build", "script": "echo"},
            "test-job": {"stage": "test", "script": "echo"},
        }
        errors = check_stages(config)
        assert errors == []

    def test_undefined_stage(self):
        """Job using undefined stage should produce error."""
        config = {
            "stages": ["build"],
            "deploy-job": {"stage": "deploy", "script": "echo"},
        }
        errors = check_stages(config)
        assert len(errors) == 1
        assert "deploy" in errors[0]
        assert "deploy-job" in errors[0]

    def test_default_stages(self):
        """Jobs using default stages (build, test, deploy) when stages not defined."""
        config = {
            "build-job": {"stage": "build", "script": "echo"},
            "test-job": {"stage": "test", "script": "echo"},
            "deploy-job": {"stage": "deploy", "script": "echo"},
        }
        errors = check_stages(config)
        assert errors == []

    def test_custom_stages_override_defaults(self):
        """Custom stages override defaults; using default stage should error."""
        config = {
            "stages": ["custom-stage"],
            "build-job": {"stage": "build", "script": "echo"},
        }
        errors = check_stages(config)
        assert len(errors) == 1
        assert "build" in errors[0]

    def test_job_without_stage(self):
        """Jobs without explicit stage should not produce errors."""
        config = {
            "stages": ["build"],
            "build-job": {"script": "echo"},  # No stage specified
        }
        errors = check_stages(config)
        assert errors == []


class TestCheckExtends:
    """Tests for check_extends() function."""

    def test_valid_extends(self):
        """Job extending existing template should not produce errors."""
        config = {
            "stages": ["build"],
            ".template": {"script": "echo"},
            "build": {"stage": "build", "extends": ".template"},
        }
        errors = check_extends(config)
        assert errors == []

    def test_unknown_template(self):
        """Extending non-existent template should produce error."""
        config = {
            "stages": ["build"],
            "build": {"stage": "build", "extends": ".missing-template"},
        }
        errors = check_extends(config)
        assert len(errors) == 1
        assert ".missing-template" in errors[0]
        assert "build" in errors[0]

    def test_multiple_extends_all_exist(self):
        """Multiple extends with all templates existing should not produce errors."""
        config = {
            "stages": ["build"],
            ".template-a": {"script": "a"},
            ".template-b": {"script": "b"},
            "build": {"stage": "build", "extends": [".template-a", ".template-b"]},
        }
        errors = check_extends(config)
        assert errors == []

    def test_multiple_extends_one_missing(self):
        """Multiple extends with one missing should produce error for missing."""
        config = {
            "stages": ["build"],
            ".template-a": {"script": "a"},
            "build": {"stage": "build", "extends": [".template-a", ".missing"]},
        }
        errors = check_extends(config)
        assert len(errors) == 1
        assert ".missing" in errors[0]

    def test_extends_regular_job(self):
        """Extending a regular job (not template) is valid in GitLab."""
        config = {
            "stages": ["build", "test"],
            "build": {"stage": "build", "script": "echo"},
            "test": {"stage": "test", "extends": "build"},
        }
        errors = check_extends(config)
        assert errors == []

    def test_no_extends(self):
        """Jobs without extends should not produce errors."""
        config = {
            "stages": ["build"],
            "build": {"stage": "build", "script": "echo"},
        }
        errors = check_extends(config)
        assert errors == []


class TestCheckCircularExtends:
    """Tests for check_circular_extends() function."""

    def test_no_extends(self):
        """Config without extends should not produce errors."""
        config = {
            "stages": ["build"],
            "build": {"stage": "build", "script": "echo"},
        }
        errors = check_circular_extends(config)
        assert errors == []

    def test_simple_chain_no_cycle(self):
        """Simple extends chain without cycle should not produce errors."""
        config = {
            ".base": {"script": "base"},
            ".derived": {"extends": ".base"},
            "build": {"extends": ".derived"},
        }
        errors = check_circular_extends(config)
        assert errors == []

    def test_self_reference(self):
        """Self-extending job should produce circular error."""
        config = {
            "build": {"extends": "build", "script": "echo"},
        }
        errors = check_circular_extends(config)
        assert len(errors) == 1
        assert "circular" in errors[0].lower()
        assert "build" in errors[0]

    def test_two_node_cycle(self):
        """Two-node cycle (A -> B -> A) should produce error."""
        config = {
            ".a": {"extends": ".b"},
            ".b": {"extends": ".a"},
        }
        errors = check_circular_extends(config)
        assert len(errors) >= 1
        assert any("circular" in e.lower() for e in errors)

    def test_three_node_cycle(self):
        """Three-node cycle (A -> B -> C -> A) should produce error."""
        config = {
            ".a": {"extends": ".b"},
            ".b": {"extends": ".c"},
            ".c": {"extends": ".a"},
        }
        errors = check_circular_extends(config)
        assert len(errors) >= 1
        assert any("circular" in e.lower() for e in errors)

    def test_diamond_no_cycle(self):
        """Diamond pattern (A -> B, A -> C, B -> D, C -> D) has no cycle."""
        config = {
            ".d": {"script": "d"},
            ".b": {"extends": ".d"},
            ".c": {"extends": ".d"},
            "a": {"extends": ".b"},  # Would need list extends for true diamond
        }
        errors = check_circular_extends(config)
        assert errors == []
