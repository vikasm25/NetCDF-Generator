"""Validation, conservative regridding, and CF-compliant NetCDF export."""

from __future__ import annotations

import os
import re
import tempfile
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import xarray as xr


NEAREST_NEIGHBOR = "nearest"
AREA_WEIGHTED = "area_weighted"
RESOLUTION_ERROR = (
    "Can not increase resolution, change the output resolution coarser then the input data"
)
SUPPORTED_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls"}
_MISSING_TEXT = {"", "na", "n/a", "nan", "none", "null", "missing"}
_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ValidationError(ValueError):
    """Raised when the selected input cannot produce a reliable output grid."""


@dataclass(frozen=True)
class VariableSpec:
    column: str
    name: str
    units: str = ""
    description: str = ""


@dataclass(frozen=True)
class DimensionSpec:
    column: str
    name: str


@dataclass(frozen=True)
class GridInfo:
    row_count: int
    latitude_count: int
    longitude_count: int
    latitude_resolution: float
    longitude_resolution: float
    latitude_values: np.ndarray = field(repr=False)
    longitude_values: np.ndarray = field(repr=False)
    latitude_bounds: tuple[float, float]
    longitude_bounds: tuple[float, float]

    @property
    def resolution_text(self) -> str:
        return (
            f"{self.latitude_resolution:g}° × "
            f"{self.longitude_resolution:g}°"
        )

    @property
    def shape_text(self) -> str:
        return f"{self.latitude_count:,} × {self.longitude_count:,} cells"


@dataclass(frozen=True)
class ConversionRequest:
    input_path: Path | str
    output_path: Path | str
    latitude_column: str
    longitude_column: str
    variables: tuple[VariableSpec, ...]
    output_resolution: float
    method: str
    dimensions: tuple[DimensionSpec, ...] = ()
    description: str = ""
    input_missing_value: float | None = None
    output_fill_value: float = -9999.0


@dataclass(frozen=True)
class ConversionResult:
    output_path: Path
    input_grid: GridInfo
    output_latitude_count: int
    output_longitude_count: int
    variable_names: tuple[str, ...]


def safe_netcdf_name(value: str, fallback: str = "value") -> str:
    """Return a predictable NetCDF identifier suitable for UI defaults."""
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", str(value).strip()).strip("_")
    if not cleaned:
        cleaned = fallback
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned


def _validate_name(name: str, label: str) -> None:
    if not _NAME_PATTERN.fullmatch(name):
        raise ValidationError(
            f"{label} '{name}' is not a valid NetCDF name. Use letters, numbers, "
            "and underscores, and do not start with a number."
        )


def _read_table(
    path: Path | str,
    *,
    usecols: Sequence[str] | None = None,
    nrows: int | None = None,
) -> pd.DataFrame:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValidationError(
            "Unsupported input file. Choose an Excel (.xlsx or .xls) or CSV file."
        )
    if not source.is_file():
        raise ValidationError(f"Input file does not exist: {source}")

    wanted = set(usecols or [])
    selector = (lambda column: str(column) in wanted) if usecols is not None else None
    try:
        if suffix == ".csv":
            with source.open("r", encoding="utf-8-sig", newline="") as stream:
                sample = stream.read(16_384)
            try:
                separator = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
            except csv.Error:
                separator = ","
            frame = pd.read_csv(
                source,
                sep=separator,
                usecols=selector,
                nrows=nrows,
                low_memory=False,
            )
        elif suffix == ".tsv":
            frame = pd.read_csv(
                source,
                sep="\t",
                usecols=selector,
                nrows=nrows,
                low_memory=False,
            )
        else:
            frame = pd.read_excel(source, usecols=selector, nrows=nrows)
    except (OSError, ValueError, ImportError) as exc:
        raise ValidationError(f"Could not read the input file: {exc}") from exc

    frame.columns = [str(column).strip() for column in frame.columns]
    if len(frame.columns) != len(set(frame.columns)):
        raise ValidationError("The input file contains duplicate column names.")
    if usecols is not None:
        missing = [column for column in usecols if column not in frame.columns]
        if missing:
            raise ValidationError(f"Missing selected column(s): {', '.join(missing)}")
        frame = frame.loc[:, list(usecols)]
    return frame


