"""Regression tests for release decisions, independent of model assessments."""
import copy
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "skills/aiwaterfalls/scripts/check-launch.py"
spec = importlib.util.spec_from_file_location("check_launch", SCRIPT)
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)
REVISION = "1234567890abcdef1234567890abcdef12345678"


def fixture():
    target = {"repository": "example/site", "origin": "https://example.com", "pr": 7,
              "checks": {"robots": True, "sitemap": True, "canonical": True,
                         "www_redirect": True, "http_redirect": True}}
    evidence = {
        "recorded_at": "2026-11-11T12:00:00Z",
        "github": {"pr": {"state": "closed", "merged": True, "merged_at": "2026-11-11T11:00:00Z", "merge_commit_sha": REVISION}},
        "cloudflare": {"type": "pages", "project": {"domains": ["example.com"], "canonical_deployment": {
            "id": "production", "environment": "production", "latest_stage": {"status": "success"},
            "deployment_trigger": {"metadata": {"commit_hash": REVISION, "commit_dirty": False}}}}},
        "http": [
            {"url": "https://example.com/", "status": 200, "headers": {"Content-Type": "text/html"},
             "body": '<!-- <link rel="canonical" href="https://bad.example/"> --><link rel=canonical href="https://example.com/">'},
            {"url": "https://example.com/robots.txt", "status": 200, "headers": {"content-type": "text/plain; charset=utf-8"}, "body": "User-agent: *\nAllow: /"},
            {"url": "https://example.com/sitemap.xml", "status": 200, "headers": {"content-type": "application/xml"}, "body": '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/</loc></url></urlset>'}
        ]}
    for scheme, www in (("https", True), ("http", False)):
        for url, expected in launch.redirect_probes(target, scheme, www):
            evidence["http"].append({"url": url, "status": 301, "headers": {"location": expected}})
    return target, evidence


