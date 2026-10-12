"""Run end-to-end conversions against all bundled sample resolutions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import xarray as xr

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import (
    AREA_WEIGHTED,
    NEAREST_NEIGHBOR,
    ConversionRequest,
    VariableSpec,
    convert_to_netcdf,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "verification",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    cases = (
        ("input_global_3.75deg.xlsx", 15.0, NEAREST_NEIGHBOR),
        ("input_global_1deg.csv", 5.0, AREA_WEIGHTED),
        ("input_global_0.25deg.csv", 3.75, AREA_WEIGHTED),
    )
    variables = (
        VariableSpec("temperature_c", "temperature_c", "degree_Celsius"),
        VariableSpec("precipitation_mm", "precipitation_mm", "mm"),
    )
    for filename, resolution, method in cases:
        source = PROJECT_ROOT / "sample_data" / filename
        output = args.output_dir / f"{source.stem}_{method}_{resolution:g}deg.nc"
        result = convert_to_netcdf(
            ConversionRequest(
                input_path=source,
                output_path=output,
                latitude_column="latitude",
                longitude_column="longitude",
                variables=variables,
                output_resolution=resolution,
                method=method,
                input_missing_value=-9999.0,
                description=f"Verification output from {filename}",
            )
        )
        with xr.open_dataset(output) as dataset:
            assert dataset.attrs["Conventions"] == "CF-1.8"
            assert dataset["crs"].attrs["epsg_code"] == "EPSG:4326"
            assert set(variables_item.name for variables_item in variables).issubset(dataset.data_vars)
        print(
            f"OK {filename}: {result.input_grid.resolution_text} -> {resolution:g}° "
            f"using {method} ({result.output_latitude_count} × {result.output_longitude_count})"
        )


if __name__ == "__main__":
    main()