def read_column_names(path: Path | str) -> list[str]:
    columns = list(_read_table(path, nrows=0).columns)
    if not columns:
        raise ValidationError("The input file has no columns.")
    return columns


def _numeric_series(series: pd.Series, label: str, missing_value: float | None) -> pd.Series:
    text = series.astype("string").str.strip().str.lower()
    recognized_missing = series.isna() | text.isin(_MISSING_TEXT)
    numeric = pd.to_numeric(series, errors="coerce").astype("float64")
    if missing_value is not None:
        recognized_missing |= np.isclose(
            numeric.to_numpy(), missing_value, rtol=0.0, atol=0.0, equal_nan=False
        )
    invalid = numeric.isna() & ~recognized_missing
    if invalid.any():
        examples = series.loc[invalid].astype(str).head(3).tolist()
        raise ValidationError(
            f"Column '{label}' contains non-numeric values, for example: "
            f"{', '.join(examples)}"
        )
    numeric = numeric.mask(recognized_missing)
    numeric = numeric.mask(~np.isfinite(numeric))
    return numeric


def _coordinate_series(series: pd.Series, label: str) -> pd.Series:
    numeric = _numeric_series(series, label, None)
    if numeric.isna().any():
        raise ValidationError(f"Coordinate column '{label}' contains missing values.")
    return numeric


def _clean_dimension_series(series: pd.Series, label: str) -> pd.Series:
    if series.isna().any():
        raise ValidationError(f"Dimension column '{label}' contains missing values.")
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        cleaned = series.astype(str).str.strip()
        if cleaned.eq("").any():
            raise ValidationError(f"Dimension column '{label}' contains blank values.")
        return cleaned
    return series


def _regular_axis(values: pd.Series, label: str) -> tuple[np.ndarray, float]:
    unique = np.sort(values.unique().astype("float64"))
    if unique.size < 2:
        raise ValidationError(f"{label} must contain at least two unique coordinates.")
    differences = np.diff(unique)
    step = float(np.median(differences))
    tolerance = max(1e-9, abs(step) * 1e-6)
    if step <= 0 or not np.allclose(differences, step, rtol=0.0, atol=tolerance):
        raise ValidationError(
            f"{label} coordinates are not a regular grid. Coordinate spacing must be uniform."
        )
    return unique, step


def _snap_bound(value: float, candidates: Sequence[float], tolerance: float) -> float:
    for candidate in candidates:
        if abs(value - candidate) <= tolerance:
            return float(candidate)
    return float(value)


def _infer_grid(frame: pd.DataFrame, latitude_column: str, longitude_column: str) -> GridInfo:
    latitudes, latitude_step = _regular_axis(frame[latitude_column], "Latitude")
    longitudes, longitude_step = _regular_axis(frame[longitude_column], "Longitude")

    if latitudes[0] < -90 or latitudes[-1] > 90:
        raise ValidationError("Latitude coordinates must be between -90 and 90 degrees.")
    if longitudes[-1] - longitudes[0] > 360 + longitude_step:
        raise ValidationError("Longitude coordinates cover more than 360 degrees.")

    latitude_tolerance = max(1e-8, latitude_step * 1e-6)
    longitude_tolerance = max(1e-8, longitude_step * 1e-6)
    latitude_lower = _snap_bound(
        latitudes[0] - latitude_step / 2,
        (-90.0,),
        latitude_tolerance,
    )
    latitude_upper = _snap_bound(
        latitudes[-1] + latitude_step / 2,
        (90.0,),
        latitude_tolerance,
    )
    longitude_lower = _snap_bound(
        longitudes[0] - longitude_step / 2,
        (-180.0, 0.0),
        longitude_tolerance,
    )
    longitude_upper = _snap_bound(
        longitudes[-1] + longitude_step / 2,
        (180.0, 360.0),
        longitude_tolerance,
    )
    if latitude_lower < -90 - latitude_tolerance or latitude_upper > 90 + latitude_tolerance:
        raise ValidationError("Latitude cell bounds extend outside -90 to 90 degrees.")
    if longitude_upper - longitude_lower > 360 + longitude_tolerance:
        raise ValidationError("Longitude cell bounds cover more than 360 degrees.")

    return GridInfo(
        row_count=len(frame),
        latitude_count=len(latitudes),
        longitude_count=len(longitudes),
        latitude_resolution=latitude_step,
        longitude_resolution=longitude_step,
        latitude_values=latitudes,
        longitude_values=longitudes,
        latitude_bounds=(latitude_lower, latitude_upper),
        longitude_bounds=(longitude_lower, longitude_upper),
    )


