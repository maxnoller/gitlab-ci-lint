import yaml
import jsonschema
from typing import List, Dict, Any
from .schema import load_schema
from .semantic import check_needs, check_stages, check_extends, check_circular_extends


class GitLabCILinter:
    def __init__(self):
        self.schema = load_schema()

    def lint(self, content: str) -> List[str]:
        """Lint the provided YAML content and return a list of error messages."""
        errors = []

        # 1. YAML Parsing
        try:
            config = yaml.safe_load(content)
        except yaml.YAMLError as e:
            return [f"YAML parsing error: {str(e)}"]

        if not config or not isinstance(config, dict):
            # empty file or valid yaml but not a dict
            return ["Invalid configuration: File is empty or not a dictionary"]

        # 2. Schema Validation
        try:
            jsonschema.validate(instance=config, schema=self.schema)
        except jsonschema.ValidationError as e:
            # Create a more readable error path
            path = ".".join(str(p) for p in e.path)
            error_msg = (
                f"Schema error at '{path}': {e.message}"
                if path
                else f"Schema error: {e.message}"
            )
            errors.append(error_msg)
            # We continue to find semantic errors if possible, but often schema errors make structure invalid

        # 3. Semantic Checks
        # Only run if basic structure is presumably okay (parsed as dict)
        if isinstance(config, dict):
            errors.extend(check_needs(config))
            errors.extend(check_stages(config))
            errors.extend(check_extends(config))
            errors.extend(check_circular_extends(config))

        return errors

    def lint_file(self, path: str) -> List[str]:
        """Lint a file from disk."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return self.lint(content)
        except Exception as e:
            return [f"Could not read file '{path}': {str(e)}"]
