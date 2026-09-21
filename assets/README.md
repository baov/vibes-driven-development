# assets

| File | Size | Use |
|---|---|---|
| `social-preview.png` | 1280×640 | GitHub social preview, LinkedIn link image |
| `snippet-square.png` | 1080×1080 | square crop |
| `benchmark-grid.png` | 1280×640 | the five-model grid, used on the benchmark page |

GitHub does not pick up the social preview from the repository: set it under
**Settings → General → Social preview** with `social-preview.png`.

The figures on these cards are drawn, not computed from `benchmark/runs/`. A new
run changes the grid in `benchmark/README.md` without changing the image — redraw
`benchmark-grid.png` when the two disagree.
