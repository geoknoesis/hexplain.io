# Snapshot errata

Snapshots under `releases/` are immutable: an archive is never rewritten, even to correct it.
Defects found in a frozen snapshot are recorded here instead, and the gates that would reject
them list exactly these entries (`tools/test_version_immutability.py`). The version lineage
that follows from the corrections is `releases/lineage.json`.

## E1 bddo 1.0 has two contents

`https://hexplain.io/ns/bddo/1.0` names different graphs in different snapshots. Snapshots
2026-09-05.1, 2026-09-06.1 and 2026-09-06.2 freeze one graph; 2026-09-08.1 and 2026-09-08.2
freeze another under the same version IRI, which adds dispatch tables (`bddo:DispatchTable`,
`bddo:DispatchArm`, `bddo:hasDispatchTable`, `bddo:dispatchOnField`, `bddo:dispatchOnExpression`,
`bddo:dispatchDefault`, `bddo:armKey`, `bddo:armDataType`, `bddo:armTable` and their shapes),
seek scopes (`bddo:SeekScope`, `bddo:seekScope`, `bddo:regionScope`, `bddo:streamScope`),
`bddo:rootKeyFromField`, and a changed `bddo:FieldShape`. The second content should have had a
new version IRI. The next version, bddo 1.1 (snapshot 2026-09-24.1), is the successor of the
2026-09-08 content. A consumer that pinned bddo 1.0 before 2026-09-08 has the first graph.

## E2 aspect/bundle 1.2 has two contents

`https://hexplain.io/ns/aspect/bundle/1.2` names different graphs in 2026-09-06.2 and in
2026-09-08.1 / 2026-09-08.2. The difference is one generated annotation: the `skos:definition`
of `abnd:AssetShape` lists `abnd:hasPart` among its paths from 2026-09-08.1 on. No axiom or
constraint differs.

## E3 dangling priorVersion in raster, spatialref and geometry 1.1

Snapshot 2026-09-05.1 freezes raster 1.1, spatialref 1.1 and geometry 1.1, each with an
`owl:priorVersion` naming a version 1.0 that no snapshot contains. Those 1.0 versions were never
published; read the three 1.1 versions as the first versions of their modules.

## E4 missing priorVersion where a predecessor was published

These frozen versions state no `owl:priorVersion`, although a snapshot froze an earlier version
of the same module. The predecessor is the version given here:

| Version | Predecessor | First frozen in |
|---|---|---|
| aspect/bundle 1.1 | aspect/bundle 1.0 (2026-09-05.1) | 2026-09-06.1 |
| aspect/bundle 1.2 | aspect/bundle 1.1 (2026-09-06.1) | 2026-09-06.2 |
| dlv 1.1 | dlv 1.0 (2026-09-05.1) | 2026-09-06.1 |
| aspect/networkflow 1.1 | aspect/networkflow 1.0 (2026-09-05.1) | 2026-09-08.2 |
| net 1.1 | net 1.0 (2026-09-05.1) | 2026-09-08.2 |
| register/geometry-type 1.1 | register/geometry-type 1.0 (2026-09-05.1) | 2026-09-06.2 |

Every version published after 2026-09-24.2 names its predecessor.

## E5 snapshot 2026-09-08.1 described as leaving the canonical graphs unchanged

`releases/index.html` said of 2026-09-08.1 that its canonical graphs were unchanged. They were
not: see E1 and E2. The page is corrected; the archive is not.
