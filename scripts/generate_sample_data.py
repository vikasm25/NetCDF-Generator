"""Generate deterministic global test grids for the application."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def grid_block(latitudes: np.ndarray, longitudes: np.ndarray) -> pd.DataFrame:
    latitude = np.repeat(latitudes, len(longitudes))
    longitude = np.tile(longitudes, len(latitudes))
    latitude_radians = np.deg2rad(latitude)
    longitude_radians = np.deg2rad(longitude)
    temperature = (
        17.0
        - 0.42 * np.abs(latitude)
        + 7.5 * np.cos(latitude_radians) * np.cos(longitude_radians)
    )
    precipitation = np.maximum(
        0.0,
        95.0
        + 110.0 * np.cos(latitude_radians) ** 2
        + 35.0 * np.sin(2.0 * longitude_radians) * np.cos(latitude_radians),
    )
    temperature[(latitude >= 10) & (latitude <= 20) & (longitude >= 40) & (longitude <= 60)] = np.nan
    precipitation[(latitude >= -35) & (latitude <= -25) & (longitude >= 120) & (longitude <= 140)] = -9999.0
    return pd.DataFrame(
        {
            "latitude": latitude,
            "longitude": longitude,
            "temperature_c": np.round(temperature, 4),
            "precipitation_mm": np.round(precipitation, 4),
        }
    )


def write_csv(path: Path, resolution: float) -> None:
    latitudes = np.arange(-90 + resolution / 2, 90, resolution, dtype="float64")
    longitudes = np.arange(-180 + resolution / 2, 180, resolution, dtype="float64")
    first = True
    rows_per_block = max(1, int(65_000 / len(longitudes)))
    for start in range(0, len(latitudes), rows_per_block):
        block = grid_block(latitudes[start : start + rows_per_block], longitudes)
        block.to_csv(path, mode="w" if first else "a", header=first, index=False, na_rep="")
        first = False


def write_excel(path: Path, resolution: float) -> None:
    latitudes = np.arange(-90 + resolution / 2, 90, resolution, dtype="float64")
    longitudes = np.arange(-180 + resolution / 2, 180, resolution, dtype="float64")
    grid_block(latitudes, longitudes).to_excel(path, index=False, sheet_name="global_grid")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "sample_data",
    )
    parser.add_argument(
        "--include-excel",
        action="store_true",
        help="Also regenerate the 3.75-degree Excel workbook.",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.include_excel:
        write_excel(args.output_dir / "input_global_3.75deg.xlsx", 3.75)
    write_csv(args.output_dir / "input_global_1deg.csv", 1.0)
    write_csv(args.output_dir / "input_global_0.25deg.csv", 0.25)


if __name__ == "__main__":
    main()
