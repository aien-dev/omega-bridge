# Independent corrective-source review — L534

Target `e4e7ed4534aece6bd3ab944094b7eed2a5d05532`, baseline
`53708d459234a623c3a6926a7137d650989c0f46`.
Independent reviewer: gpt-6-luna, delegation `deleg_5c404b11`.
Review returned these dispositions:

- **Prior build-link clobber finding resolved for reviewed default build/install
  paths.** `tools/check-build-paths.sh:7–12` rejects a symlinked build root, links,
  hardlinked regular files and special nodes beneath it. Bootstrap, converter
  builder and native builder call it before output writes. Installation reaches
  those guards before publishing the prefix.
- **Prior uninstall-parent redirect finding resolved for reviewed single-user
  cases.** `tools/uninstall.sh:12–27` checks the named prefix before normalization
  and its preflight checks named parents, bin and payload. Lines44–48 repeat the
  checks after taking the lifecycle lock. `tools/om:20–27` validates invocation
  parents before dispatching uninstall.
- **No new important destructive-path defect found in the corrections.**

Limits: read-only immutable-source inspection, not a build or runtime test. Hostile
concurrent mutation and crash durability were not assessed and are not qualified.
The parent's independently executed full suite and source-only replay are separate
runtime evidence under this directory and `../native-path-safety/`.

This does not certify universal language attachment or whole-system retirement.
