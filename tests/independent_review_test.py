"""Independent post-freeze regressions. Never edits the supplied helper or study inputs.

Run with python3 -B -m unittest discover -s tests -p '*_test.py'.
The assertions describe corrected behavior, so they expose failures in the original snapshot.
"""

import unittest
from pathlib import Path


HELPER_PATH = Path(__file__).parents[1] / "skills/aiwaterfalls/scripts/check-launch.py"
HELPER = {"__name__": "independent_review_helper", "__file__": str(HELPER_PATH)}
exec(compile(HELPER_PATH.read_text(), str(HELPER_PATH), "exec"), HELPER)

ORIGIN = "https://review-fixture.test"
REPOSITORY = "goodmeasurelabs/review-fixture"
SHA = "c" * 40
VERSION_ID = "11111111-2222-4333-8444-555555555555"


def inputs():
    target = {
        "repository": REPOSITORY,
        "origin": ORIGIN,
        "pr": 17,
        "expected_sha": SHA,
        "cloudflare": {"type": "pages", "account_id": "review-account", "project_name": "review-fixture"},
        "checks": {"robots": True, "canonical": True},
    }
    evidence = {
        "recorded_at": "2026-11-11T20:00:00Z",
        "github": {
            "repository": REPOSITORY,
            "pr": {
                "number": 17,
                "state": "closed",
                "merged": True,
                "merged_at": "2026-11-11T19:00:00Z",
                "merge_commit_sha": SHA,
                "html_url": f"https://github.com/{REPOSITORY}/pull/17",
                "base": {"repo": {"full_name": REPOSITORY}},
            },
            "commit": {"sha": SHA, "html_url": f"https://github.com/{REPOSITORY}/commit/{SHA}"},
        },
        "cloudflare": {
            "type": "pages",
            "account_id": "review-account",
            "project_name": "review-fixture",
            "project": {
                "name": "review-fixture",
                "domains": ["review-fixture.test"],
                "canonical_deployment": {
                    "id": "review-production",
                    "environment": "production",
                    "latest_stage": {"name": "deploy", "status": "success"},
                    "deployment_trigger": {"type": "github:push", "metadata": {"commit_hash": SHA, "commit_dirty": False}},
                },
            },
        },
        "http": [
            {"url": ORIGIN + "/", "status": 200, "headers": {"content-type": "text/html"}, "body": f'<html><head><link rel="canonical" href="{ORIGIN}/"></head><body>Ready.</body></html>'},
            {"url": ORIGIN + "/robots.txt", "status": 200, "headers": {"content-type": "text/plain"}, "body": "User-agent: *\nAllow: /\n"},
        ],
    }
    return target, evidence


def evaluate(target, evidence):
    report = HELPER["assess"](target, evidence)
    return report, {check["id"]: check for check in report["checks"]}


