#!/usr/bin/env python3
"""Read-only fleet health snapshot. Requires authenticated gh and curl; no app execution."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
import sys


def command(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr.strip()[:500]}")
    return result.stdout


def gh(endpoint):
    return json.loads(command("gh", "api", endpoint))


def web(url):
    return command("curl", "--fail", "--silent", "--show-error", "--location",
                   "--proto", "=https", "--proto-redir", "=https", "--max-time", "30", url)


def workflow_status(runs, commit, now, maximum_age):
    # A pass on an older commit, or an older retry, cannot mask the current run.
    current = [r for r in runs if r.get("head_sha") == commit
               and r.get("event") in ("push", "schedule", "workflow_dispatch")]
    if not current:
        return "missing", None
    latest = max(current, key=lambda r: (r["run_number"], r.get("run_attempt", 1)))
    if latest.get("status") != "completed":
        return "pending", latest
    if latest.get("conclusion") != "success":
        return "failed", latest
    finished = dt.datetime.fromisoformat(latest["updated_at"].replace("Z", "+00:00"))
    if now - finished > dt.timedelta(days=maximum_age):
        return "stale", latest
    return "passed", latest


def catalog_errors(catalog, projects):
    if not isinstance(catalog, dict) or not isinstance(catalog.get("tools"), list):
        return ["Catalog is not a tools object"]
    tools = catalog["tools"]
    if not all(isinstance(t, dict) and isinstance(t.get("id"), str) for t in tools):
        return ["Malformed catalog entry"]
    actual = [t["id"] for t in tools]
    expected = {p["id"] for p in projects if p["tool"]}
    errors = []
    if len(actual) != len(set(actual)):
        errors.append("Duplicate tools in catalog")
    if set(actual) != expected:
        errors.append(f"Maintenance inventory differs from website: added={sorted(set(actual)-expected)}, missing={sorted(expected-set(actual))}")
    return errors


def collect(config):
    now = dt.datetime.now(dt.timezone.utc)
    report = {"checkedAt": now.isoformat(), "projects": [], "site": {}, "attention": []}
    for project in config["projects"]:
        record = {"id": project["id"], "repository": project["repository"], "checks": []}
        report["projects"].append(record)
        try:
            repo = project["repository"]
            commit = gh(f"repos/{repo}/commits/main")["sha"]
            record["commit"] = commit
            for workflow in project["workflows"]:
                runs = gh(f"repos/{repo}/actions/workflows/{workflow}/runs?branch=main&per_page=30")["workflow_runs"]
                status, run = workflow_status(runs, commit, now, config["maximumCheckAgeDays"])
                record["checks"].append({"workflow": workflow, "status": status,
                                         "url": run["html_url"] if run else None})
                if status != "passed":
                    report["attention"].append(f"{project['id']}: {workflow} {status}")
            issues = gh(f"repos/{repo}/issues?state=open&sort=updated&per_page=20")
            record["recentOpenItems"] = [{"number": i["number"], "title": i["title"], "url": i["html_url"],
                                           "updatedAt": i["updated_at"]} for i in issues]
        except (RuntimeError, subprocess.TimeoutExpired, ValueError, KeyError) as error:
            record["error"] = str(error)
            report["attention"].append(f"{project['id']}: health check unavailable")
    try:
        catalog = json.loads(web(config["catalogUrl"]))
        report["attention"].extend(catalog_errors(catalog, config["projects"]))
        # Routes are constructed from the trusted inventory, not response-provided URLs.
        for project in config["projects"]:
            if project["tool"]:
                slug = project["id"]
                if not re.fullmatch(r"[a-z0-9-]+", slug):
                    raise ValueError("Unsafe tool id")
                for suffix in ("", "/help"):
                    url = f"https://www.blake.ist/tools/{slug}{suffix}"
                    body = web(url)
                    if "<h1" not in body.lower() or len(body) < 500:
                        report["attention"].append(f"Unexpected page content: {url}")
                    report["site"][url] = {"reachable": True, "bytes": len(body.encode())}
    except (RuntimeError, subprocess.TimeoutExpired, ValueError, KeyError) as error:
        report["site"]["error"] = str(error)
        report["attention"].append("Website health check failed")
    report["status"] = "attention" if report["attention"] else "passed"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", default=str(Path(__file__).parent / "maintenance/projects.json"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = collect(json.loads(Path(args.inventory).read_text()))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "attention": report["attention"], "report": str(output)}))
    return 1 if report["attention"] else 0


if __name__ == "__main__":
    sys.exit(main())
