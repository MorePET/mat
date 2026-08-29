## Description

<!-- What this PR does and why. One paragraph is fine. -->

## Type of Change

<!-- Keep ONE line below; delete the others. Must match the conventional-commit type. -->

- [ ] `feat` — New feature (minor version bump)
- [ ] `fix` — Bug fix (patch version bump)
- [ ] `feat!` / `fix!` / `BREAKING CHANGE:` — Breaking change (major version bump)
- [ ] `docs` — Documentation only (no release)
- [ ] `chore` / `refactor` / `test` / `ci` / `build` / `style` — No release

## Required

<!-- All boxes below MUST be checked. CI fails the PR otherwise. -->

- [ ] Tests pass locally (`uv run pytest`)
- [ ] Self-reviewed the diff
- [ ] No new warnings or errors in the changed code
- [ ] Linked to an issue in the `Refs:` line at the bottom (or explained why none)

## If Applicable

<!--
DELETE the entire section(s) below that don't apply.
Any unchecked box left in the body will fail the PR Hygiene check.
-->

### Documentation

- [ ] Updated `docs/templates/` and ran `just docs`
- [ ] Updated `CHANGELOG.md` under `## Unreleased` (release-please will move it to a versioned section on release)
- [ ] Updated `README.md` if user-facing API changed

### Tests

- [ ] Added new tests covering the change
- [ ] Manual testing performed (steps in **Manual Testing Details** below)

#### Manual Testing Details

<!-- Keep this section only if the box above is checked. Steps to reproduce. -->

### Dependencies

- [ ] Updated `pyproject.toml` and re-locked (`uv lock`)
- [ ] Updated `mat-rs/Cargo.toml` and re-locked (`cargo update`)
- [ ] Verified no breakage with downstream consumers (build123d, ocp_vscode, mat-vis-client)

### Breaking Change

- [ ] Migration notes added to `docs/migration/`
- [ ] `BREAKING CHANGE:` footer in commit message body
- [ ] Open issue / PR coordination with known downstream consumers

## Additional Notes

<!-- Screenshots, design rationale, links — anything that helps the reviewer. -->

Refs:

<!--
Required: link a GitHub issue (e.g., `Refs: #42`).
If there's no related issue, replace with a one-line explanation
(e.g., `Refs: N/A — pure CI tooling change`). The commit-msg hook
enforces a `Refs:` line; see docs/COMMIT_MESSAGE_STANDARD.md.
-->
