"""Release metadata tests for the Vent-Axia Svara integration."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "custom_components" / "svara_vent_axia_ble" / "manifest.json"
HACS_PATH = REPO_ROOT / "hacs.json"
README_PATH = REPO_ROOT / "README.md"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifest_has_release_version_and_codeowners() -> None:
    """The integration manifest should be release-ready for HACS."""
    manifest = _load_json(MANIFEST_PATH)

    assert manifest["domain"] == "svara_vent_axia_ble"
    assert manifest["version"] == "1.0.3"
    assert manifest["codeowners"] == ["@dfanica"]


def test_hacs_metadata_matches_release_expectations() -> None:
    """The HACS manifest should expose supported release metadata."""
    hacs = _load_json(HACS_PATH)

    assert hacs["name"] == "Vent-Axia Svara BLE"
    assert hacs["homeassistant"] == "2024.5.0"
    assert hacs["country"] == ["GB", "IE"]


def test_readme_title_matches_release_name() -> None:
    """Public-facing naming should be consistent across release files."""
    first_line = README_PATH.read_text(encoding="utf-8").splitlines()[0]

    assert first_line == "# Vent-Axia Svara BLE"
