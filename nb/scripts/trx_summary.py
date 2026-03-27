#!/usr/bin/env python3

import argparse
import json
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Summarize TRX test results, write GitHub outputs, and optionally notify Teams."
    )
    parser.add_argument("--input-dir", required=True, help="Directory containing .trx files.")
    parser.add_argument("--environment", required=True, help="Environment label for the report.")
    parser.add_argument("--exit-code", required=True, help="Exit code from the test process.")
    parser.add_argument("--duration-seconds", default="", help="Test duration in seconds.")
    parser.add_argument("--duration-minutes", default="", help="Test duration in minutes.")
    parser.add_argument("--github-output", default="", help="Path to the GitHub outputs file.")
    parser.add_argument("--step-summary", default="", help="Path to the GitHub step summary file.")
    parser.add_argument("--teams-webhook-url", default="", help="Microsoft Teams webhook URL.")
    parser.add_argument("--run-url", default="", help="GitHub Actions run URL.")
    parser.add_argument("--repo", default="", help="Repository name.")
    parser.add_argument("--branch", default="", help="Branch name.")
    return parser.parse_args()


def get_namespace(tag):
    if tag.startswith("{") and "}" in tag:
        return tag[1 : tag.index("}")]
    return ""


def qname(namespace, name):
    return f"{{{namespace}}}{name}" if namespace else name


def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_trx_counts(input_dir):
    totals = {
        "trx_files": 0,
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "timeouts": 0,
    }

    for trx_file in sorted(Path(input_dir).rglob("*.trx")):
        try:
            tree = ET.parse(trx_file)
            root = tree.getroot()
            namespace = get_namespace(root.tag)
            counters = root.find(f".//{qname(namespace, 'Counters')}")

            totals["trx_files"] += 1

            if counters is not None:
                totals["total"] += parse_int(counters.get("total"))
                totals["passed"] += parse_int(counters.get("passed"))
                totals["failed"] += parse_int(counters.get("failed"))
                totals["skipped"] += parse_int(counters.get("notExecuted")) + parse_int(counters.get("skipped"))
                totals["errors"] += parse_int(counters.get("error"))
                totals["timeouts"] += parse_int(counters.get("timeout"))
                continue

            for item in root.findall(f".//{qname(namespace, 'UnitTestResult')}"):
                outcome = (item.get("outcome") or "").strip().lower()
                totals["total"] += 1
                if outcome == "passed":
                    totals["passed"] += 1
                elif outcome in {"failed", "error", "timeout"}:
                    totals["failed"] += 1
                elif outcome in {"notexecuted", "skipped"}:
                    totals["skipped"] += 1
        except ET.ParseError as exc:
            print(f"Warning: failed to parse {trx_file}: {exc}", file=sys.stderr)

    totals["failed"] += totals["errors"] + totals["timeouts"]
    return totals


def format_status(tests_failed):
    return "FAILED" if tests_failed else "PASSED"


def write_github_output(path, data):
    if not path:
        return

    with open(path, "a", encoding="utf-8") as handle:
        for key, value in data.items():
            handle.write(f"{key}={value}\n")


def append_step_summary(path, summary_lines):
    if not path:
        return

    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(summary_lines) + "\n")


def build_teams_payload(args, counts, tests_failed):
    status = format_status(tests_failed)
    theme_color = "A30200" if tests_failed else "2EB886"

    facts = [
        {"name": "Environment", "value": args.environment},
        {"name": "Repo", "value": args.repo or "unknown"},
        {"name": "Branch", "value": args.branch or "unknown"},
        {"name": "Duration (min)", "value": args.duration_minutes or "unknown"},
        {"name": "Total Tests", "value": str(counts["total"])},
        {"name": "Passed", "value": str(counts["passed"])},
        {"name": "Failed", "value": str(counts["failed"])},
        {"name": "Skipped", "value": str(counts["skipped"])},
        {"name": "Run", "value": args.run_url or "unavailable"},
    ]

    return {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "summary": f"NightlyBilling {args.environment} Test Report",
        "themeColor": theme_color,
        "title": f"NightlyBilling Automation Test Results ({status})",
        "sections": [{"facts": facts}],
    }


def post_to_teams(webhook_url, payload):
    if not webhook_url:
        print("No Teams webhook configured; skipping notification.")
        return

    request = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            print(f"Teams notification sent (HTTP {response.status}).")
    except urllib.error.URLError as exc:
        print(f"Warning: failed to send Teams notification: {exc}", file=sys.stderr)


def main():
    args = parse_args()
    exit_code = parse_int(args.exit_code)
    counts = parse_trx_counts(args.input_dir)
    tests_failed = counts["failed"] > 0 or exit_code != 0
    status = format_status(tests_failed)

    output_data = {
        "tests_failed": str(tests_failed).lower(),
        "total": counts["total"],
        "passed": counts["passed"],
        "failed": counts["failed"],
        "skipped": counts["skipped"],
        "trx_files": counts["trx_files"],
        "status": status,
    }
    write_github_output(args.github_output, output_data)

    summary_lines = [
        f"## {args.environment} Test Summary",
        "",
        f"- Status: **{status}**",
        f"- Duration (min): {args.duration_minutes or 'unknown'}",
        f"- Total: {counts['total']}",
        f"- Passed: {counts['passed']}",
        f"- Failed: {counts['failed']}",
        f"- Skipped: {counts['skipped']}",
        f"- TRX Files: {counts['trx_files']}",
    ]
    if args.run_url:
        summary_lines.append(f"- Run: {args.run_url}")
    append_step_summary(args.step_summary, summary_lines)

    post_to_teams(args.teams_webhook_url, build_teams_payload(args, counts, tests_failed))


if __name__ == "__main__":
    main()
