"""Grafana REST API client.

Handles authenticated calls to a Grafana instance. Used for both source
(read-only) and target (read + write) during migration.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class GrafanaError(Exception):
    def __init__(self, status: int, message: str, payload: Any = None):
        super().__init__(f"[{status}] {message}")
        self.status = status
        self.message = message
        self.payload = payload


class GrafanaClient:
    def __init__(self, base_url: str, token: str, timeout: float = 60.0):
        if not base_url:
            raise ValueError("Grafana base_url is required")
        if not token:
            raise ValueError("Grafana API token is required")
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=timeout,
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "GrafanaClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            r = await self._client.request(method, path, **kwargs)
        except httpx.RequestError as e:
            raise GrafanaError(0, f"network error: {e}") from e

        if r.status_code >= 400:
            try:
                payload = r.json()
                msg = payload.get("message") or payload.get("error") or r.text
            except Exception:
                payload = r.text
                msg = r.text
            raise GrafanaError(r.status_code, msg, payload)

        if not r.content:
            return None
        try:
            return r.json()
        except Exception:
            return r.text

    # ---------- health ----------
    async def health(self) -> dict:
        return await self._request("GET", "/api/health")

    # ---------- dashboards ----------
    async def search_dashboards(self) -> list[dict]:
        return await self._request(
            "GET", "/api/search", params={"type": "dash-db", "limit": 5000}
        )

    async def get_dashboard(self, uid: str) -> dict:
        return await self._request("GET", f"/api/dashboards/uid/{uid}")

    async def get_folders(self) -> list[dict]:
        return await self._request("GET", "/api/folders")

    async def create_folder(self, title: str, uid: str | None = None) -> dict:
        body = {"title": title}
        if uid:
            body["uid"] = uid
        return await self._request("POST", "/api/folders", json=body)

    async def upsert_dashboard(
        self, dashboard: dict, folder_uid: str | None, overwrite: bool = True
    ) -> dict:
        body: dict[str, Any] = {
            "dashboard": dashboard,
            "overwrite": overwrite,
            "message": "Migrated via grafana-migration tool",
        }
        if folder_uid:
            body["folderUid"] = folder_uid
        return await self._request("POST", "/api/dashboards/db", json=body)

    # ---------- datasources ----------
    async def list_datasources(self) -> list[dict]:
        return await self._request("GET", "/api/datasources")

    async def get_datasource_by_name(self, name: str) -> dict | None:
        try:
            return await self._request("GET", f"/api/datasources/name/{name}")
        except GrafanaError as e:
            if e.status == 404:
                return None
            raise

    async def create_datasource(self, ds: dict) -> dict:
        return await self._request("POST", "/api/datasources", json=ds)

    async def update_datasource(self, uid: str, ds: dict) -> dict:
        return await self._request("PUT", f"/api/datasources/uid/{uid}", json=ds)

    # ---------- alert rules (Grafana-managed, unified alerting) ----------
    async def list_alert_rules(self) -> dict:
        """Returns {namespace: [{interval, rules: [...]}, ...]}."""
        return await self._request("GET", "/api/ruler/grafana/api/v1/rules")

    async def get_rule_group(self, namespace: str, group_name: str) -> dict | None:
        from urllib.parse import quote
        try:
            return await self._request(
                "GET",
                f"/api/ruler/grafana/api/v1/rules/{quote(namespace, safe='')}/{quote(group_name, safe='')}",
            )
        except GrafanaError as e:
            if e.status == 404:
                return None
            raise

    async def post_rule_group(self, namespace: str, group: dict) -> Any:
        from urllib.parse import quote

        return await self._request(
            "POST",
            f"/api/ruler/grafana/api/v1/rules/{quote(namespace, safe='')}",
            json=group,
        )

    # ---------- users ----------
    async def list_org_users(self) -> list[dict]:
        return await self._request("GET", "/api/org/users", params={"perpage": 1000})

    async def lookup_user(self, login_or_email: str) -> dict | None:
        try:
            return await self._request(
                "GET", "/api/users/lookup", params={"loginOrEmail": login_or_email}
            )
        except GrafanaError as e:
            if e.status == 404:
                return None
            raise

    async def invite_user(self, login_or_email: str, name: str, role: str) -> dict:
        """Add a user to the org via invite (sendEmail=false). Requires only Org Admin.
        When the user first logs in (e.g. via Azure AD), Grafana matches by email
        and assigns the specified role."""
        return await self._request(
            "POST", "/api/org/invites",
            json={"loginOrEmail": login_or_email, "name": name, "role": role, "sendEmail": False},
        )

    async def create_user(self, payload: dict) -> dict:
        """Requires Grafana Server Admin (users:create). Falls back to invite_user if 403."""
        return await self._request("POST", "/api/admin/users", json=payload)

    async def update_org_user_role(self, user_id: int, role: str) -> None:
        await self._request("PATCH", f"/api/org/users/{user_id}", json={"role": role})

    # ---------- contact points ----------
    async def list_contact_points(self) -> list[dict]:
        return await self._request("GET", "/api/v1/provisioning/contact-points")

    async def create_contact_point(self, cp: dict) -> dict:
        return await self._request("POST", "/api/v1/provisioning/contact-points", json=cp)

    async def update_contact_point(self, uid: str, cp: dict) -> dict:
        return await self._request(
            "PUT", f"/api/v1/provisioning/contact-points/{uid}", json=cp
        )

    # ---------- notification policy ----------
    async def get_notification_policy(self) -> dict:
        return await self._request("GET", "/api/v1/provisioning/policies")

    async def put_notification_policy(self, policy: dict) -> dict:
        return await self._request("PUT", "/api/v1/provisioning/policies", json=policy)

    # ---------- mute timings ----------
    async def list_mute_timings(self) -> list[dict]:
        return await self._request("GET", "/api/v1/provisioning/mute-timings")

    async def create_mute_timing(self, mt: dict) -> dict:
        return await self._request("POST", "/api/v1/provisioning/mute-timings", json=mt)

    async def put_mute_timing(self, name: str, mt: dict) -> None:
        from urllib.parse import quote
        await self._request(
            "PUT", f"/api/v1/provisioning/mute-timings/{quote(name, safe='')}", json=mt
        )