class PostFreezeCounterexamples(unittest.TestCase):
    def test_control_valid_recording_is_verified(self):
        target, evidence = inputs()
        report, _ = evaluate(target, evidence)
        self.assertEqual(report["status"], "verified")

    def test_wrong_requested_pr_cannot_reuse_another_prs_merge(self):
        target, evidence = inputs()
        target["pr"] = 99
        report, checks = evaluate(target, evidence)
        self.assertNotEqual(checks.get("github.identity", checks["github.merge"])["status"], "pass")
        self.assertNotEqual(report["status"], "verified")

    def test_wrong_repository_cannot_reuse_another_repositorys_recording(self):
        target, evidence = inputs()
        target["repository"] = "different-owner/unrelated-repository"
        report, checks = evaluate(target, evidence)
        self.assertNotEqual(checks.get("github.identity", checks["github.revision"])["status"], "pass")
        self.assertNotEqual(report["status"], "verified")

    def test_wrong_pages_project_cannot_reuse_another_projects_production(self):
        target, evidence = inputs()
        target["cloudflare"]["project_name"] = "different-project"
        report, checks = evaluate(target, evidence)
        self.assertNotEqual(checks.get("cloudflare.identity", checks["cloudflare.production"])["status"], "pass")
        self.assertNotEqual(report["status"], "verified")

    def test_successful_build_stage_is_insufficient_for_completed_deployment(self):
        target, evidence = inputs()
        evidence["cloudflare"]["project"]["canonical_deployment"]["latest_stage"] = {"name": "build", "status": "success"}
        report, checks = evaluate(target, evidence)
        self.assertNotEqual(checks["cloudflare.production"]["status"], "pass")
        self.assertNotEqual(report["status"], "verified")

    def test_provider_error_cannot_be_hidden_by_a_stale_success_object(self):
        target, evidence = inputs()
        evidence["cloudflare"]["error"] = {"status": 403, "message": "Current project read denied"}
        report, checks = evaluate(target, evidence)
        self.assertEqual(checks["cloudflare.production"]["status"], "unverified")
        self.assertNotEqual(report["status"], "verified")

    def test_recorded_cross_origin_robots_redirect_is_not_accepted(self):
        target, evidence = inputs()
        robots = evidence["http"][1]
        robots["final_url"] = "https://different-host.test/robots.txt"
        robots["redirects"] = [{"url": robots["url"], "status": 301, "location": robots["final_url"]}]
        report, checks = evaluate(target, evidence)
        self.assertNotEqual(checks["http.robots"]["status"], "pass")
        self.assertNotEqual(report["status"], "verified")

    def test_recorded_robots_redirect_loop_is_not_accepted(self):
        target, evidence = inputs()
        robots = evidence["http"][1]
        robots["final_url"] = robots["url"]
        robots["redirects"] = [{"url": robots["url"], "status": 301, "location": robots["url"]}]
        report, checks = evaluate(target, evidence)
        self.assertNotEqual(checks["http.robots"]["status"], "pass")
        self.assertNotEqual(report["status"], "verified")

    def test_link_in_body_is_not_a_head_canonical(self):
        target, evidence = inputs()
        evidence["http"][0]["body"] = f'<html><head><title>Example</title></head><body><link rel="canonical" href="{ORIGIN}/"></body></html>'
        report, checks = evaluate(target, evidence)
        self.assertNotEqual(checks["html.canonical"]["status"], "pass")
        self.assertNotEqual(report["status"], "verified")

    def test_inert_template_link_is_not_a_document_canonical(self):
        target, evidence = inputs()
        evidence["http"][0]["body"] = f'<html><head><template><link rel="canonical" href="{ORIGIN}/"></template></head><body>Example.</body></html>'
        report, checks = evaluate(target, evidence)
        self.assertNotEqual(checks["html.canonical"]["status"], "pass")
        self.assertNotEqual(report["status"], "verified")

    def test_non_html_media_type_does_not_pass_due_to_a_parameter_substring(self):
        target, evidence = inputs()
        evidence["http"][0]["headers"]["content-type"] = "text/plain; note=html"
        report, checks = evaluate(target, evidence)
        self.assertNotEqual(checks["html.canonical"]["status"], "pass")
        self.assertNotEqual(report["status"], "verified")

    def test_alternate_language_annotation_is_not_a_supported_canonical(self):
        target, evidence = inputs()
        evidence["http"][0]["body"] = f'<html><head><link rel="canonical" href="{ORIGIN}/" hreflang="en"></head><body>Example.</body></html>'
        report, checks = evaluate(target, evidence)
        self.assertNotEqual(checks["html.canonical"]["status"], "pass")
        self.assertNotEqual(report["status"], "verified")

    def test_body_start_closes_an_unclosed_head_before_canonical(self):
        target, evidence = inputs()
        evidence["http"][0]["body"] = f'<html><head><title>Example</title><body><link rel="canonical" href="{ORIGIN}/"></body></html>'
        report, checks = evaluate(target, evidence)
        self.assertNotEqual(checks["html.canonical"]["status"], "pass")
        self.assertNotEqual(report["status"], "verified")

    def test_worker_traffic_without_deployment_timestamp_is_unverified(self):
        target, evidence = inputs()
        target["cloudflare"] = {"type": "workers", "account_id": "review-account", "script_name": "review-fixture", "expected_version_id": VERSION_ID}
        evidence["cloudflare"] = {
            "type": "workers",
            "account_id": "review-account",
            "script_name": "review-fixture",
            "domains": [{"hostname": "review-fixture.test", "service": "review-fixture"}],
            "deployments": [{"id": "unknown-age-deployment", "versions": [{"version_id": VERSION_ID, "percentage": 100}]}],
            "versions": [{"id": VERSION_ID, "annotations": {"workers/tag": SHA}}],
        }
        report, checks = evaluate(target, evidence)
        self.assertEqual(checks["cloudflare.production"]["status"], "unverified")
        self.assertNotEqual(report["status"], "verified")

    def test_explicit_worker_version_pin_still_requires_source_linkage(self):
        target, evidence = inputs()
        target["cloudflare"] = {"type": "workers", "account_id": "review-account", "script_name": "review-fixture", "expected_version_id": VERSION_ID}
        evidence["cloudflare"] = {
            "type": "workers",
            "account_id": "review-account",
            "script_name": "review-fixture",
            "domains": [{"hostname": "review-fixture.test", "service": "review-fixture"}],
            "deployments": [{"id": "selected-deployment", "created_on": "2026-11-11T19:10:00Z", "versions": [{"version_id": VERSION_ID, "percentage": 100}]}],
            "versions": [{"id": VERSION_ID}],
        }
        _, checks = evaluate(target, evidence)
        self.assertEqual(checks["cloudflare.revision"]["status"], "unverified")


if __name__ == "__main__":
    unittest.main(verbosity=2)
