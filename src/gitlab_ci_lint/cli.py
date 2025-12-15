import click
import json
import os
from typing import List
from rich.console import Console
from rich.table import Table
from .linter import GitLabCILinter

console = Console()


@click.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def cli(files, format):
    """Validate GitLab CI/CD configuration files."""
    linter = GitLabCILinter()
    has_errors = False
    results = {}

    for file_path in files:
        errors = linter.lint_file(file_path)
        results[file_path] = errors
        if errors:
            has_errors = True

    if format == "json":
        click.echo(json.dumps(results, indent=2))
    else:
        for file_path, errors in results.items():
            if not errors:
                console.print(f"[green]✓ {file_path} is valid[/green]")
            else:
                console.print(f"[red]✗ {file_path} has {len(errors)} errors:[/red]")
                for err in errors:
                    console.print(f"  - {err}")
                console.print("")  # spacing

    if has_errors:
        raise click.Abort()


if __name__ == "__main__":
    cli()
