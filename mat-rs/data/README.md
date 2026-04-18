# mat-rs/data — symlinks to the canonical TOMLs

These files are **symlinks** pointing at `../../src/pymat/data/*.toml`. There is exactly one source of truth for material data, and it lives on the Python side.

## Why symlinks instead of duplication

Earlier the Rust crate kept a separate copy of each TOML, embedded at compile time via `include_str!`. The two copies drifted (vis cutover, new materials) and the integration test `builtin_matches_file_loaded` started failing — symptom of the SSoT violation.

## How it works

- **Local builds** (`cargo build`, `cargo test`): `include_str!` follows the symlink at compile time and reads the actual TOML content from `src/pymat/data/`.
- **Published crate** (`cargo publish`): cargo packages the resolved file content into the `.crate` tarball — there are no symlinks in the published artifact, just baked-in TOML strings. Consumers of `rs-materials` from crates.io see normal files.
- **Cross-platform**: native Windows requires symlink permission on `git clone`. macOS / Linux / WSL handle this transparently.

## Adding a new material category

Add the TOML in `src/pymat/data/<category>.toml`, then add a symlink here:

```bash
ln -s ../../src/pymat/data/<category>.toml mat-rs/data/<category>.toml
```

And register the category in `mat-rs/src/db.rs` via the `BUILTIN_DATA` array.
