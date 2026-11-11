#!/usr/bin/env python3
"""Read-only release verification. Credentials are never included in receipts."""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$", re.I)
PENDING = {"queued", "pending", "initializing", "active", "building", "idle"}
MAX_BODY = 512_000


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_target(target):
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", target.get("repository", "")):
        raise ValueError("repository must be owner/repo")
    origin = urllib.parse.urlsplit(target.get("origin", ""))
    if (origin.scheme != "https" or not origin.hostname or origin.username or
            origin.password or origin.path not in ("", "/") or origin.query or origin.fragment):
        raise ValueError("origin must be an HTTPS origin without credentials, path, or query")
    if "expected_sha" in target and not SHA.fullmatch(target["expected_sha"]):
        raise ValueError("expected_sha must be a full Git SHA")
    if "pr" in target and (type(target["pr"]) is not int or target["pr"] < 1):
        raise ValueError("pr must be a positive integer")
    for key, value in target.get("checks", {}).items():
        if key not in {"robots", "sitemap", "canonical", "www_redirect", "http_redirect"} or type(value) is not bool:
            raise ValueError("checks must contain supported boolean checks")
    for path in redirect_paths(target):
        parsed = urllib.parse.urlsplit(path)
        if not path.startswith("/") or path.startswith("//") or parsed.netloc or parsed.scheme or parsed.fragment:
            raise ValueError("redirect_paths must be origin-relative paths with optional query")
    statuses = target.get("permanent_redirect_statuses", [301, 308])
    if not isinstance(statuses, list) or not statuses or any(type(status) is not int or status not in (301, 308) for status in statuses):
        raise ValueError("permanent_redirect_statuses must select 301 and/or 308")
    cf = target.get("cloudflare")
    if cf and cf.get("type") not in {"pages", "workers"}:
        raise ValueError("cloudflare.type must be pages or workers")


def redirect_paths(target):
    return target.get("redirect_paths", [target.get("redirect_path", "/aiwaterfalls-check?release=1")])


def home_url(target):
    return target["origin"].rstrip("/") + "/"


def canonical_url(target):
    return target.get("canonical_url", home_url(target))


def normalized_url(url):
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, parts.fragment))


def redirect_probes(target, scheme, www=False):
    origin = urllib.parse.urlsplit(home_url(target))
    host = origin.netloc
    if www:
        host = "www." + host.removeprefix("www.")
    return [(f"{scheme}://{host}{path}", urllib.parse.urljoin(home_url(target), path))
            for path in dict.fromkeys(["/", *redirect_paths(target)])]


