# Third-party notices

This directory contains dsRNAmax from Stephen Fletcher, pinned to commit
`674b5b513248ea551dcc9217f1059d593f827766`, under the BSD 3-Clause License.
The original notice is retained in `LICENSE`. The `discover` and `assemble`
JSON protocol adapter in `protocol.go` and its tests were added for Dicer Lab;
changes are marked with the 2026 copyright attribution in source headers.

Comparison with the pinned upstream revision also identifies modifications
to `main.go` (JSON command dispatch) and `main_test.go` (CLI checks). The local
protocol supports `discover`, `assemble`, `blocks`, and `screen`, with weighted
block selection, occurrence coordinates and exact reference screening.
These local changes are distributed under the same BSD 3-Clause terms; they
are not an official upstream dsRNAmax release.

The local `README.md` replaces a broken image reference with an upstream link;
the omitted image is not redistributed. All other retained upstream files,
including `testData/`, match that revision
after line-ending normalization. The 2025 dsRNAmax article is by Stephen J.
Fletcher and colleagues: https://doi.org/10.1093/nargab/lqaf064.

The executable also links Go's BSD runtime and MIT-licensed strutil v0.2.3,
tablewriter v0.0.5 and go-runewidth v0.0.9. Their license texts are retained in
`../licenses/` and must accompany binary redistributions.

The design adapter reuses upstream `getKmers` and extends the output with
occurrence coordinates. It does not import LUCID's GPL-licensed source.
