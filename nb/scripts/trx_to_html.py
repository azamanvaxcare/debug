#!/usr/bin/env python3

import argparse
import html
from pathlib import Path
import xml.etree.ElementTree as ET


def parse_args():
    parser = argparse.ArgumentParser(description="Convert TRX test results to HTML.")
    parser.add_argument("--input-dir", required=True, help="Directory containing .trx files.")
    parser.add_argument("--output-file", required=True, help="Path to the output HTML file.")
    parser.add_argument("--title", default="Test Report", help="Report title.")
    return parser.parse_args()


def get_namespace(tag):
    if tag.startswith("{") and "}" in tag:
        return tag[1 : tag.index("}")]
    return ""


def qname(namespace, name):
    return f"{{{namespace}}}{name}" if namespace else name


def text_or_empty(value):
    return html.escape(value or "")


def load_trx_report(path):
    tree = ET.parse(path)
    root = tree.getroot()
    namespace = get_namespace(root.tag)

    counters = root.find(f".//{qname(namespace, 'Counters')}")
    summary = {
        "total": counters.get("total", "0") if counters is not None else "0",
        "executed": counters.get("executed", "0") if counters is not None else "0",
        "passed": counters.get("passed", "0") if counters is not None else "0",
        "failed": counters.get("failed", "0") if counters is not None else "0",
        "error": counters.get("error", "0") if counters is not None else "0",
        "timeout": counters.get("timeout", "0") if counters is not None else "0",
    }

    results = []
    for item in root.findall(f".//{qname(namespace, 'UnitTestResult')}"):
        output = item.find(qname(namespace, "Output"))
        error_info = output.find(qname(namespace, "ErrorInfo")) if output is not None else None
        message = ""
        stack_trace = ""

        if error_info is not None:
            message = error_info.findtext(qname(namespace, "Message"), default="")
            stack_trace = error_info.findtext(qname(namespace, "StackTrace"), default="")

        results.append(
            {
                "test_name": item.get("testName", ""),
                "outcome": item.get("outcome", "Unknown"),
                "duration": item.get("duration", ""),
                "start_time": item.get("startTime", ""),
                "end_time": item.get("endTime", ""),
                "message": message,
                "stack_trace": stack_trace,
            }
        )

    results.sort(key=lambda row: (row["outcome"] != "Failed", row["test_name"].lower()))
    return summary, results


def build_html(title, reports):
    if not reports:
        body = """
        <section class="card">
          <h2>No TRX files found</h2>
          <p>The test run did not produce any <code>.trx</code> files.</p>
        </section>
        """
    else:
        sections = []
        for report_name, summary, results in reports:
            rows = []
            for result in results:
                outcome_class = result["outcome"].lower()
                details = ""
                if result["message"] or result["stack_trace"]:
                    details = (
                        "<details><summary>Failure details</summary>"
                        f"<pre>{text_or_empty(result['message'])}\n{text_or_empty(result['stack_trace'])}</pre>"
                        "</details>"
                    )

                rows.append(
                    f"""
                    <tr class="{text_or_empty(outcome_class)}">
                      <td>{text_or_empty(result["test_name"])}</td>
                      <td>{text_or_empty(result["outcome"])}</td>
                      <td>{text_or_empty(result["duration"])}</td>
                      <td>{text_or_empty(result["start_time"])}</td>
                      <td>{text_or_empty(result["end_time"])}</td>
                      <td>{details}</td>
                    </tr>
                    """
                )

            sections.append(
                f"""
                <section class="card">
                  <h2>{text_or_empty(report_name)}</h2>
                  <div class="summary">
                    <div><strong>Total</strong><span>{text_or_empty(summary["total"])}</span></div>
                    <div><strong>Executed</strong><span>{text_or_empty(summary["executed"])}</span></div>
                    <div><strong>Passed</strong><span>{text_or_empty(summary["passed"])}</span></div>
                    <div><strong>Failed</strong><span>{text_or_empty(summary["failed"])}</span></div>
                    <div><strong>Error</strong><span>{text_or_empty(summary["error"])}</span></div>
                    <div><strong>Timeout</strong><span>{text_or_empty(summary["timeout"])}</span></div>
                  </div>
                  <table>
                    <thead>
                      <tr>
                        <th>Test</th>
                        <th>Outcome</th>
                        <th>Duration</th>
                        <th>Start</th>
                        <th>End</th>
                        <th>Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {"".join(rows) if rows else '<tr><td colspan="6">No test rows found.</td></tr>'}
                    </tbody>
                  </table>
                </section>
                """
            )

        body = "".join(sections)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{text_or_empty(title)}</title>
  <style>
    body {{
      background: #0f172a;
      color: #e2e8f0;
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 24px;
    }}
    h1, h2 {{
      margin-top: 0;
    }}
    .card {{
      background: #111827;
      border: 1px solid #334155;
      border-radius: 12px;
      margin-bottom: 24px;
      padding: 20px;
    }}
    .summary {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      margin: 16px 0 20px;
    }}
    .summary div {{
      background: #1e293b;
      border-radius: 8px;
      padding: 12px;
    }}
    .summary strong, .summary span {{
      display: block;
    }}
    .summary span {{
      font-size: 24px;
      margin-top: 4px;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
    }}
    th, td {{
      border-bottom: 1px solid #334155;
      padding: 10px;
      text-align: left;
      vertical-align: top;
    }}
    tr.passed td {{
      background: rgba(22, 163, 74, 0.12);
    }}
    tr.failed td, tr.error td {{
      background: rgba(220, 38, 38, 0.14);
    }}
    tr.warning td, tr.timeout td {{
      background: rgba(245, 158, 11, 0.14);
    }}
    code, pre {{
      background: #020617;
      border-radius: 6px;
      padding: 2px 6px;
    }}
    pre {{
      overflow-x: auto;
      padding: 12px;
      white-space: pre-wrap;
    }}
    a {{
      color: #93c5fd;
    }}
  </style>
</head>
<body>
  <h1>{text_or_empty(title)}</h1>
  {body}
</body>
</html>
"""


def main():
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_file = Path(args.output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    reports = []
    for trx_file in sorted(input_dir.rglob("*.trx")):
        summary, results = load_trx_report(trx_file)
        reports.append((trx_file.name, summary, results))

    html_content = build_html(args.title, reports)
    output_file.write_text(html_content, encoding="utf-8")
    print(f"Wrote HTML report to {output_file}")


if __name__ == "__main__":
    main()
