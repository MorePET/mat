# Release Process for mat

Releases are driven by [release-please](https://github.com/googleapis/release-please) — see `.github/workflows/release-please.yml`. **Do not bump versions or push tags by hand.**

## How a release happens

1. Land conventional commits on `dev` (`feat:`, `fix:`, `feat!:`, etc. — the commit-msg hook enforces the format).
2. Open a `release/x.y.z → main` PR (manual gate; CI runs the full check matrix).
3. Merge to `main`. On every push to main, release-please re-evaluates the commit history since the last tag and (per package) opens or updates a **Release PR** titled `chore(main): release X.Y.Z`. The PR bumps `pyproject.toml` + `src/pymat/__init__.py` (Python) or `mat-rs/Cargo.toml` (Rust) and prepends a CHANGELOG section generated from commits.
4. Review the Release PR — version computation:
   - `feat:` → minor bump
   - `fix:` → patch bump
   - `feat!:` or `BREAKING CHANGE:` footer → major bump
   - `chore:`, `docs:`, `ci:`, `test:`, `style:` → no release
5. Merge the Release PR. Release-please pushes the tag (`vX.Y.Z` for Python, `rs-materials/vX.Y.Z` for Rust). The tag push triggers `release.yml` (PyPI) or `release-rs-materials.yml` (crates.io). Release-please also creates the GitHub Release with auto-generated notes.

## Two independent packages

Each package has its own Release PR, version, and tag:

| Package        | Path     | Tag format             | Publishes to |
|----------------|----------|------------------------|--------------|
| `py-materials` | `.`      | `vX.Y.Z`               | PyPI         |
| `rs-materials` | `mat-rs` | `rs-materials/vX.Y.Z`  | crates.io    |

A `feat:` touching only `mat-rs/**` triggers a Rust Release PR; a `feat:` touching `src/pymat/**` triggers a Python Release PR. Commits affecting both produce two Release PRs.

## Auth

`release-please.yml` uses the `RELEASE_APP` GitHub App (same App used by `sync-main-to-dev.yml`). This is required — tags pushed by `GITHUB_TOKEN` are inert under GitHub's recursion-protection and would silently skip the publish workflows.

### Registry credentials

Both registries use **trusted publishing** (OIDC). Neither publishing job reads
a long-lived API token, so there is nothing to rotate and nothing that expires:

| Registry  | Publishing job                       | Environment | Token exchanged by             |
|-----------|--------------------------------------|-------------|--------------------------------|
| PyPI      | `release.yml`                        | `pypi`      | `pypa/gh-action-pypi-publish`  |
| PyPI      | `publish-mcp.yml`                    | `pypi`      | `pypa/gh-action-pypi-publish`  |
| crates.io | `release-rs-materials.yml`           | `crates-io` | `rust-lang/crates-io-auth-action` |

Each job needs `permissions: id-token: write` and must run in the environment
the registry's trusted-publisher entry names. The crates.io entry lives at
<https://crates.io/crates/rs-materials/settings> and pins repository owner and
name, the workflow **filename**, and the environment name — renaming any of the
three breaks publishing until the entry is updated to match.

Trusted publishing authenticates the *workflow*, not the *ref* — the OIDC claim
says nothing about which commit is checked out. What constrains that is each
environment's **deployment branch policy**:

| Environment | Refs allowed to deploy                        |
|-------------|-----------------------------------------------|
| `pypi`      | `main`, tags `v*` and `pymat-mcp/v*`          |
| `crates-io` | `main`, tags `rs-materials/v*`                |

Without it, `workflow_dispatch` from any branch would publish whatever that
branch's `pyproject.toml` / `Cargo.toml` claimed as its version. `main` is
allowed because it is the retry path below; nothing else is.

A policy pattern must be added for **every** tag prefix that deploys to the
environment — `*` does not cross `/`, so `v*` matches neither `pymat-mcp/v0.1.0`
nor `rs-materials/v0.3.0`. Two PyPI projects share the `pypi` environment
(`release.yml` and `publish-mcp.yml`), which is why it carries two tag patterns.
Adding a third publishing workflow means adding its tag pattern here, or its
tag pushes will fail with *"Branch not allowed to deploy"* after a green build.

`vars.CRATES_IO_PUBLISH_ENABLED` remains as a kill switch independent of
credentials (`gh variable set CRATES_IO_PUBLISH_ENABLED --body false`).

The dead `CARGO_REGISTRY_TOKEN` secret is scheduled for deletion once the first
trusted publish succeeds; it is already invalid and no workflow reads it.

### Retrying a failed publish

Re-run from the tag, which is what pins the version being published:

```console
gh workflow run release-rs-materials.yml --ref rs-materials/vX.Y.Z
```

Two cases where that does not work:

- **The workflow file itself is the bug.** A tag ref replays the workflow as it
  was at that tag, so the fix would not be picked up.
- **The tag predates `workflow_dispatch:`** on that workflow. `gh workflow run`
  reads the trigger from the target ref, so a tag whose workflow file has no
  dispatch trigger cannot be dispatched at all — this applies to every tag
  before `rs-materials/v0.3.0`.

In both cases: land the fix on `main` and dispatch `--ref main`. That publishes
the version in `main`'s manifest, which is the version you want only while
`main` still points at the release commit — check before dispatching. Either
way the tag never needs to be deleted or moved.

## Why This Works

Projects can now use:

```toml
[tool.uv.sources]
pymat = { git = "https://github.com/MorePET/mat.git", tag = "latest" }
```

This gives:

- Automatic updates: `uv sync` fetches the latest release
- Stability: only updated on official releases (not random commits)
- Explicit control: pin to a specific version anytime with `tag = "v0.1.1"`
- Reproducible: same commit hash until next release

## Alternative Options

### Pin to specific version

```toml
pymat = { git = "https://github.com/MorePET/mat.git", tag = "v0.1.1" }
```

### Track main branch (bleeding edge)

```toml
pymat = { git = "https://github.com/MorePET/mat.git", branch = "main" }
```

### From PyPI (when published)

```toml
[project]
dependencies = ["pymat>=0.1.0"]
```
