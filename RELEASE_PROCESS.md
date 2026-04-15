# Release Process for mat

## Creating a New Release

When releasing a new version of mat:

1. **Update version numbers:**
   ```bash
   cd /Users/larsgerchow/Projects/mat

   # Edit version in:
   # - pyproject.toml
   # - src/pymat/__init__.py
   ```

2. **Commit and tag:**
   ```bash
   git add -A
   git commit -m "Release vX.Y.Z - Description"
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   ```

3. **Update the 'latest' tag (force overwrite):**
   ```bash
   git tag -f -a latest -m "Latest release"
   ```

4. **Push everything:**
   ```bash
   git push origin main --tags
   git push -f origin latest  # Force push to update 'latest' tag
   ```

## Why This Works

Projects can now use:

```toml
[tool.uv.sources]
pymat = { git = "https://github.com/MorePET/mat.git", tag = "latest" }
```

This gives:
- ✅ **Automatic updates**: `uv sync` fetches the latest release
- ✅ **Stability**: Only updated on official releases (not random commits)
- ✅ **Explicit control**: Pin to specific version anytime with `tag = "v0.1.1"`
- ✅ **Reproducible**: Same commit hash until next release

## Alternative Options

### Pin to specific version:
```toml
pymat = { git = "https://github.com/MorePET/mat.git", tag = "v0.1.1" }
```

### Track main branch (bleeding edge):
```toml
pymat = { git = "https://github.com/MorePET/mat.git", branch = "main" }
```

### From PyPI (when published):
```toml
[project]
dependencies = ["pymat>=0.1.0"]
```