class Canonicals(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and "canonical" in (attrs.get("rel") or "").lower().split():
            self.urls.append(attrs.get("href"))


def assess(target, evidence, provenance="provided_evidence"):
    validate_target(target)
    checks = []
    actions = []

    def add(check_id, status, expected, observed, sources, action):
        checks.append(dict(id=check_id, status=status, expected=expected, observed=observed, evidence=sources))
        if status != "pass":
            actions.append(dict(code=check_id, message=action))

    github = evidence.get("github", {})
    pr = github.get("pr") or {}
    merged = pr.get("merged") is True and bool(pr.get("merged_at"))
    if target.get("pr"):
        status = "pass" if merged else "unverified"
        if not merged and pr.get("state") == "open" and pr.get("merged") is False:
            status = "pending"
        elif not merged and pr.get("state") == "closed" and pr.get("merged") is False:
            status = "fail"
        add("github.merge", status, "PR merged", {
            "merged": pr.get("merged"), "merged_at": pr.get("merged_at"), "state": pr.get("state"),
            "error": github.get("error")}, [f"github.pr#{target['pr']}"],
            "Wait for the requested PR to merge, or resolve missing GitHub access before publishing.")
    revision = target.get("expected_sha") or (pr.get("merge_commit_sha") if merged else None)
    if target.get("pr") or target.get("expected_sha"):
        observed_sha = (github.get("commit") or {}).get("sha")
        known_sha = observed_sha or (pr.get("merge_commit_sha") if merged else None)
        status = "unverified"
        if revision and known_sha:
            status = "pass" if revision == known_sha and SHA.fullmatch(revision) else "fail"
        add("github.revision", status, revision or "a confirmed merged revision", known_sha,
            ["github.commit.sha", "github.pr.merge_commit_sha after merge"],
            "Resolve the intended committed revision. An open PR's test merge is insufficient.")

    cf = evidence.get("cloudflare") or {}
    provider = (target.get("cloudflare") or {}).get("type") or cf.get("type")
    if provider == "pages":
        deployment = (cf.get("project") or {}).get("canonical_deployment") or {}
        stage = deployment.get("latest_stage") or {}
        status = "unverified"
        if deployment:
            status = "fail"
            if deployment.get("environment") == "production":
                status = "pass" if stage.get("status") == "success" else "fail"
                if stage.get("status") in PENDING:
                    status = "pending"
        add("cloudflare.production", status, "successful canonical production deployment", {
            "id": deployment.get("id"), "environment": deployment.get("environment"),
            "stage": stage, "error": cf.get("error")}, ["cloudflare.project.canonical_deployment"],
            "Inspect or resume the canonical production deployment. Resolve provider access if unavailable.")
        metadata = (deployment.get("deployment_trigger") or {}).get("metadata") or {}
        actual = metadata.get("commit_hash")
        dirty = metadata.get("commit_dirty")
        status = "unverified"
        if revision and actual:
            status = "fail" if actual != revision or dirty is True else "unverified"
            if actual == revision and dirty is False:
                status = "pass"
        add("cloudflare.revision", status, revision or "confirmed intended revision", {
            "commit_hash": actual, "commit_dirty": dirty, "deployment_id": deployment.get("id")},
            ["cloudflare.project.canonical_deployment.deployment_trigger.metadata"],
            "Compare the active deployment with the intended clean source and its build receipt.")
        domains = (cf.get("project") or {}).get("domains")
        if domains is not None:
            hostname = urllib.parse.urlsplit(home_url(target)).hostname
            add("cloudflare.domain", "pass" if hostname in domains else "fail", hostname, domains,
                ["cloudflare.project.domains"], "Confirm the requested hostname is attached to this project.")
    elif provider == "workers":
        deployments = cf.get("deployments") or []
        active = max(deployments, key=lambda item: item.get("created_on", ""), default={})
        traffic = [item for item in active.get("versions", []) if item.get("percentage", 0) > 0]
        status = "unverified" if not active or not active.get("created_on") else "fail"
        if len(traffic) == 1 and traffic[0].get("percentage") == 100:
            status = "pass"
        add("cloudflare.production", status, "one intended version receiving 100% of traffic", {
            "deployment_id": active.get("id"), "versions": traffic, "error": cf.get("error")},
            ["cloudflare.deployments latest by created_on"],
            "Inspect active Worker traffic and complete the requested rollout if authorized.")
        current_ids = [item.get("version_id") for item in traffic]
        versions = {item.get("id"): item for item in cf.get("versions", [])}
        tags = [(versions.get(item) or {}).get("annotations", {}).get("workers/tag") for item in current_ids]
        expected_version = (target.get("cloudflare") or {}).get("expected_version_id")
        status = "unverified"
        if revision and tags and all(tags):
            status = "pass" if len(tags) == 1 and tags[0] == revision else "fail"
        if expected_version and current_ids != [expected_version]:
            status = "fail" if current_ids else "unverified"
        add("cloudflare.revision", status, {"commit_sha": revision, "version_id": expected_version},
            {"version_ids": current_ids, "source_tags": tags}, ["cloudflare.versions.annotations.workers/tag"],
            "Link the active Worker version to the requested clean source using the deployment receipt.")

    responses = {item.get("url"): item for item in evidence.get("http", [])}

    def response(url):
        item = responses.get(url, {})
        return item, {key.lower(): value for key, value in item.get("headers", {}).items()}

    def resource(check_id, path, predicate, expectation):
        url = urllib.parse.urljoin(home_url(target), path)
        item, headers = response(url)
        status = "unverified" if not item or item.get("error") else "fail"
        if not item.get("error") and item.get("status") == 200 and predicate(item.get("body", ""), headers):
            status = "pass"
        if item.get("truncated"):
            status = "unverified"
        add(check_id, status, expectation, {
            "status": item.get("status"), "content_type": headers.get("content-type"),
            "error": item.get("error"), "url": url, "final_url": item.get("final_url"),
            "redirects": item.get("redirects", [])}, [url],
            f"Fetch and correct {url} against the requested response and content requirements.")

    resource("http.home", "/", lambda body, headers: True, "HTTP 200 over HTTPS")
    wanted = target.get("checks", {})
    if wanted.get("robots"):
        def robots(body, headers):
            lines = [line.split("#", 1)[0].strip() for line in body.splitlines()]
            valid_lines = all(re.match(r"^[\w-]+\s*:", line) for line in lines if line)
            return headers.get("content-type", "").split(";")[0].strip().lower() == "text/plain" and valid_lines and not re.search(r"(?i)<(?:!doctype|html|body)\b", body)
        resource("http.robots", "/robots.txt", robots, "HTTP 200, text/plain, valid robots fields or an empty/comment-only policy")
    if wanted.get("sitemap"):
        def sitemap(body, headers):
            if headers.get("content-type", "").split(";")[0].strip().lower() not in {"application/xml", "text/xml"}:
                return False
            try:
                root = ET.fromstring(body)
            except ET.ParseError:
                return False
            urls = [element.text for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "loc"]
            return root.tag.rsplit("}", 1)[-1] == "urlset" and any(normalized_url(url or "") == normalized_url(canonical_url(target)) for url in urls)
        resource("http.sitemap", "/sitemap.xml", sitemap, f"XML urlset containing {canonical_url(target)}")
    if wanted.get("canonical"):
        item, headers = response(home_url(target))
        parser = Canonicals()
        parser.feed(item.get("body", ""))
        expected = canonical_url(target)
        status = "unverified" if not item or item.get("error") else "fail"
        if not item.get("error") and item.get("status") == 200 and parser.urls == [expected] and "html" in headers.get("content-type", ""):
            status = "pass"
        if item.get("truncated"):
            status = "unverified"
        add("html.canonical", status, expected, parser.urls, [home_url(target)],
            "Set one canonical link in the served HTML to the intended canonical URL.")

    def redirects(check_id, probes):
        observations = []
        statuses = []
        for url, expected in probes:
            item, headers = response(url)
            location = headers.get("location")
            actual = urllib.parse.urljoin(url, location) if location else None
            status = "unverified" if not item or item.get("error") else "fail"
            if not item.get("error") and item.get("status") in target.get("permanent_redirect_statuses", [301, 308]) and actual == expected:
                status = "pass"
            statuses.append(status)
            observations.append(dict(url=url, status=item.get("status"), location=location, expected=expected, error=item.get("error")))
        status = "fail" if "fail" in statuses else "unverified" if "unverified" in statuses else "pass"
        add(check_id, status, {"statuses": target.get("permanent_redirect_statuses", [301, 308]),
                              "destination": "canonical HTTPS hostname preserving path and query"}, observations,
            [url for url, expected in probes], "Correct the permanent redirect and verify both root and path/query probes.")
    if wanted.get("www_redirect"):
        redirects("redirect.www", redirect_probes(target, "https", www=True))
    if wanted.get("http_redirect"):
        redirects("redirect.http", redirect_probes(target, "http"))

    statuses = {item["status"] for item in checks}
    status = "not_ready" if "fail" in statuses else "pending" if "pending" in statuses else "unverified" if "unverified" in statuses else "verified"
    return dict(schema_version=1, status=status, provenance=provenance,
                observed_at=evidence.get("recorded_at"), assessed_at=now(),
                target={key: target[key] for key in ("repository", "origin", "pr", "expected_sha") if key in target},
                checks=checks, next_actions=actions)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_once(url):
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": "AIWaterfalls-LaunchCheck/0.1"})
    try:
        try:
            result = opener.open(request, timeout=15)
        except urllib.error.HTTPError as error:
            result = error
        with result:
            raw = result.read(MAX_BODY + 1)
            return dict(url=url, status=result.code, headers={key.lower(): value for key, value in result.headers.items()
                        if key.lower() in {"content-type", "location"}}, body=raw[:MAX_BODY].decode("utf-8", errors="replace"),
                        truncated=len(raw) > MAX_BODY)
    except (urllib.error.URLError, TimeoutError, OSError):
        return dict(url=url, error="HTTP request unavailable or timed out")


def http_get(url, follow_same_origin=False):
    result = http_once(url)
    if not follow_same_origin:
        return result
    redirects = []
    visited = {url}
    origin = urllib.parse.urlsplit(url)[:2]
    while result.get("status") in (301, 302, 303, 307, 308):
        location = result.get("headers", {}).get("location")
        if not location:
            break
        destination = urllib.parse.urljoin(result["url"], location)
        parsed = urllib.parse.urlsplit(destination)
        if parsed[:2] != origin or parsed.username or parsed.password:
            result["error"] = "Crawl resource redirects outside its HTTPS origin"
            break
        if destination in visited or len(redirects) >= 5:
            result["error"] = "Crawl resource redirect loop or limit"
            break
        redirects.append({"url": result["url"], "status": result["status"], "location": location})
        visited.add(destination)
        result = http_once(destination)
    return {**result, "url": url, "final_url": result["url"], "redirects": redirects}


def gh_read(path):
    try:
        result = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=30, check=False)
        if result.returncode:
            return {"error": "GitHub read unavailable. Check existing gh access."}
        return json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return {"error": "GitHub read unavailable. Check existing gh access."}


