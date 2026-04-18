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