class LaunchChecks(unittest.TestCase):
    def check(self, target, evidence, check_id):
        return next(item for item in launch.assess(target, evidence)["checks"] if item["id"] == check_id)

    def test_verified_observations_keep_recording_time(self):
        target, evidence = fixture()
        report = launch.assess(target, evidence)
        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["observed_at"], evidence["recorded_at"])
        self.assertEqual(report["provenance"], "provided_evidence")

    def test_open_pr_sha_is_not_a_release(self):
        target, evidence = fixture()
        evidence["github"]["pr"].update(state="open", merged=False, merged_at=None)
        self.assertEqual(self.check(target, evidence, "github.merge")["status"], "pending")
        self.assertEqual(self.check(target, evidence, "cloudflare.revision")["status"], "unverified")
        self.assertEqual(launch.assess(target, evidence)["status"], "pending")

    def test_canonical_production_wins_over_preview_and_old_success(self):
        target, evidence = fixture()
        production = evidence["cloudflare"]["project"]["canonical_deployment"]
        old = copy.deepcopy(production)
        production["latest_stage"]["status"] = "failure"
        evidence["cloudflare"]["deployments"] = [old]
        self.assertEqual(self.check(target, evidence, "cloudflare.production")["status"], "fail")

    def test_matching_sha_does_not_clear_dirty_build(self):
        target, evidence = fixture()
        evidence["cloudflare"]["project"]["canonical_deployment"]["deployment_trigger"]["metadata"]["commit_dirty"] = True
        self.assertEqual(self.check(target, evidence, "cloudflare.revision")["status"], "fail")

    def test_html_spa_robots_and_malformed_xml_fail(self):
        target, evidence = fixture()
        evidence["http"][1].update(headers={"content-type": "text/html"}, body="<html>User-agent: *\nAllow: /</html>")
        evidence["http"][2]["body"] = '<urlset><url><loc>https://example.com/</loc></urlset>'
        self.assertEqual(self.check(target, evidence, "http.robots")["status"], "fail")
        self.assertEqual(self.check(target, evidence, "http.sitemap")["status"], "fail")

    def test_nested_redirect_must_preserve_query(self):
        target, evidence = fixture()
        evidence["http"][4]["headers"]["location"] = "https://example.com/"
        self.assertEqual(self.check(target, evidence, "redirect.www")["status"], "fail")

    def test_missing_api_access_is_unknown(self):
        target, evidence = fixture()
        evidence["cloudflare"] = {"type": "pages", "error": "Cloudflare HTTP 403"}
        self.assertEqual(launch.assess(target, evidence)["status"], "unverified")
        self.assertEqual(self.check(target, evidence, "cloudflare.production")["status"], "unverified")

    def test_worker_split_traffic_is_not_complete(self):
        target, evidence = fixture()
        evidence["cloudflare"] = {"type": "workers", "deployments": [{"id": "active", "created_on": "2026-11-11T12:00:00Z", "versions": [
            {"version_id": "v1", "percentage": 50}, {"version_id": "v2", "percentage": 50}]}], "versions": [
            {"id": "v1", "annotations": {"workers/tag": REVISION}},
            {"id": "v2", "annotations": {"workers/tag": "a" * 40}}]}
        self.assertEqual(self.check(target, evidence, "cloudflare.production")["status"], "fail")
        self.assertEqual(self.check(target, evidence, "cloudflare.revision")["status"], "fail")

    def test_no_worker_source_link_is_unknown(self):
        target, evidence = fixture()
        evidence["cloudflare"] = {"type": "workers", "deployments": [{"id": "active", "created_on": "2026-11-11T12:00:00Z", "versions": [
            {"version_id": "v1", "percentage": 100}]}], "versions": [{"id": "v1", "annotations": {}}]}
        self.assertEqual(self.check(target, evidence, "cloudflare.production")["status"], "pass")
        self.assertEqual(self.check(target, evidence, "cloudflare.revision")["status"], "unverified")

    def test_input_cannot_change_trusted_api_host(self):
        target, evidence = fixture()
        target["repository"] = "owner/repo/../../other"
        with self.assertRaises(ValueError):
            launch.assess(target, evidence)

    def test_sitemap_only_robots_is_valid(self):
        target, evidence = fixture()
        evidence["http"][1]["body"] = "# Public website\nSitemap: https://example.com/sitemap.xml\n"
        self.assertEqual(self.check(target, evidence, "http.robots")["status"], "pass")

    def test_permanent_308_can_be_selected_or_excluded(self):
        target, evidence = fixture()
        evidence["http"][3]["status"] = 308
        self.assertEqual(self.check(target, evidence, "redirect.www")["status"], "pass")
        target["permanent_redirect_statuses"] = [301]
        self.assertEqual(self.check(target, evidence, "redirect.www")["status"], "fail")

    def test_sitemap_redirect_is_collected_with_its_chain(self):
        url = "https://example.com/sitemap.xml"
        destination = "https://example.com/api/sitemap"
        observations = {url: {"url": url, "status": 308, "headers": {"location": "/api/sitemap"}},
                        destination: {"url": destination, "status": 200, "headers": {"content-type": "application/xml"}, "body": "<urlset/>"}}
        with patch.object(launch, "http_once", side_effect=lambda address: observations[address]):
            result = launch.http_get(url, follow_same_origin=True)
        self.assertEqual(result["url"], url)
        self.assertEqual(result["final_url"], destination)
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["redirects"][0]["status"], 308)

    def test_crawl_redirect_never_transmits_to_another_origin(self):
        url = "https://example.com/sitemap.xml"
        with patch.object(launch, "http_once", return_value={"url": url, "status": 302, "headers": {"location": "https://other.example/sitemap"}}) as request:
            result = launch.http_get(url, follow_same_origin=True)
        self.assertEqual(request.call_count, 1)
        self.assertIn("outside", result["error"])

    def test_equivalent_empty_root_path_in_sitemap(self):
        target, evidence = fixture()
        target["canonical_url"] = "https://example.com"
        self.assertEqual(self.check(target, evidence, "http.sitemap")["status"], "pass")


if __name__ == "__main__":
    unittest.main()
