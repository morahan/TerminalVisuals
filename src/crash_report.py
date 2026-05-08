from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Any
from urllib import error, parse, request


DEFAULT_REPORTING = "auto"
GITHUB_LABELS = ["crash", "automated-report"]
POLICY_VERSION = 1
PRIVACY_NOTICE = """Freio Labs, LLC crash reporting notice

Freio can save crash logs and draft them for submission as GitHub issues so
the developers and agents maintaining the app can diagnose terminal crashes.
Crash logs may include the active visualization mode, terminal size, Python and
OS details, command-line arguments, and a traceback. Freio redacts your home
directory and GitHub token before writing or submitting a report.

If GitHub reporting is configured, enabling crash reporting lets Freio create
or update a GitHub issue with the crash details. You can opt out by answering
no here, passing --crash-reporting off, or setting FREIO_CRASH_REPORTING=off.

If you are feeling generous, submit a PR with a fix! :-)
"""


@dataclass(frozen=True)
class CrashReportResult:
    path: Path | None
    fingerprint: str | None
    github_url: str | None = None
    github_status: str = "disabled"
    error: str | None = None


class CrashReporter:
    def __init__(
        self,
        *,
        enabled: bool = True,
        report_dir: str | Path | None = None,
        github_repo: str | None = None,
        github_token: str | None = None,
        github_opt_in: bool = False,
        timeout: float = 4.0,
    ):
        self.enabled = enabled
        self.report_dir = Path(report_dir) if report_dir else default_report_dir()
        self.github_repo = github_repo
        self.github_token = github_token
        self.github_opt_in = github_opt_in
        self.timeout = timeout

    @classmethod
    def from_environment(
        cls,
        *,
        reporting: str = DEFAULT_REPORTING,
        report_dir: str | Path | None = None,
        github_opt_in: bool = False,
    ) -> "CrashReporter":
        env_reporting = os.environ.get("FREIO_CRASH_REPORTING")
        if env_reporting:
            reporting = env_reporting
        env_report_dir = os.environ.get("FREIO_CRASH_REPORT_DIR")
        enabled = reporting.lower() != "off"
        return cls(
            enabled=enabled,
            report_dir=report_dir or env_report_dir,
            github_repo=os.environ.get("FREIO_GITHUB_REPO"),
            github_token=os.environ.get("FREIO_GITHUB_TOKEN"),
            github_opt_in=github_opt_in,
        )

    def report_exception(
        self,
        exc_info: tuple[type[BaseException], BaseException, TracebackType | None],
        context: dict[str, Any],
    ) -> CrashReportResult:
        if not self.enabled:
            return CrashReportResult(path=None, fingerprint=None, github_status="disabled")

        report = self._build_report(exc_info, context)
        path = self._write_local_report(report)
        github_url = None
        github_status = "not_configured"
        github_error = None

        if self.github_repo and self.github_token and self.github_opt_in:
            try:
                github_url = self._create_or_update_github_issue(report)
                github_status = "reported"
            except Exception as exc:  # noqa: BLE001 - reporting must never crash the app
                github_status = "failed"
                github_error = str(exc)
        elif self.github_repo and self.github_token:
            github_status = "awaiting_opt_in"

        return CrashReportResult(
            path=path,
            fingerprint=report["fingerprint"],
            github_url=github_url,
            github_status=github_status,
            error=github_error,
        )

    def _build_report(
        self,
        exc_info: tuple[type[BaseException], BaseException, TracebackType | None],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        exc_type, exc, tb = exc_info
        formatted = "".join(traceback.format_exception(exc_type, exc, tb))
        frames = traceback.extract_tb(tb) if tb else []
        fingerprint = self._fingerprint(exc_type, exc, frames, context)

        return {
            "schema": 1,
            "app": "freio",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "fingerprint": fingerprint,
            "exception": {
                "type": exc_type.__name__,
                "message": self._redact_text(str(exc)),
                "traceback": self._redact_text(formatted),
            },
            "context": context,
            "runtime": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "executable": self._redact_text(sys.executable),
                "argv": [self._redact_text(arg) for arg in sys.argv],
                "env": {
                    key: self._redact_text(os.environ[key])
                    for key in ("TERM", "TERM_PROGRAM", "COLORTERM")
                    if key in os.environ
                },
            },
        }

    def _fingerprint(
        self,
        exc_type: type[BaseException],
        exc: BaseException,
        frames: traceback.StackSummary,
        context: dict[str, Any],
    ) -> str:
        top = frames[-1] if frames else None
        payload = {
            "mode": context.get("mode"),
            "type": exc_type.__name__,
            "message": str(exc),
            "file": Path(top.filename).name if top else None,
            "function": top.name if top else None,
            "line": (top.line or "").strip() if top else None,
        }
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8", "replace")
        return hashlib.sha256(encoded).hexdigest()[:12]

    def _write_local_report(self, report: dict[str, Any]) -> Path:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.report_dir / f"freio-crash-{stamp}-{report['fingerprint']}.json"
        path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def _create_or_update_github_issue(self, report: dict[str, Any]) -> str:
        repo = _clean_github_repo(self.github_repo)
        marker = f"[freio-crash:{report['fingerprint']}]"
        title = f"{marker} {report['exception']['type']} in {report['context'].get('mode', 'unknown')}"
        existing = self._find_github_issue(repo, marker)
        body = self._github_body(report)

        if existing:
            self._github_request(
                "POST",
                f"/repos/{repo}/issues/{existing['number']}/comments",
                {"body": body},
            )
            return str(existing.get("html_url", ""))

        issue_payload = {"title": title, "body": body, "labels": GITHUB_LABELS}
        try:
            issue = self._github_request("POST", f"/repos/{repo}/issues", issue_payload)
        except RuntimeError as exc:
            if "422" not in str(exc):
                raise
            issue = self._github_request(
                "POST",
                f"/repos/{repo}/issues",
                {"title": title, "body": body},
            )
        return str(issue.get("html_url", ""))

    def _find_github_issue(self, repo: str, marker: str) -> dict[str, Any] | None:
        query = parse.urlencode(
            {"state": "open", "labels": ",".join(GITHUB_LABELS), "per_page": "100"}
        )
        issues = self._github_request("GET", f"/repos/{repo}/issues?{query}")
        for issue in issues:
            if "pull_request" in issue:
                continue
            if marker in issue.get("title", ""):
                return issue
        return None

    def _github_body(self, report: dict[str, Any]) -> str:
        summary = {
            "fingerprint": report["fingerprint"],
            "created_at": report["created_at"],
            "context": report["context"],
            "runtime": report["runtime"],
            "exception": {
                "type": report["exception"]["type"],
                "message": report["exception"]["message"],
                "traceback": report["exception"]["traceback"][-4000:],
            },
        }
        payload = json.dumps(summary, indent=2, sort_keys=True)
        if len(payload) > 6000:
            payload = payload[:6000] + "\n... truncated ..."
        return (
            "Automated Freio crash report.\n\n"
            "```json\n"
            f"{payload}\n"
            "```\n"
        )

    def _github_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        if not self.github_token:
            raise RuntimeError("missing GitHub token")
        url = path if path.startswith("https://") else f"https://api.github.com{path}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("Authorization", f"Bearer {self.github_token}")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if data is not None:
            req.add_header("Content-Type", "application/json")

        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"GitHub API {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"GitHub API unavailable: {exc.reason}") from exc

        if not raw:
            return None
        return json.loads(raw)

    def _redact_text(self, value: str) -> str:
        home = str(Path.home())
        if home and home in value:
            value = value.replace(home, "~")
        token = self.github_token
        if token and token in value:
            value = value.replace(token, "<redacted>")
        return value


