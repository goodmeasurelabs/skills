# GitHub and Cloudflare release evidence

## GitHub

Inspect repository instructions, the deployment configuration, workflow YAML, and the intended
commit before executing a release. Use the existing account and pipeline.

```sh
gh pr view <number> --repo <owner/repo> --json state,mergedAt,mergeCommit,headRefOid,baseRefName
gh api repos/<owner/repo>/actions/runs
```

The REST PR fields are `merged`, `merged_at`, and `merge_commit_sha`. The SHA before merge
is a synthetic test merge. After merge it depends on the merge method. Pin a source commit
actually present in the repository. A workflow's `head_sha`, event, branch, conclusion, and
deployment outputs must correspond to the requested production operation. PR checks often
validate without deploying. Inspect workflow inputs and `checkout` configuration before
assuming that a dispatch will build an exact SHA.

## Pages

Use `GET /accounts/{account}/pages/projects/{project}` for `canonical_deployment` and `domains`.
Inspect the canonical deployment's `environment`, successful stage, and
`deployment_trigger.metadata.commit_hash` and `commit_dirty`. A list containing a matching
successful preview or an earlier success does not prove the production project is using it.

For Direct Upload, commit metadata is supplied by the uploader. Establish the clean source and
build provenance in the release receipt before trusting that association. Preserve the existing
output directory, production branch, build configuration, and bindings. A typical existing Pages
workflow uses `wrangler pages deploy <output> --project-name <project> --branch <production-branch>
--commit-hash <sha>`. Confirm those parameters against the repository before invoking it.

Cloudflare project and deployment objects can contain environment variables. Extract only IDs,
timestamps, status, domains, and commit metadata. The helper does this for its collected evidence.

## Workers

Use `GET /accounts/{account}/workers/scripts/{script}/deployments` to inspect active traffic,
and `GET /accounts/{account}/workers/scripts/{script}/versions/{id}` for the selected version.
A Worker can send traffic to multiple versions. A newly uploaded version need not be active.
Version IDs are not Git commit SHAs. Link the expected active version to the intended clean
source using the deployment output or an exact source SHA recorded in `workers/tag` metadata.
Treat missing source linkage as unverified. Tags are source labels, not cryptographic proof.

Respect the repository's existing Worker configuration, bindings, secrets, and rollout method.
An existing Pages or Sites project must not be migrated to Workers merely to make checks pass.

## Source documentation

- [GitHub pull requests](https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request)
- [Cloudflare Pages projects](https://developers.cloudflare.com/api/resources/pages/subresources/projects/methods/get/)
- [Workers deployments](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/deployments/methods/list/)
- [Workers versions](https://developers.cloudflare.com/workers/configuration/versions-and-deployments/)
- [Cloudflare domain redirects](https://developers.cloudflare.com/fundamentals/manage-domains/redirect-domain/)
