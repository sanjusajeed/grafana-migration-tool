"""FastAPI app exposing Grafana migration endpoints."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import json

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from grafana_client import GrafanaClient, GrafanaError
from migrator import run_migration_stream
from models import (
    FetchRequest,
    GrafanaConfig,
    MigrateRequest,
)

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "DEBUG"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("grafana-migration")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Grafana Migration API starting")
    yield
    logger.info("Grafana Migration API shutting down")


app = FastAPI(title="Grafana Migration API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _handle_grafana_error(e: GrafanaError) -> HTTPException:
    status = e.status if 400 <= e.status < 600 else 502
    return HTTPException(status_code=status, detail=e.message)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/verify")
async def verify(cfg: GrafanaConfig):
    """Check that a given URL + token works by hitting /api/health."""
    try:
        async with GrafanaClient(cfg.url, cfg.token) as g:
            h = await g.health()
        return {"ok": True, "grafana": h}
    except GrafanaError as e:
        raise _handle_grafana_error(e)


@app.post("/fetch/dashboards")
async def fetch_dashboards(req: FetchRequest):
    try:
        async with GrafanaClient(req.source.url, req.source.token) as g:
            items = await g.search_dashboards()
        return [
            {
                "uid": d.get("uid"),
                "title": d.get("title"),
                "folder": d.get("folderTitle", "General"),
                "tags": d.get("tags", []),
                "url": d.get("url"),
            }
            for d in items
        ]
    except GrafanaError as e:
        raise _handle_grafana_error(e)


@app.post("/fetch/datasources")
async def fetch_datasources(req: FetchRequest):
    try:
        async with GrafanaClient(req.source.url, req.source.token) as g:
            items = await g.list_datasources()
        return [
            {
                "uid": d.get("uid"),
                "name": d.get("name"),
                "type": d.get("type"),
                "url": d.get("url"),
                "isDefault": d.get("isDefault", False),
            }
            for d in items
        ]
    except GrafanaError as e:
        raise _handle_grafana_error(e)


@app.post("/fetch/users")
async def fetch_users(req: FetchRequest):
    try:
        async with GrafanaClient(req.source.url, req.source.token) as g:
            items = await g.list_org_users()
        return [
            {
                "login": u.get("login"),
                "name": u.get("name") or u.get("login"),
                "email": u.get("email", ""),
                "role": u.get("role", "Viewer"),
            }
            for u in items
            if u.get("login") != "admin"
        ]
    except GrafanaError as e:
        if e.status == 403:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Access denied fetching users. The source API token requires "
                    "Org Admin or Server Admin role. Please use an Admin-level "
                    "API token or service account on the source Grafana."
                ),
            )
        raise _handle_grafana_error(e)


@app.post("/fetch/contact-points")
async def fetch_contact_points(req: FetchRequest):
    try:
        async with GrafanaClient(req.source.url, req.source.token) as g:
            items = await g.list_contact_points()
        return [
            {
                "uid": cp.get("uid"),
                "name": cp.get("name"),
                "type": cp.get("type"),
            }
            for cp in items
        ]
    except GrafanaError as e:
        if e.status == 403:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Access denied fetching contact points. The source API token requires "
                    "Org Admin role to read alerting configuration. Please use an "
                    "Admin-level API token or service account on the source Grafana."
                ),
            )
        raise _handle_grafana_error(e)


@app.post("/fetch/alerts")
async def fetch_alerts(req: FetchRequest):
    try:
        async with GrafanaClient(req.source.url, req.source.token) as g:
            rules = await g.list_alert_rules()
        out = []
        for namespace, groups in (rules or {}).items():
            for group in groups:
                out.append({
                    "key": f"{namespace}::{group.get('name')}",
                    "namespace": namespace,
                    "group": group.get("name"),
                    "interval": group.get("interval"),
                    "ruleCount": len(group.get("rules", [])),
                })
        return out
    except GrafanaError as e:
        raise _handle_grafana_error(e)


@app.post("/migrate")
async def migrate(req: MigrateRequest):
    """Streams NDJSON progress events.

    Event types:
      plan  → {"type":"plan","totals":{"datasources":N,"dashboards":N,"alerts":N,"total":N}}
      item  → {"type":"item","result":{...},"progress":{"done":X,"total":Y}}
      done  → {"type":"done","summary":{"created":N,"updated":N,"skipped":N,"failed":N}}
      error → {"type":"error","message":"..."}
    """
    async def gen():
        try:
            async for evt in run_migration_stream(
                source_cfg=req.source.model_dump(),
                target_cfg=req.target.model_dump(),
                selection=req.selection,
                on_conflict=req.on_conflict,
            ):
                yield json.dumps(evt) + "\n"
        except GrafanaError as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"
        except Exception as e:
            logger.exception("migration failed")
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
