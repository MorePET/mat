---
type: issue
state: open
created: 2026-03-22T15:41:22Z
updated: 2026-03-22T15:41:22Z
author: gumyr
author_url: https://github.com/gumyr
url: https://github.com/MorePET/mat/issues/3
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-15T04:38:30.191Z
---

# [Issue 3]: [Further build123d/ocp_vscode integration](https://github.com/MorePET/mat/issues/3)

Thank you for creating this project, adding a material system to build123d is one of the long standing roadmap items. `py-mat` could be the solution, an project independent of `build123d` but directly supported.

Recently @bernhard-42 added support for PBR into the ocp_vscode viewer (see: https://discordapp.com/channels/964330484911972403/964330777401770025/1483435846081187981)  which uses MaterialX materials which can be browsed at the 4 supported sources:

- https://ambientcg.com/list?type=material,
- https://matlib.gpuopen.com/main/materials/all,
- https://polyhaven.com/textures,
- https://physicallybased.info/

We're wondering if you would consider supporting this version of PBR which allows for things like texture maps for wood grain?  Possibly something like: `steel = bd.Material(name="steel", density=7.8, pbr=bd.Material.gpuopen.load("Brushed Steel"))`.

I would also hope that we could get to the point where one could add materials to build123d shapes by just setting the `material` attribute like: `my_thing.material = Material(name="Steel", density=7.8)`.

We're looking forward to collaborating with you.

Cheers, Roger


