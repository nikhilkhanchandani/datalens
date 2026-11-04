"""Pydantic models for cleaning requests and transformation results.

Requests are a discriminated union on `operation`: each operation has its own
model with only the fields it needs, and unknown fields are rejected. Pydantic
enforces shape and simple rules here; column- and type-dependent rules (is the
column numeric? does the custom value parse?) are checked in
`services/cleaner.py`, because they depend on the data.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

FillStrategy = Literal["mean", "median", "mode", "custom", "remove_rows"]
ConversionTarget = Literal["numeric", "datetime", "boolean", "string"]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FillMissingRequest(_Request):
    operation: Literal["fill_missing"]
    column: str
    strategy: FillStrategy
    # Used only when strategy == "custom". Type is checked against the column.
    value: float | str | bool | None = None


class RemoveDuplicatesRequest(_Request):
    operation: Literal["remove_duplicates"]
    # None means "rows identical across every column".
    subset: list[str] | None = Field(default=None, min_length=1)


class NormalizeTextRequest(_Request):
    operation: Literal["normalize_text"]
    columns: list[str] = Field(min_length=1)
    trim: bool = True
    blank_to_missing: bool = True


class DropColumnsRequest(_Request):
    operation: Literal["drop_columns"]
    columns: list[str] = Field(min_length=1)


class RenameColumnRequest(_Request):
    operation: Literal["rename_column"]
    column: str
    new_name: str


class ConvertTypeRequest(_Request):
    operation: Literal["convert_type"]
    column: str
    target: ConversionTarget


CleaningRequest = Annotated[
    Union[
        FillMissingRequest,
        RemoveDuplicatesRequest,
        NormalizeTextRequest,
        DropColumnsRequest,
        RenameColumnRequest,
        ConvertTypeRequest,
    ],
    Field(discriminator="operation"),
]

OPERATION_MODELS: dict[str, type[_Request]] = {
    "fill_missing": FillMissingRequest,
    "remove_duplicates": RemoveDuplicatesRequest,
    "normalize_text": NormalizeTextRequest,
    "drop_columns": DropColumnsRequest,
    "rename_column": RenameColumnRequest,
    "convert_type": ConvertTypeRequest,
}


class TransformationResult(BaseModel):
    operation: str
    column: str | None = None
    strategy: str | None = None
    # Columns involved: dropped, normalized, or renamed (old, new).
    columns: list[str] = Field(default_factory=list)
    # Rows whose data changed or that were removed. Dropping a column counts
    # every row; renaming changes no data, so it counts zero.
    affected_rows: int
    rows_before: int
    rows_after: int
    summary: str
    working_version: int
