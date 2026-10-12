# NetCDF Grid Generator

A desktop application that converts regular latitude-longitude tables in Excel or CSV format to coarser, georeferenced NetCDF files.

## What it does

- Reads `.xlsx`, `.xls`, `.csv`, and `.tsv` files.
- Lets you select latitude, longitude, optional extra dimensions, and one or more variables.
- Detects and validates regular input-grid spacing.
- Supports nearest-neighbor and spherical area-weighted averaging.
- Rejects output resolutions that are equal to or finer than either input axis.
- Preserves missing values. Area-weighted output ignores missing contributors and remains missing when a target cell has no valid data.
- Writes compressed NetCDF4 with CF-1.8 metadata, WGS84 CRS information, coordinate bounds, and user-supplied descriptions.
- Writes through a temporary file, so a failed conversion does not leave a partial output.

## Install and run

Double-click `Run App.bat`. It checks the default Python environment, installs any missing packages, and launches the application. Python 3.12 or 3.13 must be available in `PATH`.

For manual setup instead:

```powershell
cd NetCDF Grid Generator Directory
python -m venv .venv
.venv\Scripts\python -m pip install -r Requirements.txt
.venv\Scripts\python Main.py
```

The batch launcher installs into the default Python environment as requested. If that location is protected, it retries using the current Windows user's package directory.

## Input format

Use a flat table with one row per grid cell. Latitude and longitude must be numeric cell centres on a regular grid. Each combination of selected dimensions, latitude, and longitude must be unique. Variable cells may be blank, `NaN`, `NA`, `N/A`, `null`, `none`, or a numeric marker selected in the app.

The output resolution is a single square-cell size in degrees. It must be strictly larger than both input spacings and divide the input extent exactly.

## Interpolation methods

- **Nearest Neighbor** selects the input cell centre nearest to each output cell centre. A missing selected value stays missing.
- **Area-weighted average** computes exact spherical latitude-longitude overlap areas. Missing source values are excluded from the denominator.

## Sample data

The `sample_data` directory contains global 3.75°, 1°, and 0.25° grids. Regenerate them with:

```powershell
.venv\Scripts\python scripts\generate_sample_data.py --include-excel
```

## Tests

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.venv\Scripts\python -m unittest discover -s tests -v
```

Run real conversions against all three bundled files with:

```powershell
.venv\Scripts\python scripts\verify_samples.py
```
