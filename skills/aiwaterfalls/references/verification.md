# Verification helper

Requires Python 3.10+ and its standard library only. All operations are read-only.

## Target

```json
{
  "repository": "owner/repo",
  "origin": "https://example.com",
  "pr": 2,
  "expected_sha": "0123456789abcdef0123456789abcdef01234567",
  "cloudflare": {
    "type": "pages",
    "account_id": "existing-account-id",
    "project_name": "existing-project-name"
  },
  "checks": {
    "robots": true,
    "sitemap": true,
    "canonical": true,
    "www_redirect": true,
    "http_redirect": true
  }
}
```

`repository` and HTTPS `origin` are required. `pr` adds a merge prerequisite. `expected_sha`
pins the intended revision; otherwise a merged PR supplies it. `cloudflare` selects Pages
(`project_name`) or Workers (`script_name`, optional `expected_version_id`). Omit it when the
task only concerns HTTP behavior. `canonical_url` optionally overrides the homepage canonical.
Requested booleans default to false. Permanent redirects accept 301 or 308 by default.
Set `permanent_redirect_statuses: [301]` when the task explicitly requires 301. The homepage is always checked. Set `redirect_paths` to an array of safe application paths/queries when desired.
The default is `["/aiwaterfalls-check?release=1"]`.

Live mode uses `gh api` and `CLOUDFLARE_API_TOKEN`. GitHub and Cloudflare requests go only to
their official API hosts. `--save-evidence <file>` stores sanitized observations for replay.
Missing credentials and HTTP errors produce explicit unverified checks. Retries never mutate.

## Recorded observations

Every arm of an evaluation should receive the same evidence and target. Only the installed
skill set changes. A recorded observation cannot establish a site's current state.

```json
{
  "recorded_at": "2026-11-11T12:00:00Z",
  "github": {
    "pr": {"merged": true, "merged_at": "2026-11-10T12:00:00Z", "merge_commit_sha": "0123456789abcdef0123456789abcdef01234567"},
    "commit": {"sha": "0123456789abcdef0123456789abcdef01234567"}
  },
  "cloudflare": {
    "type": "pages",
    "project": {
      "domains": ["example.com"],
      "canonical_deployment": {
        "id": "deployment-id", "environment": "production",
        "latest_stage": {"name": "deploy", "status": "success"},
        "deployment_trigger": {"metadata": {"commit_hash": "0123456789abcdef0123456789abcdef01234567", "commit_dirty": false}}
      }
    }
  },
  "http": [
    {"url": "https://example.com/", "status": 200, "headers": {"content-type": "text/html"}, "body": "<link rel=\"canonical\" href=\"https://example.com/\">"},
    {"url": "https://example.com/robots.txt", "status": 200, "headers": {"content-type": "text/plain"}, "body": "User-agent: *\nAllow: /\n"}
  ]
}
```

Worker evidence instead supplies `deployments` with `created_on` and traffic `versions`
(`version_id`, `percentage`), plus full `versions` with `id` and `annotations["workers/tag"]`.
The active deployment is the latest by timestamp. A split rollout is incomplete when the task
requires a single intended production revision. An explicit `expected_version_id` selects it;
otherwise an exact Git SHA tag must identify it. Unlinked source versions remain unverified.

Hostname/HTTP redirect observations use original requested URLs and unfollowed responses.
Crawl resources follow at most five same-origin redirects, storing `final_url` and a
`redirects` chain, and validate the final response. A cross-origin redirect remains unverified. Include both `/` and
`redirect_path` probes for each requested redirect. Header names are case-insensitive. Error
observations can contain `error` instead of a response. Keep application credentials out.

## Receipt

The report has `schema_version: 1`, `status`, `provenance`, `observed_at`, `assessed_at`,
`checks`, and `next_actions`. Check IDs are `github.merge`, `github.revision`,
`cloudflare.production`, `cloudflare.revision`, `cloudflare.domain`, `http.home`,
`http.robots`, `http.sitemap`, `html.canonical`, `redirect.www`, and `redirect.http` when relevant.
Each carries `status`, `expected`, `observed`, and `evidence`. Check status is `pass`, `fail`,
`pending`, or `unverified`. Overall status is `not_ready` if any check fails, then `pending`
if a prerequisite is pending, then `unverified` if evidence is missing, otherwise `verified`.

The evidence format retains facts rather than provider credentials. A replay can detect logical
errors in a release assessment. Live checks are necessary to establish the current site state.
