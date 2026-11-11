---
name: aiwaterfalls
description: Complete and verify website releases from GitHub to Cloudflare Pages or Workers. Use for deploying a requested revision, waiting for a PR merge, checking a production release, or diagnosing domain redirects, crawl files, and deployment mismatches.
---

# AI Waterfalls

Carry the requested release through its dependencies and verify the observed production result.
Use the user's repository, hosting project, revision, and completion criteria. Check the actual
host before choosing a deployment method. A Cloudflare DNS zone does not establish that
Cloudflare hosts the website.

## Establish the release

- Record the exact repository, production origin, requested revision or PR, and requested checks.
  Use the existing repository's build and deployment workflow. Read
  [GitHub and Cloudflare](references/github-cloudflare.md) when inspecting or changing a release.
- For an after-merge task, require `merged: true` and a non-null `merged_at`. An open PR's
  `merge_commit_sha` is a provisional test merge. It does not authorize publishing that SHA.
- Check existing deployments before starting another. Resume a matching pending deployment.
  A successful PR validation, completed workflow, or newly uploaded Worker version alone
  does not establish which revision serves production.

## Perform the requested work

Build from the intended clean checkout, using its established build command and service bindings.
Deploy through the existing reviewed workflow or provider CLI within the user's authorized scope.
Record the source SHA and returned deployment/version ID. Recheck branch state if a workflow
builds a moving branch. Never attach a claimed SHA to an artifact built from different files.

Keep a small receipt of the target, deployment ID, completed operations, unresolved dependencies,
and evidence. After interruption, reread provider state before repeating a mutation. A timed-out
request may already have succeeded. Poll a specific nonterminal deployment with a bounded
deadline. If access or another prerequisite is missing, identify that dependency and continue
independent checks. Use the host's follow-up mechanism only when the user requested waiting.

Use a host-level `301` for a requested permanent hostname redirect. Cloudflare redirect rules
require the incoming hostname to be proxied. Match the intended hostname and retain paths and
query strings unless the user specified another mapping. Verify the origin's TLS and actual
responses. A canonical HTML tag does not establish a redirect.

## Check the result

The bundled Python 3.10+ helper performs read-only checks and returns a structured receipt.
It can inspect live APIs and HTTP responses, or assess recorded observations.

```sh
python3 <skill-directory>/scripts/check-launch.py --target target.json --live --out receipt.json
python3 <skill-directory>/scripts/check-launch.py --target target.json --evidence evidence.json --out receipt.json
```

Read [the target and evidence format](references/verification.md) to select only the required
checks. Live GitHub reads use the existing `gh` login. Cloudflare API reads use an existing
`CLOUDFLARE_API_TOKEN`; missing access is recorded as unverified. Never paste credentials into
a target, report, or transcript. Keep authenticated provider responses to the allowlisted subset.

Verify these common release failures when relevant to the task:

- The active production deployment corresponds to the requested revision. Pages preview URLs
  and old successful deployments are insufficient. Workers may split traffic across versions;
  inspect active traffic and source linkage rather than assuming the newest version is live.
- `robots.txt` returns the requested status and a plain-text policy (Sitemap-only and empty policies are valid). A SPA can return
  its homepage at that path with HTTP 200. Check both content type and body.
- A sitemap is XML, contains the intended canonical URL, and can be fetched. Follow bounded same-origin redirects for crawl files and retain the redirect evidence.
- The homepage's canonical URL matches the intended origin. Check observed HTML.
- A `www` or HTTP redirect returns the required status and destination (301 or 308 by default). Include a path/query
  probe to catch rules that silently send every URL to the homepage.

The helper exits `0` for verified requested checks, `2` for pending/failed/unverified checks,
and `1` for invalid input. Its receipt is an assessment of its evidence, not permission to mutate.
Recorded evidence is labeled with its observation time and must not be described as a live check.

Report verified results and precise remaining dependencies. Distinguish a failed check from
an inaccessible check. Completion requires the requested checks and user journey to pass;
the helper covers the mechanical checks selected in the target, not every application feature.
