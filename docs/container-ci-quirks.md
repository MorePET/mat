# Container CI vs Bare-Runner CI

Behavioral differences when running CI inside
`ghcr.io/vig-os/devcontainer:latest` via the GitHub Actions `container:`
directive, compared to the bare-runner workflow (`ci.yml`).

## No `setup-env` composite action

The bare-runner CI uses `.github/actions/setup-env` to install Python, uv,
pre-commit, and other tools on a fresh Ubuntu runner.  Inside the container
these tools are already present in the image, and marketplace setup actions
(`actions/setup-python`, `astral-sh/setup-uv`) target the runner OS rather
than the container filesystem.  The container workflow skips `setup-env`
entirely and calls tools directly.

## git safe.directory

`actions/checkout` runs on the host and bind-mounts the workspace into the
container.  The resulting directory is owned by a different UID than the
container's root user, which triggers git's `safe.directory` rejection.
The container workflow adds:

```yaml
- run: git config --global --add safe.directory "$GITHUB_WORKSPACE"
```

## Root user

The container runs as `root` by default.  No `sudo` is required and file
permission issues are unlikely, but any git operations need the
`safe.directory` fix above.

## No Docker-in-Docker

The container job does not have access to a Docker or Podman daemon.
Jobs that require building or running containers (e.g. integration tests
using `devcontainer up`) are not supported in this workflow.

## No dedicated security job

The bare-runner CI runs a standalone security job that invokes `bandit`
and `safety` independently, uploads JSON reports as artifacts, and posts
findings to the step summary.  `bandit` still runs inside the container
via the `pre-commit` lint hook (`uv run bandit`), but `safety` is not
available in the image.  The dedicated security job with artifact uploads
remains bare-runner-only until `safety` is added to a future image
release.

## No dependency-review job

The bare-runner CI includes an `actions/dependency-review-action` job
that checks for dependency vulnerabilities on pull requests.  This is a
marketplace action that inspects the GitHub dependency graph and does not
need to run inside the container.  It is omitted from the container
workflow to keep it focused on validating tools shipped in the image.

## No coverage artifact upload

The bare-runner test job produces an XML coverage report
(`--cov-report=xml`) and uploads it via `actions/upload-artifact`.  The
container test job only prints coverage to the terminal
(`--cov-report=term-missing`) and does not upload artifacts.

## Pre-commit cache miss

The image ships a pre-commit hook cache at `/opt/pre-commit-cache`, built
from the template workspace's `.pre-commit-config.yaml` (which uses version
tags as revs).  This repository pins hooks by commit hash, so the cached
environments do not match and pre-commit downloads fresh environments at
runtime.