def default_report_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "freio" / "crashes"
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "freio" / "crashes"
    base = os.environ.get("XDG_CACHE_HOME")
    if base:
        return Path(base) / "freio" / "crashes"
    return Path.home() / ".cache" / "freio" / "crashes"


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


def consent_file_path() -> Path:
    return default_config_dir() / "crash-reporting-consent.json"


def has_crash_reporting_consent(path: str | Path | None = None) -> bool:
    return crash_reporting_consent_state(path) is True


def crash_reporting_consent_state(path: str | Path | None = None) -> bool | None:
    consent_path = Path(path) if path else consent_file_path()
    try:
        data = json.loads(consent_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if data.get("policy_version") != POLICY_VERSION:
        return None
    return bool(data.get("accepted"))


def store_crash_reporting_consent(
    accepted: bool,
    path: str | Path | None = None,
) -> None:
    consent_path = Path(path) if path else consent_file_path()
    consent_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "accepted": bool(accepted),
        "accepted_at": datetime.now(timezone.utc).isoformat() if accepted else None,
        "policy_version": POLICY_VERSION,
        "company": "Freio Labs, LLC",
    }
    consent_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def request_crash_reporting_consent(
    *,
    reporting: str = DEFAULT_REPORTING,
    input_stream: Any = None,
    output_stream: Any = None,
    path: str | Path | None = None,
) -> bool:
    if reporting.lower() == "off" or os.environ.get("FREIO_CRASH_REPORTING", "").lower() == "off":
        return False
    state = crash_reporting_consent_state(path)
    if state is not None:
        return state

    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stderr
    if not getattr(input_stream, "isatty", lambda: False)():
        return False

    output_stream.write(PRIVACY_NOTICE)
    output_stream.write("\nEnable GitHub crash issue submission for Freio? [y/N]: ")
    output_stream.flush()
    answer = input_stream.readline().strip().lower()
    accepted = answer in {"y", "yes"}
    store_crash_reporting_consent(accepted, path)
    return accepted


def _clean_github_repo(repo: str | None) -> str:
    if not repo or "/" not in repo:
        raise RuntimeError("FREIO_GITHUB_REPO must be in owner/repo form")
    owner, name = repo.split("/", 1)
    if not owner or not name or "/" in name:
        raise RuntimeError("FREIO_GITHUB_REPO must be in owner/repo form")
    return f"{owner}/{name}"
