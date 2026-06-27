#!/usr/bin/env python3
"""Local wrapper for the shared read-only TDC helper."""

from runpy import run_path


run_path(
    "/mnt/d/Dev/enterprise-agents-system/.claude/scripts/delivery/tdc_next.py",
    run_name="__main__",
)