def inspect_grid(
    path: Path | str,
    latitude_column: str,
    longitude_column: str,
) -> GridInfo:
    if latitude_column == longitude_column:
        raise ValidationError("Latitude and longitude must use different columns.")
    frame = _read_table(path, usecols=[latitude_column, longitude_column])
    frame[latitude_column] = _coordinate_series(frame[latitude_column], latitude_column)
    frame[longitude_column] = _coordinate_series(frame[longitude_column], longitude_column)
    return _infer_grid(frame, latitude_column, longitude_column)


def _target_axis(lower: float, upper: float, resolution: float, label: str) -> tuple[np.ndarray, np.ndarray]:
    span = upper - lower
    raw_count = span / resolution
    count = int(round(raw_count))
    if count < 1 or not np.isclose(raw_count, count, rtol=0.0, atol=1e-8):
        raise ValidationError(
            f"Output resolution {resolution:g}° does not divide the {label.lower()} "
            f"extent ({span:g}°) exactly."
        )
    edges = lower + np.arange(count + 1, dtype="float64") * resolution
    edges[-1] = upper
    centers = (edges[:-1] + edges[1:]) / 2
    return centers, edges


def _nearest_indices(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    insertion = np.searchsorted(source, target)
    right = np.clip(insertion, 0, len(source) - 1)
    left = np.clip(insertion - 1, 0, len(source) - 1)
    choose_right = np.abs(source[right] - target) < np.abs(source[left] - target)
    return np.where(choose_right, right, left)


def _overlap_weights(
    source_edges: np.ndarray,
    target_edges: np.ndarray,
    *,
    latitude: bool,
) -> np.ndarray:
    lower = np.maximum(target_edges[:-1, None], source_edges[None, :-1])
    upper = np.minimum(target_edges[1:, None], source_edges[None, 1:])
    overlap = upper > lower
    if latitude:
        weights = np.sin(np.deg2rad(upper)) - np.sin(np.deg2rad(lower))
    else:
        weights = np.deg2rad(upper - lower)
    return np.where(overlap, weights, 0.0)


def _area_weighted_values(
    values: np.ndarray,
    latitude_weights: np.ndarray,
    longitude_weights: np.ndarray,
) -> np.ndarray:
    source_shape = values.shape
    flattened = values.reshape((-1, source_shape[-2], source_shape[-1]))
    result = np.full(
        (flattened.shape[0], latitude_weights.shape[0], longitude_weights.shape[0]),
        np.nan,
        dtype="float64",
    )
    longitude_transpose = longitude_weights.T
    for start in range(0, flattened.shape[0], 8):
        block = flattened[start : start + 8]
        valid = np.isfinite(block)
        numerator = np.matmul(
            np.matmul(latitude_weights, np.where(valid, block, 0.0)),
            longitude_transpose,
        )
        denominator = np.matmul(
            np.matmul(latitude_weights, valid.astype("float64")),
            longitude_transpose,
        )
        result[start : start + len(block)] = np.divide(
            numerator,
            denominator,
            out=np.full_like(numerator, np.nan),
            where=denominator > 0,
        )
    return result.reshape(source_shape[:-2] + result.shape[-2:])


def _sorted_unique(series: pd.Series) -> np.ndarray:
    values = pd.Index(pd.unique(series))
    try:
        values = values.sort_values()
    except TypeError:
        values = pd.Index(sorted(values.astype(str)))
    array = values.to_numpy()
    if array.dtype == object:
        array = array.astype(str)
    return array


def _dense_variable(
    frame: pd.DataFrame,
    coordinate_columns: list[str],
    coordinate_values: list[np.ndarray],
    variable_column: str,
) -> np.ndarray:
    index = pd.MultiIndex.from_frame(frame[coordinate_columns])
    full_index = pd.MultiIndex.from_product(coordinate_values, names=coordinate_columns)
    series = pd.Series(frame[variable_column].to_numpy(), index=index)
    return series.reindex(full_index).to_numpy(dtype="float64").reshape(
        tuple(len(values) for values in coordinate_values)
    )


def _validate_request(request: ConversionRequest, columns: Sequence[str]) -> None:
    if request.latitude_column == request.longitude_column:
        raise ValidationError("Latitude and longitude must use different columns.")
    if not request.variables:
        raise ValidationError("Select at least one variable to export.")
    if request.method not in {NEAREST_NEIGHBOR, AREA_WEIGHTED}:
        raise ValidationError("Select a supported interpolation method.")
    if not np.isfinite(request.output_resolution) or request.output_resolution <= 0:
        raise ValidationError("Output resolution must be a positive number.")
    if request.input_missing_value is not None and not np.isfinite(request.input_missing_value):
        raise ValidationError("Input missing marker must be a finite number.")
    if not (np.isfinite(request.output_fill_value) or np.isnan(request.output_fill_value)):
        raise ValidationError("NetCDF fill value must be finite or NaN.")
    selected_columns = [
        request.latitude_column,
        request.longitude_column,
        *(dimension.column for dimension in request.dimensions),
        *(variable.column for variable in request.variables),
    ]
    missing = [column for column in selected_columns if column not in columns]
    if missing:
        raise ValidationError(f"Missing selected column(s): {', '.join(missing)}")
    if len(selected_columns) != len(set(selected_columns)):
        raise ValidationError("Each coordinate, dimension, and variable must use a different source column.")

    output_names = [dimension.name for dimension in request.dimensions] + [
        variable.name for variable in request.variables
    ]
    reserved = {"latitude", "longitude", "latitude_bounds", "longitude_bounds", "bounds", "crs"}
    for dimension in request.dimensions:
        _validate_name(dimension.name, "Dimension name")
    for variable in request.variables:
        _validate_name(variable.name, "Variable name")
    if len(output_names) != len(set(output_names)):
        raise ValidationError("Output dimension and variable names must be unique.")
    collision = sorted(set(output_names) & reserved)
    if collision:
        raise ValidationError(f"Reserved output name(s): {', '.join(collision)}")


def _build_dataset(request: ConversionRequest, frame: pd.DataFrame, grid: GridInfo) -> xr.Dataset:
    resolution = float(request.output_resolution)
    tolerance = max(grid.latitude_resolution, grid.longitude_resolution) * 1e-8
    if (
        resolution <= grid.latitude_resolution + tolerance
        or resolution <= grid.longitude_resolution + tolerance
    ):
        raise ValidationError(RESOLUTION_ERROR)

    target_latitudes, target_latitude_edges = _target_axis(
        *grid.latitude_bounds, resolution, "Latitude"
    )
    target_longitudes, target_longitude_edges = _target_axis(
        *grid.longitude_bounds, resolution, "Longitude"
    )

    extra_columns = [dimension.column for dimension in request.dimensions]
    extra_names = [dimension.name for dimension in request.dimensions]
    extra_values = [_sorted_unique(frame[column]) for column in extra_columns]
    source_columns = extra_columns + [request.latitude_column, request.longitude_column]
    source_values = extra_values + [grid.latitude_values, grid.longitude_values]
    output_dimensions = tuple(extra_names + ["latitude", "longitude"])
    output_coordinates: dict[str, np.ndarray] = {
        **dict(zip(extra_names, extra_values)),
        "latitude": target_latitudes,
        "longitude": target_longitudes,
    }

    if request.method == NEAREST_NEIGHBOR:
        latitude_indices = _nearest_indices(grid.latitude_values, target_latitudes)
        longitude_indices = _nearest_indices(grid.longitude_values, target_longitudes)
    else:
        source_latitude_edges = np.linspace(
            grid.latitude_bounds[0],
            grid.latitude_bounds[1],
            grid.latitude_count + 1,
        )
        source_longitude_edges = np.linspace(
            grid.longitude_bounds[0],
            grid.longitude_bounds[1],
            grid.longitude_count + 1,
        )
        latitude_weights = _overlap_weights(
            source_latitude_edges, target_latitude_edges, latitude=True
        )
        longitude_weights = _overlap_weights(
            source_longitude_edges, target_longitude_edges, latitude=False
        )

    data_variables: dict[str, xr.DataArray] = {}
    for variable in request.variables:
        source_data = _dense_variable(
            frame,
            source_columns,
            source_values,
            variable.column,
        )
        if request.method == NEAREST_NEIGHBOR:
            output_data = np.take(
                np.take(source_data, latitude_indices, axis=-2),
                longitude_indices,
                axis=-1,
            )
        else:
            output_data = _area_weighted_values(
                source_data,
                latitude_weights,
                longitude_weights,
            )
        attrs = {
            "long_name": variable.description.strip() or variable.name.replace("_", " "),
            "grid_mapping": "crs",
            "coordinates": "latitude longitude",
            "resampling_method": (
                "nearest_neighbor"
                if request.method == NEAREST_NEIGHBOR
                else "spherical_area_weighted_average"
            ),
        }
        if variable.units.strip():
            attrs["units"] = variable.units.strip()
        data_variables[variable.name] = xr.DataArray(
            output_data,
            dims=output_dimensions,
            coords=output_coordinates,
            attrs=attrs,
        )

    dataset = xr.Dataset(data_variables)
    dataset["latitude"].attrs = {
        "standard_name": "latitude",
        "long_name": "latitude",
        "units": "degrees_north",
        "axis": "Y",
        "bounds": "latitude_bounds",
    }
    dataset["longitude"].attrs = {
        "standard_name": "longitude",
        "long_name": "longitude",
        "units": "degrees_east",
        "axis": "X",
        "bounds": "longitude_bounds",
    }
    dataset["latitude_bounds"] = xr.DataArray(
        np.column_stack((target_latitude_edges[:-1], target_latitude_edges[1:])),
        dims=("latitude", "bounds"),
    )
    dataset["longitude_bounds"] = xr.DataArray(
        np.column_stack((target_longitude_edges[:-1], target_longitude_edges[1:])),
        dims=("longitude", "bounds"),
    )
    dataset["crs"] = xr.DataArray(
        np.int32(0),
        attrs={
            "grid_mapping_name": "latitude_longitude",
            "epsg_code": "EPSG:4326",
            "semi_major_axis": 6378137.0,
            "inverse_flattening": 298.257223563,
            "longitude_of_prime_meridian": 0.0,
            "spatial_ref": (
                'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,'
                '298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433],'
                'AUTHORITY["EPSG","4326"]]'
            ),
        },
    )
    for dimension in request.dimensions:
        dataset[dimension.name].attrs["long_name"] = dimension.name.replace("_", " ")

    method_text = (
        "nearest neighbor"
        if request.method == NEAREST_NEIGHBOR
        else "spherical area-weighted average"
    )
    dataset.attrs = {
        "Conventions": "CF-1.8",
        "title": request.description.strip() or "Interpolated gridded dataset",
        "summary": request.description.strip() or "Coarsened from a regular tabular latitude-longitude grid.",
        "source": Path(request.input_path).name,
        "history": (
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} "
            "created by NetCDF Grid Interpolator"
        ),
        "geospatial_lat_min": float(target_latitude_edges[0]),
        "geospatial_lat_max": float(target_latitude_edges[-1]),
        "geospatial_lon_min": float(target_longitude_edges[0]),
        "geospatial_lon_max": float(target_longitude_edges[-1]),
        "geospatial_lat_resolution": resolution,
        "geospatial_lon_resolution": resolution,
        "geospatial_lat_units": "degrees_north",
        "geospatial_lon_units": "degrees_east",
        "resampling_method": method_text,
    }
    return dataset


