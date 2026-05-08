from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
POLICY_VERSION = 1
SETTINGS_FILENAME = "settings.json"
LEGACY_CONSENT_FILENAME = "crash-reporting-consent.json"


@dataclass
class AppSettings:
    schema_version: int = SCHEMA_VERSION
    crash_reporting_opt_in: bool | None = None
    crash_reporting_policy_version: int = POLICY_VERSION
    locked_mode: str | None = None
    locked_sliders: dict[str, float | int] = field(default_factory=dict)
    updated_at: str | None = None
    checksum: str = ""
    corrupt: bool = False

    def to_payload(self, *, include_checksum: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "crash_reporting_opt_in": self.crash_reporting_opt_in,
            "crash_reporting_policy_version": self.crash_reporting_policy_version,
            "locked_mode": self.locked_mode,
            "locked_sliders": dict(self.locked_sliders),
            "updated_at": self.updated_at,
        }
        if include_checksum:
            payload["checksum"] = self.checksum
        return payload

    @property
    def crash_reporting_enabled(self) -> bool:
        return self.crash_reporting_opt_in is True


def default_config_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "freio"
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "freio"
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "freio"
    return Path.home() / ".config" / "freio"


def settings_file_path(path: str | Path | None = None) -> Path:
    return Path(path) if path else default_config_dir() / SETTINGS_FILENAME


def legacy_consent_file_path(path: str | Path | None = None) -> Path:
    return Path(path) if path else default_config_dir() / LEGACY_CONSENT_FILENAME


def load_settings(
    path: str | Path | None = None,
    *,
    legacy_path: str | Path | None = None,
) -> AppSettings:
    settings_path = settings_file_path(path)
    should_migrate_legacy = path is None or legacy_path is not None
    try:
        raw = settings_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if should_migrate_legacy:
            return _migrate_legacy_settings(settings_path, legacy_path)
        return AppSettings()
    except OSError:
        return AppSettings(corrupt=True)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return AppSettings(corrupt=True)

    settings = _settings_from_payload(payload)
    if settings is None or not _checksum_matches(payload):
        return AppSettings(corrupt=True)
    return settings


def save_settings(settings: AppSettings, path: str | Path | None = None) -> AppSettings:
    settings_path = settings_file_path(path)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    clean = AppSettings(
        crash_reporting_opt_in=settings.crash_reporting_opt_in,
        crash_reporting_policy_version=settings.crash_reporting_policy_version,
        locked_mode=settings.locked_mode,
        locked_sliders=_clean_slider_values(settings.locked_sliders),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    clean.checksum = _settings_checksum(clean.to_payload(include_checksum=False))

    tmp_path = settings_path.with_name(f"{settings_path.name}.tmp")
    tmp_path.write_text(json.dumps(clean.to_payload(), indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(settings_path)
    return clean


def save_crash_reporting_opt_in(
    accepted: bool,
    path: str | Path | None = None,
) -> AppSettings:
    settings = load_settings(path)
    settings.crash_reporting_opt_in = bool(accepted)
    settings.crash_reporting_policy_version = POLICY_VERSION
    return save_settings(settings, path)


def save_locked_animation(
    mode: str,
    sliders: dict[str, float | int],
    path: str | Path | None = None,
) -> AppSettings:
    settings = load_settings(path)
    settings.locked_mode = mode
    settings.locked_sliders = _clean_slider_values(sliders)
    return save_settings(settings, path)


def clear_locked_animation(path: str | Path | None = None) -> AppSettings:
    settings = load_settings(path)
    settings.locked_mode = None
    settings.locked_sliders = {}
    return save_settings(settings, path)


def crash_reporting_state_requires_consent(
    settings: AppSettings,
    *,
    reporting: str = "auto",
) -> bool:
    if reporting.lower() == "off" or os.environ.get("FREIO_CRASH_REPORTING", "").lower() == "off":
        return False
    if settings.crash_reporting_policy_version != POLICY_VERSION:
        return True
    return settings.crash_reporting_opt_in is not True


def _migrate_legacy_settings(
    settings_path: Path,
    legacy_path: str | Path | None,
) -> AppSettings:
    state = _legacy_crash_reporting_state(legacy_consent_file_path(legacy_path))
    if state is None:
        return AppSettings()
    migrated = AppSettings(crash_reporting_opt_in=state)
    return save_settings(migrated, settings_path)


def _legacy_crash_reporting_state(path: Path) -> bool | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if payload.get("policy_version") != POLICY_VERSION:
        return None
    return bool(payload.get("accepted"))


def _settings_from_payload(payload: Any) -> AppSettings | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != SCHEMA_VERSION:
        return None
    if payload.get("crash_reporting_policy_version") != POLICY_VERSION:
        return None

    opt_in = payload.get("crash_reporting_opt_in")
    if opt_in is not None and not isinstance(opt_in, bool):
        return None

    locked_mode = payload.get("locked_mode")
    if locked_mode is not None and not isinstance(locked_mode, str):
        return None

    locked_sliders = payload.get("locked_sliders")
    if not isinstance(locked_sliders, dict):
        return None

    updated_at = payload.get("updated_at")
    if updated_at is not None and not isinstance(updated_at, str):
        return None

    checksum = payload.get("checksum")
    if not isinstance(checksum, str) or not checksum:
        return None

    return AppSettings(
        crash_reporting_opt_in=opt_in,
        crash_reporting_policy_version=POLICY_VERSION,
        locked_mode=locked_mode,
        locked_sliders=_clean_slider_values(locked_sliders),
        updated_at=updated_at,
        checksum=checksum,
    )


def _checksum_matches(payload: dict[str, Any]) -> bool:
    checksum = payload.get("checksum")
    if not isinstance(checksum, str):
        return False
    stable_payload = {key: value for key, value in payload.items() if key != "checksum"}
    expected = _settings_checksum(stable_payload)
    return checksum == expected


def _settings_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(b"freio-settings-v1:" + encoded).hexdigest()


def _clean_slider_values(values: dict[str, Any]) -> dict[str, float | int]:
    clean: dict[str, float | int] = {}
    for key, value in values.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            clean[key] = value
        elif isinstance(value, float):
            clean[key] = value
    return clean
