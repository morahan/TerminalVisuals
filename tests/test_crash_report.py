import json
import tempfile
import unittest
from pathlib import Path

from src.crash_report import (
    CrashReporter,
    crash_reporting_consent_state,
    request_crash_reporting_consent,
)


class FakeTTY:
    def __init__(self, answer: str):
        self.answer = answer

    def isatty(self) -> bool:
        return True

    def readline(self) -> str:
        return self.answer


class FakeOutput:
    def __init__(self):
        self.value = ""

    def write(self, value: str) -> None:
        self.value += value

    def flush(self) -> None:
        pass


class FakeGithubReporter(CrashReporter):
    def __init__(self, *, existing=None, **kwargs):
        super().__init__(**kwargs)
        self.existing = existing
        self.requests = []

    def _github_request(self, method, path, payload=None):
        self.requests.append((method, path, payload))
        if method == "GET":
            return self.existing or []
        if path.endswith("/comments"):
            return {"html_url": "https://github.example/comment"}
        return {"html_url": "https://github.example/issue/1", "number": 1}


def make_exception():
    try:
        raise ValueError("boom")
    except ValueError as exc:
        return (type(exc), exc, exc.__traceback__)


class CrashReporterTests(unittest.TestCase):
    def test_local_report_is_written_with_stable_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            reporter = CrashReporter(report_dir=tmp)
            context = {"mode": "waves", "terminal": {"columns": 80, "rows": 24}}

            first = reporter.report_exception(make_exception(), context)
            second = reporter.report_exception(make_exception(), context)

            self.assertIsNotNone(first.path)
            self.assertTrue(first.path.exists())
            self.assertEqual(first.fingerprint, second.fingerprint)

            data = json.loads(first.path.read_text(encoding="utf-8"))
            self.assertEqual(data["exception"]["type"], "ValueError")
            self.assertEqual(data["context"]["mode"], "waves")

    def test_github_reporting_waits_for_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            reporter = FakeGithubReporter(
                enabled=True,
                report_dir=tmp,
                github_repo="owner/repo",
                github_token="token",
                github_opt_in=False,
            )

            result = reporter.report_exception(make_exception(), {"mode": "waves"})

            self.assertEqual(result.github_status, "awaiting_opt_in")
            self.assertEqual(reporter.requests, [])

    def test_github_reporting_creates_issue_after_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            reporter = FakeGithubReporter(
                enabled=True,
                report_dir=tmp,
                github_repo="owner/repo",
                github_token="token",
                github_opt_in=True,
            )

            result = reporter.report_exception(make_exception(), {"mode": "waves"})

            self.assertEqual(result.github_status, "reported")
            self.assertEqual(result.github_url, "https://github.example/issue/1")
            self.assertEqual(reporter.requests[0][0], "GET")
            self.assertEqual(reporter.requests[1][0], "POST")
            self.assertTrue(reporter.requests[1][1].endswith("/issues"))

    def test_consent_prompt_records_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "consent.json"
            output = FakeOutput()

            accepted = request_crash_reporting_consent(
                input_stream=FakeTTY("yes\n"),
                output_stream=output,
                path=path,
            )

            self.assertTrue(accepted)
            self.assertTrue(crash_reporting_consent_state(path))
            self.assertIn("Freio Labs, LLC", output.value)
            self.assertIn("submit a PR", output.value)

    def test_consent_prompt_records_decline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "consent.json"

            accepted = request_crash_reporting_consent(
                input_stream=FakeTTY("\n"),
                output_stream=FakeOutput(),
                path=path,
            )

            self.assertFalse(accepted)
            self.assertFalse(crash_reporting_consent_state(path))


if __name__ == "__main__":
    unittest.main()