def convert_to_netcdf(request: ConversionRequest) -> ConversionResult:
    """Validate a request, coarsen selected variables, and atomically write NetCDF."""
    input_path = Path(request.input_path)
    output_path = Path(request.output_path)
    if output_path.suffix.lower() != ".nc":
        raise ValidationError("Output file must use the .nc extension.")
    if input_path.resolve() == output_path.resolve():
        raise ValidationError("Input and output files must be different.")

    columns = read_column_names(input_path)
    _validate_request(request, columns)
    selected_columns = list(
        dict.fromkeys(
            [
                request.latitude_column,
                request.longitude_column,
                *(dimension.column for dimension in request.dimensions),
                *(variable.column for variable in request.variables),
            ]
        )
    )
    frame = _read_table(input_path, usecols=selected_columns)
    if frame.empty:
        raise ValidationError("The input file contains no data rows.")

    frame[request.latitude_column] = _coordinate_series(
        frame[request.latitude_column], request.latitude_column
    )
    frame[request.longitude_column] = _coordinate_series(
        frame[request.longitude_column], request.longitude_column
    )
    for dimension in request.dimensions:
        frame[dimension.column] = _clean_dimension_series(
            frame[dimension.column], dimension.column
        )
    for variable in request.variables:
        frame[variable.column] = _numeric_series(
            frame[variable.column], variable.column, request.input_missing_value
        )

    coordinate_columns = [
        *(dimension.column for dimension in request.dimensions),
        request.latitude_column,
        request.longitude_column,
    ]
    duplicate_rows = frame.duplicated(coordinate_columns, keep=False)
    if duplicate_rows.any():
        raise ValidationError(
            "The selected dimensions contain duplicate coordinate combinations. "
            "Each grid cell must appear once."
        )

    grid = _infer_grid(frame, request.latitude_column, request.longitude_column)
    dataset = _build_dataset(request, frame, grid)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{output_path.stem}_",
            suffix=".nc",
            dir=output_path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
        encoding: dict[str, dict[str, object]] = {
            variable.name: {
                "zlib": True,
                "complevel": 4,
                "shuffle": True,
                "dtype": "float32",
                "_FillValue": np.float32(request.output_fill_value),
            }
            for variable in request.variables
        }
        encoding.update(
            {
                "latitude": {"_FillValue": None},
                "longitude": {"_FillValue": None},
                "latitude_bounds": {"_FillValue": None},
                "longitude_bounds": {"_FillValue": None},
                "crs": {"_FillValue": None},
            }
        )
        dataset.to_netcdf(
            temporary_path,
            engine="netcdf4",
            format="NETCDF4",
            encoding=encoding,
        )
        os.replace(temporary_path, output_path)
        temporary_path = None
    except (OSError, ValueError, RuntimeError) as exc:
        raise ValidationError(f"Could not write the NetCDF file: {exc}") from exc
    finally:
        dataset.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return ConversionResult(
        output_path=output_path,
        input_grid=grid,
        output_latitude_count=dataset.sizes["latitude"],
        output_longitude_count=dataset.sizes["longitude"],
        variable_names=tuple(variable.name for variable in request.variables),
    )
