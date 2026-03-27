#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse TRX results and emit HTML/GitHub summaries.")
    parser.add_argument("--trx", required=True, help="Path to the TRX file.")
    parser.add_argument("--html", required=True, help="Path to write the HTML summary.")
    parser.add_argument("--github-output", help="GitHub output file path.")
    parser.add_argument("--github-step-summary", help="GitHub step summary file path.")
    parser.add_argument("--test-exit-code", default="0", help="Exit code returned by dotnet test.")
    parser.add_argument("--duration-seconds", default="0", help="Test duration in seconds.")
    parser.add_argument("--duration-minutes", default="0", help="Test duration in minutes.")
    parser.add_argument("--environment", default="", help="Environment label for summaries.")
    parser.add_argument("--repo", default="", help="Repository name.")
    parser.add_argument("--branch", default="", help="Branch or ref name.")
    parser.add_argument("--run-url", default="", help="Workflow run URL.")
    return parser.parse_args()


def text_or_default(value: str | None, default: str = "unknown") -> str:
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def safe_int(value: str | None, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def find_child(root: ET.Element, tag_name: str) -> ET.Element | None:
    for element in root.iter():
        if element.tag.endswith(tag_name):
            return element
    return None


def findall(root: ET.Element, tag_name: str) -> list[ET.Element]:
    return [element for element in root.iter() if element.tag.endswith(tag_name)]


def parse_trx(trx_path: Path) -> dict[str, object]:
    totals = {
        "total": "unknown",
        "passed": "unknown",
        "failed": "unknown",
        "skipped": "unknown",
    }
    failed_tests: list[dict[str, str]] = []
    executed_tests: list[dict[str, str]] = []
    outcome = "Unknown"

    if not trx_path.is_file():
        return {
            **totals,
            "outcome": outcome,
            "failed_tests": failed_tests,
            "executed_tests": executed_tests,
            "trx_found": False,
        }

    tree = ET.parse(trx_path)
    root = tree.getroot()

    counters = find_child(root, "Counters")
    if counters is not None:
        totals["total"] = text_or_default(counters.attrib.get("total"))
        totals["passed"] = text_or_default(counters.attrib.get("passed"))
        failed_count = (
            safe_int(counters.attrib.get("failed"))
            + safe_int(counters.attrib.get("error"))
            + safe_int(counters.attrib.get("timeout"))
            + safe_int(counters.attrib.get("aborted"))
        )
        skipped_count = (
            safe_int(counters.attrib.get("notExecuted"))
            + safe_int(counters.attrib.get("notRunnable"))
            + safe_int(counters.attrib.get("disconnected"))
            + safe_int(counters.attrib.get("warning"))
            + safe_int(counters.attrib.get("inconclusive"))
        )
        totals["failed"] = str(failed_count)
        totals["skipped"] = str(skipped_count)

    result_summary = find_child(root, "ResultSummary")
    if result_summary is not None:
        outcome = text_or_default(result_summary.attrib.get("outcome"), "Unknown")

    if totals["total"] == "unknown":
        results = findall(root, "UnitTestResult")
        total_count = len(results)
        passed_count = sum(1 for item in results if item.attrib.get("outcome") == "Passed")
        failed_count = sum(1 for item in results if item.attrib.get("outcome") == "Failed")
        skipped_count = sum(1 for item in results if item.attrib.get("outcome") in {"NotExecuted", "Skipped"})
        totals["total"] = str(total_count)
        totals["passed"] = str(passed_count)
        totals["failed"] = str(failed_count)
        totals["skipped"] = str(skipped_count)

    for result in findall(root, "UnitTestResult"):
        test_name = text_or_default(result.attrib.get("testName"), "Unnamed test")
        test_outcome = text_or_default(result.attrib.get("outcome"), "Unknown")
        test_duration = text_or_default(result.attrib.get("duration"), "")
        executed_tests.append(
            {
                "name": test_name,
                "outcome": test_outcome,
                "duration": test_duration,
            }
        )

        if test_outcome != "Failed":
            continue
        message = ""
        stack_trace = ""
        output = find_child(result, "Output")
        if output is not None:
            error_info = find_child(output, "ErrorInfo")
            if error_info is not None:
                message = text_or_default(
                    (find_child(error_info, "Message").text if find_child(error_info, "Message") is not None else ""),
                    "",
                )
                stack_trace = text_or_default(
                    (find_child(error_info, "StackTrace").text if find_child(error_info, "StackTrace") is not None else ""),
                    "",
                )
        failed_tests.append(
            {
                "name": test_name,
                "message": message,
                "stack_trace": stack_trace,
            }
        )

    return {
        **totals,
        "outcome": outcome,
        "failed_tests": failed_tests,
        "executed_tests": executed_tests,
        "trx_found": True,
    }


def build_markdown_summary(data: dict[str, object], args: argparse.Namespace, status: str) -> str:
    lines = [
        "## HL7 Unit Test Summary",
        "",
        f"- Status: **{status}**",
        f"- Environment: {args.environment or 'unknown'}",
        f"- Duration (min): {args.duration_minutes}",
        f"- Duration (sec): {args.duration_seconds}",
        f"- Total: {data['total']}",
        f"- Passed: {data['passed']}",
        f"- Failed: {data['failed']}",
        f"- Skipped: {data['skipped']}",
        f"- TRX found: {'yes' if data['trx_found'] else 'no'}",
    ]
    if args.run_url:
        lines.append(f"- Run: {args.run_url}")
    if data["failed_tests"]:
        lines.extend(["", "### Failed Tests", ""])
        for failed in data["failed_tests"][:10]:
            lines.append(f"- `{failed['name']}`: {failed['message'] or 'No error message captured.'}")
        remaining = len(data["failed_tests"]) - 10
        if remaining > 0:
            lines.append(f"- ... and {remaining} more failed test(s).")
    return "\n".join(lines) + "\n"


def build_html_report(data: dict[str, object], args: argparse.Namespace, status: str) -> str:
    executed_rows = []
    for test in data["executed_tests"]:
        executed_rows.append(
            "<tr>"
            f"<td>{html.escape(test['name'])}</td>"
            f"<td>{html.escape(test['outcome'])}</td>"
            f"<td>{html.escape(test['duration'] or '-')}</td>"
            "</tr>"
        )

    failed_rows = []
    for failed in data["failed_tests"]:
        failed_rows.append(
            "<tr>"
            f"<td>{html.escape(failed['name'])}</td>"
            f"<td><pre>{html.escape(failed['message'] or 'No error message captured.')}</pre></td>"
            f"<td><pre>{html.escape(failed['stack_trace'] or '')}</pre></td>"
            "</tr>"
        )

    failed_table = (
        "<h2>Failed Tests</h2>"
        "<table><thead><tr><th>Name</th><th>Message</th><th>Stack Trace</th></tr></thead>"
        f"<tbody>{''.join(failed_rows)}</tbody></table>"
        if failed_rows
        else "<h2>Failed Tests</h2><p>No failed tests recorded.</p>"
    )

    executed_table = (
        "<h2>Executed Tests</h2>"
        "<table><thead><tr><th>Name</th><th>Outcome</th><th>Duration</th></tr></thead>"
        f"<tbody>{''.join(executed_rows)}</tbody></table>"
        if executed_rows
        else "<h2>Executed Tests</h2><p>No executed tests were found in the TRX file.</p>"
    )

    run_link = (
        f'<p><strong>Run:</strong> <a href="{html.escape(args.run_url)}">{html.escape(args.run_url)}</a></p>'
        if args.run_url
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>HL7 Unit Test Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2937; }}
    h1, h2 {{ color: #111827; }}
    .status {{ font-weight: bold; color: {"#b91c1c" if status == "FAILED" else "#047857"}; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; vertical-align: top; text-align: left; }}
    th {{ background: #f3f4f6; }}
    pre {{ white-space: pre-wrap; margin: 0; font-family: Consolas, monospace; }}
    .facts td:first-child {{ font-weight: bold; width: 220px; }}
  </style>
</head>
<body>
  <h1>HL7 Unit Test Report</h1>
  <p class="status">Status: {html.escape(status)}</p>
  <table class="facts">
    <tbody>
      <tr><td>Environment</td><td>{html.escape(args.environment or "unknown")}</td></tr>
      <tr><td>Repository</td><td>{html.escape(args.repo or "unknown")}</td></tr>
      <tr><td>Branch</td><td>{html.escape(args.branch or "unknown")}</td></tr>
      <tr><td>Duration (min)</td><td>{html.escape(args.duration_minutes)}</td></tr>
      <tr><td>Duration (sec)</td><td>{html.escape(args.duration_seconds)}</td></tr>
      <tr><td>Total</td><td>{html.escape(str(data["total"]))}</td></tr>
      <tr><td>Passed</td><td>{html.escape(str(data["passed"]))}</td></tr>
      <tr><td>Failed</td><td>{html.escape(str(data["failed"]))}</td></tr>
      <tr><td>Skipped</td><td>{html.escape(str(data["skipped"]))}</td></tr>
      <tr><td>TRX Found</td><td>{"yes" if data["trx_found"] else "no"}</td></tr>
    </tbody>
  </table>
  {run_link}
  {executed_table}
  {failed_table}
</body>
</html>
"""


def append_file(path_value: str | None, content: str) -> None:
    if not path_value:
        return
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(content)


def append_outputs(path_value: str | None, output_values: dict[str, str]) -> None:
    if not path_value:
        return
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for key, value in output_values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    args = parse_args()
    trx_path = Path(args.trx)
    html_path = Path(args.html)
    html_path.parent.mkdir(parents=True, exist_ok=True)

    data = parse_trx(trx_path)
    failed_count = safe_int(str(data["failed"]), 0) if str(data["failed"]).isdigit() else 0
    raw_exit_code = args.test_exit_code.strip()
    test_exit_code = safe_int(raw_exit_code, 0 if raw_exit_code == "" else 1)
    status = "FAILED" if test_exit_code != 0 or failed_count > 0 else "PASSED"

    html_path.write_text(build_html_report(data, args, status), encoding="utf-8")

    summary = build_markdown_summary(data, args, status)
    append_file(args.github_step_summary, summary)

    append_outputs(
        args.github_output,
        {
            "TESTS_FAILED": "true" if status == "FAILED" else "false",
            "STATUS": status,
            "TOTAL": str(data["total"]),
            "PASSED": str(data["passed"]),
            "FAILED": str(data["failed"]),
            "SKIPPED": str(data["skipped"]),
            "TRX_FOUND": "true" if data["trx_found"] else "false",
            "HTML_REPORT": str(html_path),
            "TRX_PATH": str(trx_path),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
