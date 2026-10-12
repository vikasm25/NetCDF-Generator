from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from core import (
    AREA_WEIGHTED,
    NEAREST_NEIGHBOR,
    RESOLUTION_ERROR,
    ConversionRequest,
    ValidationError,
    VariableSpec,
    convert_to_netcdf,
    inspect_grid,
    read_column_names,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_EXCEL = PROJECT_ROOT / "sample_data" / "input_global_3.75deg.xlsx"


class ConverterTests(unittest.TestCase):
    def test_reads_excel_headers_and_detects_grid(self) -> None:
        columns = read_column_names(SAMPLE_EXCEL)
        self.assertEqual(
            columns,
            ["latitude", "longitude", "temperature_c", "precipitation_mm"],
        )
        info = inspect_grid(SAMPLE_EXCEL, "latitude", "longitude")
        self.assertEqual(info.row_count, 4_608)
        self.assertEqual((info.latitude_count, info.longitude_count), (48, 96))
        self.assertAlmostEqual(info.latitude_resolution, 3.75)
        self.assertAlmostEqual(info.longitude_resolution, 3.75)
        self.assertEqual(info.latitude_bounds, (-90.0, 90.0))
        self.assertEqual(info.longitude_bounds, (-180.0, 180.0))

    def test_nearest_export_is_cf_georeferenced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nearest.nc"
            result = convert_to_netcdf(
                ConversionRequest(
                    input_path=SAMPLE_EXCEL,
                    output_path=output,
                    latitude_column="latitude",
                    longitude_column="longitude",
                    variables=(
                        VariableSpec("temperature_c", "air_temperature", "degree_Celsius"),
                    ),
                    output_resolution=15.0,
                    method=NEAREST_NEIGHBOR,
                    description="Synthetic global temperature",
                )
            )
            self.assertEqual((result.output_latitude_count, result.output_longitude_count), (12, 24))
            with xr.open_dataset(output) as dataset:
                self.assertEqual(dataset.attrs["Conventions"], "CF-1.8")
                self.assertEqual(dataset.sizes["latitude"], 12)
                self.assertEqual(dataset.sizes["longitude"], 24)
                self.assertIn("latitude_bounds", dataset)
                self.assertIn("longitude_bounds", dataset)
                self.assertIn("crs", dataset)
                self.assertEqual(dataset["crs"].attrs["epsg_code"], "EPSG:4326")
                self.assertEqual(dataset["air_temperature"].attrs["grid_mapping"], "crs")
                self.assertEqual(dataset["latitude"].attrs["units"], "degrees_north")
                self.assertEqual(dataset["longitude"].attrs["units"], "degrees_east")

    def test_rejects_equal_or_finer_resolution_with_required_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            request = ConversionRequest(
                input_path=SAMPLE_EXCEL,
                output_path=Path(directory) / "invalid.nc",
                latitude_column="latitude",
                longitude_column="longitude",
                variables=(VariableSpec("temperature_c", "temperature"),),
                output_resolution=3.75,
                method=NEAREST_NEIGHBOR,
            )
            with self.assertRaisesRegex(ValidationError, RESOLUTION_ERROR):
                convert_to_netcdf(request)

    def test_area_weighting_ignores_missing_values(self) -> None:
        latitudes = np.repeat([-45.0, 45.0], 4)
        longitudes = np.tile([-135.0, -45.0, 45.0, 135.0], 2)
        values = np.where(longitudes < 0, np.nan, np.where(latitudes < 0, 1.0, 3.0))
        frame = pd.DataFrame(
            {"latitude": latitudes, "longitude": longitudes, "value": values}
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.csv"
            output = Path(directory) / "weighted.nc"
            frame.to_csv(source, index=False)
            convert_to_netcdf(
                ConversionRequest(
                    input_path=source,
                    output_path=output,
                    latitude_column="latitude",
                    longitude_column="longitude",
                    variables=(VariableSpec("value", "value", "1"),),
                    output_resolution=180.0,
                    method=AREA_WEIGHTED,
                )
            )
            with xr.open_dataset(output) as dataset:
                result = dataset["value"].values
                self.assertEqual(result.shape, (1, 2))
                self.assertTrue(np.isnan(result[0, 0]))
                self.assertAlmostEqual(float(result[0, 1]), 2.0, places=6)

    def test_duplicate_grid_cells_are_rejected(self) -> None:
        frame = pd.DataFrame(
            {
                "latitude": [-45.0, -45.0, -45.0, 45.0, 45.0],
                "longitude": [-90.0, -90.0, 90.0, -90.0, 90.0],
                "value": [1, 2, 3, 4, 5],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "duplicates.csv"
            frame.to_csv(source, index=False)
            with self.assertRaisesRegex(ValidationError, "duplicate coordinate combinations"):
                convert_to_netcdf(
                    ConversionRequest(
                        input_path=source,
                        output_path=Path(directory) / "output.nc",
                        latitude_column="latitude",
                        longitude_column="longitude",
                        variables=(VariableSpec("value", "value"),),
                        output_resolution=180.0,
                        method=AREA_WEIGHTED,
                    )
                )


if __name__ == "__main__":
    unittest.main()