def pages_deployment(item):
    if not item:
        return None
    metadata = (item.get("deployment_trigger") or {}).get("metadata") or {}
    return {"id": item.get("id"), "environment": item.get("environment"), "created_on": item.get("created_on"),
            "url": item.get("url"), "latest_stage": item.get("latest_stage"),
            "deployment_trigger": {"metadata": {key: metadata.get(key) for key in ("commit_hash", "commit_dirty", "branch")}}}


def cf_read(path):
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not token:
        return {"error": "CLOUDFLARE_API_TOKEN unavailable"}
    req = urllib.request.Request("https://api.cloudflare.com/client/v4/" + path,
                                 headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=30) as result:
            body = json.load(result)
        return body.get("result") if body.get("success") else {"error": "Cloudflare API read unsuccessful"}
    except urllib.error.HTTPError as error:
        return {"error": f"Cloudflare HTTP {error.code}"}
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return {"error": "Cloudflare read unavailable"}


def collect(target):
    validate_target(target)
    evidence = dict(recorded_at=now(), github={}, http=[])
    github = evidence["github"]
    if target.get("pr"):
        pr = gh_read(f"repos/{target['repository']}/pulls/{target['pr']}")
        github["pr"] = {key: pr.get(key) for key in ("state", "merged", "merged_at", "merge_commit_sha")}
        if pr.get("error"):
            github["error"] = pr["error"]
    if target.get("expected_sha"):
        commit = gh_read(f"repos/{target['repository']}/commits/{target['expected_sha']}")
        github["commit"] = {"sha": commit.get("sha")}
        if commit.get("error"):
            github["error"] = commit["error"]
    cf = target.get("cloudflare")
    if cf:
        identifier = cf.get("project_name") if cf["type"] == "pages" else cf.get("script_name")
        if not cf.get("account_id") or not identifier:
            raise ValueError("live Cloudflare checks need account_id and project_name or script_name")
        account = urllib.parse.quote(cf["account_id"], safe="")
        name = urllib.parse.quote(identifier, safe="")
        evidence["cloudflare"] = {"type": cf["type"]}
        result = evidence["cloudflare"]
        if cf["type"] == "pages":
            project = cf_read(f"accounts/{account}/pages/projects/{name}")
            result["project"] = {"domains": project.get("domains"), "canonical_deployment": pages_deployment(project.get("canonical_deployment"))}
            if project.get("error"):
                result["error"] = project["error"]
        else:
            deployments = cf_read(f"accounts/{account}/workers/scripts/{name}/deployments")
            if isinstance(deployments, dict) and deployments.get("error"):
                result["error"] = deployments["error"]
            else:
                items = deployments.get("deployments", []) if isinstance(deployments, dict) else deployments
                result["deployments"] = [{key: item.get(key) for key in ("id", "created_on", "versions")} for item in items]
                active = max(result["deployments"], key=lambda item: item.get("created_on") or "", default={})
                result["versions"] = []
                for entry in active.get("versions") or []:
                    version_id = entry["version_id"]
                    version = cf_read(f"accounts/{account}/workers/scripts/{name}/versions/{urllib.parse.quote(version_id, safe='')}")
                    result["versions"].append({"id": version_id, "annotations": version.get("annotations", {})})
    wanted = target.get("checks", {})
    urls = [home_url(target)]
    urls.extend(urllib.parse.urljoin(home_url(target), path) for key, path in (("robots", "/robots.txt"), ("sitemap", "/sitemap.xml")) if wanted.get(key))
    if wanted.get("www_redirect"):
        urls.extend(url for url, expected in redirect_probes(target, "https", www=True))
    if wanted.get("http_redirect"):
        urls.extend(url for url, expected in redirect_probes(target, "http"))
    resource_urls = {urllib.parse.urljoin(home_url(target), path) for path in ("/robots.txt", "/sitemap.xml")}
    evidence["http"] = [http_get(url, follow_same_origin=url in resource_urls) for url in dict.fromkeys(urls)]
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--evidence")
    parser.add_argument("--out")
    parser.add_argument("--save-evidence")
    args = parser.parse_args()
    try:
        target = json.loads(Path(args.target).read_text())
        evidence = collect(target) if args.live else json.loads(Path(args.evidence).read_text())
        report = assess(target, evidence, "live_collection" if args.live else "provided_evidence")
        if args.save_evidence:
            if not args.live:
                raise ValueError("--save-evidence requires --live")
            Path(args.save_evidence).write_text(json.dumps(evidence, indent=2) + "\n")
        output = json.dumps(report, indent=2) + "\n"
        if args.out:
            Path(args.out).write_text(output)
        else:
            print(output, end="")
        return 0 if report["status"] == "verified" else 2
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as error:
        print(f"Invalid input or unavailable file: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
