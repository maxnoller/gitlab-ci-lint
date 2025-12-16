"""Integration tests for schema loading and caching."""

from gitlab_ci_lint.schema import load_schema


class TestSchemaLoading:
    """Tests for schema loading functionality."""

    def test_schema_loads_successfully(self):
        """Schema should load without errors."""
        schema = load_schema()
        assert schema is not None
        assert isinstance(schema, dict)

    def test_schema_has_expected_structure(self):
        """Schema should have expected JSON Schema structure."""
        schema = load_schema()
        # JSON Schema should have a type or $schema
        assert "$schema" in schema or "type" in schema or "definitions" in schema

    def test_schema_is_cached(self):
        """Schema loading should use LRU cache (same object returned)."""
        schema1 = load_schema()
        schema2 = load_schema()
        assert schema1 is schema2  # Same object due to caching

    def test_schema_has_job_definitions(self):
        """Schema should have job-related definitions."""
        schema = load_schema()
        # The GitLab CI schema typically has definitions for jobs
        # This is a sanity check that we loaded the right schema
        assert "definitions" in schema or "properties" in schema or "$defs" in schema
