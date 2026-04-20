# Changelog

## [1.0.0](https://github.com/MorePET/mat/compare/rs-materials/v0.2.0...rs-materials/v1.0.0) (2026-04-20)


### ⚠ BREAKING CHANGES

* 3.0 vis cutover — `properties.pbr` removed, `.vis` canonical, mat-vis-client 0.4.x ([#52](https://github.com/MorePET/mat/issues/52))

### Added

* 3.0 vis cutover — `properties.pbr` removed, `.vis` canonical, mat-vis-client 0.4.x ([#52](https://github.com/MorePET/mat/issues/52)) ([49b5dff](https://github.com/MorePET/mat/commit/49b5dff0f5ca139e8e7f1dec82587d4ddf146c45))
* add mat-rs Rust crate for material database + formula parsing ([82630d4](https://github.com/MorePET/mat/commit/82630d4dea1c9f26a80f37a1d64d0f4c962e1e8f))
* embed TOML data files in crate via include_str!() ([0e82f07](https://github.com/MorePET/mat/commit/0e82f0713bf04133c5ff982dafc76cd689bf249c)), closes [#5](https://github.com/MorePET/mat/issues/5)


### Fixed

* regenerate uv.lock for py-materials rename, apply rustfmt ([d1ace0b](https://github.com/MorePET/mat/commit/d1ace0be9c2c0344f6767ce0820e555bb9e89457))


### Changed

* rename Rust crate mat-rs → rs-materials ([c2d8ec1](https://github.com/MorePET/mat/commit/c2d8ec13a7378f8ec5fc4f94a92db7a703994337))
