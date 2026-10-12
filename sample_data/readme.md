# Sample global grids

Each file contains cell-centre coordinates for a regular WGS84 latitude-longitude grid:

- `input_global_3.75deg.xlsx`: 4,608 rows, used to exercise Excel input.
- `input_global_1deg.csv`: 64,800 rows.
- `input_global_0.25deg.csv`: 1,036,800 rows, used to exercise large-file handling.

The variables are deterministic synthetic data, not observations:

- `temperature_c` contains blank cells in a small region to test native missing values.
- `precipitation_mm` contains `-9999` in a small region to test a user-defined missing marker.

Use `-9999` as the **Input missing marker** when exporting precipitation.
