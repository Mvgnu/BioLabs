"""Governance lifecycle CLI package."""

# purpose: expose typer application entrypoint for governance migrations
# status: pilot
# depends_on: backend.app.cli.migrate_templates

from .migrate_templates import app  # noqa: F401
