"""
Template utilities for rendering Jinja2 templates across the testsuite.

This module provides centralized template management with templates organized
in the testsuite/templates/ directory.
"""

from pathlib import Path
from jinja2 import (
    Environment,
    FileSystemLoader,
    select_autoescape,
    Template,
    TemplateNotFound,
    TemplateSyntaxError,
    UndefinedError,
)

# Base template directory
TEMPLATE_DIR = Path(__file__).parent / "templates"


def get_environment() -> Environment:
    """
    Get a configured Jinja2 Environment for the template directory.

    Returns:
        Configured Jinja2 Environment instance
    """
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def get_template(path: str) -> Template:
    """
    Load a template by relative path from testsuite/templates/.

    Args:
        path: Template path relative to templates/ directory
              (e.g., 'reporting/launch_description.txt.j2')

    Returns:
        Jinja2 Template instance

    Example:
        >>> template = get_template('reporting/launch_description.txt.j2')
        >>> output = template.render(cluster_count=2, clusters={...})
    """
    env = get_environment()
    return env.get_template(path)


def render_template(path: str, context: dict) -> str:
    """
    Render a template with the given context data.

    Args:
        path: Template path relative to templates/ directory
              (e.g., 'reporting/launch_description.txt.j2')
        context: Dictionary of variables to pass to the template

    Returns:
        Rendered template as string

    Example:
        >>> output = render_template(
        ...     'reporting/launch_description.txt.j2',
        ...     {'cluster_count': 2, 'clusters': {...}}
        ... )
    """
    template = get_template(path)
    return template.render(context)


if __name__ == "__main__":
    import sys
    import yaml

    if len(sys.argv) != 3:
        print("Usage: python -m testsuite.template_utils <template_path> <yaml_file>", file=sys.stderr)
        print("", file=sys.stderr)
        print("Example:", file=sys.stderr)
        print("  python -m testsuite.template_utils reporting/launch_description.txt.j2 data.yaml", file=sys.stderr)
        print("", file=sys.stderr)
        print("Template path is relative to testsuite/templates/", file=sys.stderr)
        sys.exit(1)

    template_path = sys.argv[1]
    yaml_file = sys.argv[2]

    try:
        with open(yaml_file, "r", encoding="utf-8") as f:
            context = yaml.safe_load(f)
    except FileNotFoundError as e:
        print(f"Error: YAML file not found: {e}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML syntax: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        output = render_template(template_path, context)
        print(output, end="")
    except TemplateNotFound as e:
        print(f"Error: Template not found: {e}", file=sys.stderr)
        print(f"  Looking in: {TEMPLATE_DIR}", file=sys.stderr)
        sys.exit(1)
    except TemplateSyntaxError as e:
        print(f"Error: Invalid template syntax at line {e.lineno}: {e.message}", file=sys.stderr)
        sys.exit(1)
    except UndefinedError as e:
        print(f"Error: Missing or undefined variable in template: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error: Unexpected error rendering template: {e}", file=sys.stderr)
        sys.exit(1)
