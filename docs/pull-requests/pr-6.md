---
type: pull_request
state: open
branch: py310 → main
created: 2026-04-04T12:47:32Z
updated: 2026-04-04T12:47:32Z
author: bernhard-42
author_url: https://github.com/bernhard-42
url: https://github.com/MorePET/mat/pull/6
comments: 0
labels: none
assignees: none
milestone: none
projects: none
synced: 2026-04-15T04:38:31.295Z
---

# [PR 6](https://github.com/MorePET/mat/pull/6) enable Python 3.10 support

## Description

<!-- Provide a clear and concise description of what this PR does. -->

## Type of Change

<!-- Mark the relevant option(s) with an 'x' -->

- [ ] `feat` -- New feature
- [ ] `fix` -- Bug fix
- [ ] `docs` -- Documentation only
- [ ] `chore` -- Maintenance task (deps, config, etc.)
- [ ] `refactor` -- Code restructuring (no behavior change)
- [ ] `test` -- Adding or updating tests
- [ ] `ci` -- CI/CD pipeline changes
- [X] `build` -- Build system or dependency changes
- [ ] `revert` -- Reverts a previous commit
- [ ] `style` -- Code style (formatting, whitespace)

### Modifiers

- [ ] Breaking change (`!`) -- This change breaks backward compatibility

## Changes Made

We would like to use py-materials as the materials provider for build123d, see https://github.com/MorePET/mat/issues/3
build123d supports Python 3.10 - 3.14
We were wondering whether py-materials could also support Python 3.10

As far as I can see, the only issue is the use of `tomllib`, however there is a proven workaround with `tomli` in Python 3.10.

This PR adds tomli conditionally as 3.10 dependency and has a Python version checked import of tomli or tomllib

CC: @gumyr

## Changelog Entry

     ### Added
     - Python 3.10 support

## Testing

I just ran the pytest suite under Python 3.10 and it created the same result as under Python 3.14

### Manual Testing Details

Run the pytest suite under Python 3.10

## Checklist

<!-- Mark completed items with an 'x' -->
- [X] My code follows the project's style guidelines
- [X] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have updated the documentation accordingly (edit `docs/templates/`, then run `just docs`)
- [ ] I have updated `CHANGELOG.md` in the `[Unreleased]` section (and pasted the entry above)
- [X] My changes generate no new warnings or errors
- [ ] I have added tests that prove my fix is effective or that my feature works
- [X] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published

## Additional Notes

None

Refs:

(https://github.com/MorePET/mat/issues/3)

