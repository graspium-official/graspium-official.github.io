#!/usr/bin/env python3
"""Validate _data/*.yml files for RoboReview."""

import sys
import yaml
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "_data"

errors = []


def error(msg):
    errors.append(msg)
    print(f"  ERROR: {msg}")


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate():
    print("Validating data files...\n")

    # Load data files
    papers = load_yaml(DATA / "papers.yml")
    tags = load_yaml(DATA / "tags.yml")
    members = load_yaml(DATA / "members.yml")

    # Build lookup sets
    valid_fields = {f["key"] for f in tags["fields"]}
    valid_members = {m["name"] for m in members}

    print(f"[tags.yml] {len(valid_fields)} fields, {len(tags.get('known_venues', []))} known venues")
    print(f"[members.yml] {len(valid_members)} members")
    print(f"[papers.yml] {len(papers)} papers\n")

    # Validate papers
    required_fields = ["id", "title", "authors", "venue", "date", "field", "keywords", "presenter", "status"]
    valid_statuses = {"reviewed", "upcoming", "cancelled", "candidate"}
    seen_ids = set()

    for i, paper in enumerate(papers):
        prefix = f"Paper #{i+1}"
        pid = paper.get("id", f"(index {i})")

        # Check required fields
        for field in required_fields:
            if field not in paper or paper[field] is None:
                error(f"{prefix} [{pid}]: missing required field '{field}'")

        # Check duplicate IDs
        if pid in seen_ids:
            error(f"{prefix} [{pid}]: duplicate id '{pid}'")
        seen_ids.add(pid)

        # Check field value
        if "field" in paper and paper["field"] not in valid_fields:
            error(f"{prefix} [{pid}]: field '{paper['field']}' not in tags.yml (valid: {valid_fields})")

        # Check presenter
        presenter = paper.get("presenter", "")
        if presenter and presenter != "TBD" and presenter not in valid_members:
            error(f"{prefix} [{pid}]: presenter '{presenter}' not in members.yml")

        # Check status
        status = paper.get("status", "")
        if status and status not in valid_statuses:
            error(f"{prefix} [{pid}]: invalid status '{status}' (valid: {valid_statuses})")

        # Check date format
        date_str = paper.get("date", "")
        if date_str:
            try:
                datetime.strptime(str(date_str), "%Y-%m-%d")
            except ValueError:
                error(f"{prefix} [{pid}]: invalid date format '{date_str}' (expected YYYY-MM-DD)")

        # Check keywords is a list
        keywords = paper.get("keywords", [])
        if not isinstance(keywords, list):
            error(f"{prefix} [{pid}]: keywords should be a list")
        elif len(keywords) < 1:
            error(f"{prefix} [{pid}]: should have at least 1 keyword")

    # Summary
    print()
    if errors:
        print(f"FAILED: {len(errors)} error(s) found.")
        return 1
    else:
        print("PASSED: All validations passed.")
        return 0


if __name__ == "__main__":
    sys.exit(validate())
