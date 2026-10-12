"""Core services for the NetCDF Grid Interpolator."""

from .converter import (
    AREA_WEIGHTED,
    NEAREST_NEIGHBOR,
    RESOLUTION_ERROR,
    ConversionRequest,
    ConversionResult,
    DimensionSpec,
    GridInfo,
    ValidationError,
    VariableSpec,
    convert_to_netcdf,
    inspect_grid,
    read_column_names,
    safe_netcdf_name,
)

__all__ = [
    "AREA_WEIGHTED",
    "NEAREST_NEIGHBOR",
    "RESOLUTION_ERROR",
    "ConversionRequest",
    "ConversionResult",
    "DimensionSpec",
    "GridInfo",
    "ValidationError",
    "VariableSpec",
    "convert_to_netcdf",
    "inspect_grid",
    "read_column_names",
    "safe_netcdf_name",
]
