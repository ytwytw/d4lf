"""Persist the exact build selection independently of a profile's filename."""

from pydantic import BaseModel, ConfigDict


class BuildSourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    url: str
    variant_id: str | None = None
    variant_name: str = ""
    build_title: str = ""
    class_name: str = ""
    season: str = ""
    imported_at: str = ""
