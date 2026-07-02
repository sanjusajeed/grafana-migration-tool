from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class GrafanaConfig(BaseModel):
    url: str = Field(..., description="Base URL, e.g. http://host:3000")
    token: str = Field(..., description="Bearer API token / service account token")


class FetchRequest(BaseModel):
    source: GrafanaConfig


class Selection(BaseModel):
    dashboards: list[str] = Field(default_factory=list, description="Dashboard UIDs")
    datasources: list[str] = Field(default_factory=list, description="Datasource UIDs or names")
    alerts: list[str] = Field(default_factory=list, description="Rule group keys: 'namespace::group'")
    all_dashboards: bool = False
    all_datasources: bool = False
    all_alerts: bool = False

    users: list[str] = Field(default_factory=list, description="User logins")
    all_users: bool = False

    contact_points: list[str] = Field(default_factory=list, description="Contact point UIDs")
    all_contact_points: bool = False

    notification_policy: bool = False  # migrate full policy tree + mute timings


class MigrateRequest(BaseModel):
    source: GrafanaConfig
    target: GrafanaConfig
    selection: Selection
    on_conflict: Literal["skip", "update"] = "update"


class MigrateItemResult(BaseModel):
    kind: Literal[
        "datasource", "folder", "dashboard", "alert",
        "user", "contact_point", "mute_timing", "notification_policy",
    ]
    name: str
    uid: Optional[str] = None
    status: Literal["created", "updated", "skipped", "failed"]
    message: Optional[str] = None


class MigrateResponse(BaseModel):
    ok: bool
    results: list[MigrateItemResult]
    summary: dict
