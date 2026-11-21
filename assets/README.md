# assets

| File | Size | Use |
|---|---|---|
| `social-preview.png` | 1280×640 | GitHub social preview, LinkedIn link image |
| `snippet-square.png` | 1080×1080 | square crop |
| `benchmark-grid.svg` | computed | the five-model grid, used on the benchmark page; regenerate with `python3 tools/render_grid.py > assets/benchmark-grid.svg` |
| `benchmark-grid.png` | 1280×640 | hand-drawn card, kept for social use; **not** computed from the results |

GitHub does not pick up the social preview from the repository: set it under
**Settings → General → Social preview** with `social-preview.png`.

The PNG cards are drawn, not computed. `benchmark-grid.svg` is computed from
`benchmark/results.json`, and a test fails when it or the table in
`benchmark/README.md` drifts from that file.
