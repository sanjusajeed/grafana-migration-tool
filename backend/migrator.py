"""Migration orchestration. Order: users -> datasources -> folders -> dashboards -> alerts
-> mute timings -> contact points -> notification policy.
"""
from __future__ import annotations

import copy
import logging
from typing import Any, AsyncIterator

from grafana_client import GrafanaClient, GrafanaError
from models import MigrateItemResult, Selection

logger = logging.getLogger(__name__)

_DS_STRIP = {"id", "orgId", "version", "readOnly"}


def _prep_datasource(ds: dict) -> dict:
    out = {k: v for k, v in ds.items() if k not in _DS_STRIP}
    out.setdefault("secureJsonData", {})
    return out


_RULE_STRIP = {"id", "orgId", "folderUID", "updated", "provenance", "namespace_uid", "namespace_id"}


def _prep_rule_group(group: dict, existing_by_title: dict[str, str] | None = None) -> dict:
    """Prepare a rule group for POST to the target ruler API.

    existing_by_title maps rule title → target UID for rules that already exist
    on the target (found via GET before POST). When a title matches, we use the
    target's UID so Grafana updates the existing rule rather than creating a
    duplicate. For new rules (no title match) we strip the source UID and let
    the target assign a fresh one.
    """
    g = copy.deepcopy(group)
    for rule in g.get("rules", []):
        for key in _RULE_STRIP:
            rule.pop(key, None)
        ga = rule.get("grafana_alert", {})
        for key in _RULE_STRIP:
            ga.pop(key, None)
        if existing_by_title is not None:
            title = ga.get("title", "")
            if title in existing_by_title:
                ga["uid"] = existing_by_title[title]
            else:
                ga.pop("uid", None)
    return g


def _strip_library_panels(dash: dict) -> None:
    count = 0
    for panel in dash.get("panels", []):
        if panel.pop("libraryPanel", None):
            count += 1
        for sub in panel.get("panels", []):
            if sub.pop("libraryPanel", None):
                count += 1
    if count:
        logger.debug("stripped %d libraryPanel reference(s) from dashboard '%s'",
                     count, dash.get("title", "?"))


def _prep_contact_point(cp: dict) -> dict:
    return {k: v for k, v in cp.items() if k != "provenance"}


def _prep_notification_policy(policy: dict, valid_receivers: set[str], fallback: str) -> dict:
    """Strip provenance and fix any receiver name not present on target.

    Grafana auto-creates 'autogen-contact-point-default' internally; it never
    appears in the provisioning API contact-point list. We always replace empty
    or unknown receivers with the target's own default — never popping the key,
    because Grafana re-adds receiver="" as a default if the key is absent.
    """
    _MISSING = object()

    def _fix(node: dict) -> None:
        node.pop("provenance", None)
        recv = node.get("receiver", _MISSING)
        if recv is _MISSING:
            # No receiver key at all — Grafana treats this as receiver=""
            logger.warning(
                "notification policy: route has no receiver key, adding fallback %r",
                fallback,
            )
            node["receiver"] = fallback
        elif not recv or recv not in valid_receivers:
            # None (JSON null), "" (empty string), or unknown name
            logger.warning(
                "notification policy: receiver %r not valid on target, replacing with %r",
                recv, fallback,
            )
            node["receiver"] = fallback
        # guard against routes: null in the JSON
        for route in (node.get("routes") or []):
            _fix(route)

    p = copy.deepcopy(policy)
    _fix(p)
    return p


def _event(kind: str, **payload: Any) -> dict:
    return {"type": kind, **payload}


def _result_event(result: MigrateItemResult, done: int, total: int) -> dict:
    return _event(
        "item",
        result=result.model_dump(),
        progress={"done": done, "total": total},
    )


async def _plan(
    src: GrafanaClient, sel: Selection
) -> tuple[list[dict], list[dict], list[dict], list[tuple[str, dict]], list[dict]]:
    """Return (users, datasources, dashboards, alert_groups, contact_points)."""
    user_chosen: list[dict] = []
    ds_chosen: list[dict] = []
    dash_chosen: list[dict] = []
    alert_chosen: list[tuple[str, dict]] = []
    cp_chosen: list[dict] = []

    if sel.all_users or sel.users:
        try:
            all_users = await src.list_org_users()
            selected_logins = set(sel.users)
            user_chosen = (
                [u for u in all_users if u.get("login") != "admin"]
                if sel.all_users
                else [u for u in all_users if u.get("login") in selected_logins]
            )
            logger.info("plan: %d user(s) selected", len(user_chosen))
        except GrafanaError as e:
            logger.warning("could not list org users: %s", e)

    if sel.all_datasources or sel.datasources:
        all_ds = await src.list_datasources()
        ds_chosen = (
            all_ds
            if sel.all_datasources
            else [
                d for d in all_ds
                if d.get("uid") in sel.datasources or d.get("name") in sel.datasources
            ]
        )
        logger.info("plan: %d datasource(s) selected", len(ds_chosen))

    if sel.all_dashboards or sel.dashboards:
        search = await src.search_dashboards()
        dash_chosen = (
            search if sel.all_dashboards
            else [d for d in search if d.get("uid") in sel.dashboards]
        )
        logger.info("plan: %d dashboard(s) selected", len(dash_chosen))

    if sel.all_alerts or sel.alerts:
        try:
            rules = await src.list_alert_rules()
        except GrafanaError:
            rules = {}
        selected_keys = set(sel.alerts)
        for namespace, groups in (rules or {}).items():
            for group in groups:
                key = f"{namespace}::{group.get('name')}"
                if sel.all_alerts or key in selected_keys:
                    alert_chosen.append((namespace, group))
        logger.info("plan: %d alert group(s) selected", len(alert_chosen))

    if sel.all_contact_points or sel.contact_points or sel.notification_policy:
        try:
            all_cps = await src.list_contact_points()
            if sel.all_contact_points or sel.notification_policy:
                # notification_policy requires all contact points to exist on target
                cp_chosen = all_cps
            else:
                selected_uids = set(sel.contact_points)
                cp_chosen = [cp for cp in all_cps if cp.get("uid") in selected_uids]
            logger.info("plan: %d contact point(s) selected", len(cp_chosen))
        except GrafanaError as e:
            logger.warning("could not list contact points: %s", e)

    return user_chosen, ds_chosen, dash_chosen, alert_chosen, cp_chosen


async def _ensure_folder(
    tgt: GrafanaClient,
    target_folders: dict[str, dict],
    title: str | None,
    uid: str | None,
) -> str | None:
    if not title or title == "General":
        return None
    if uid and uid in target_folders:
        logger.debug("folder '%s' found on target by uid=%s", title, uid)
        return uid
    for f in target_folders.values():
        if f.get("title") == title:
            found_uid = f.get("uid")
            logger.debug("folder '%s' found on target by title, uid=%s", title, found_uid)
            return found_uid
    logger.info("folder '%s' not found on target — creating", title)
    try:
        created = await tgt.create_folder(title=title, uid=uid)
    except GrafanaError as e:
        if e.status in (409, 412):
            logger.warning("folder '%s' conflict (%s), retrying without uid", title, e.status)
            created = await tgt.create_folder(title=title)
        else:
            raise
    new_uid = created.get("uid")
    logger.info("folder '%s' created on target with uid=%s", title, new_uid)
    target_folders[new_uid] = created
    return new_uid


async def run_migration_stream(
    source_cfg: dict,
    target_cfg: dict,
    selection: Selection,
    on_conflict: str = "update",
) -> AsyncIterator[dict]:
    summary = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}

    async with GrafanaClient(source_cfg["url"], source_cfg["token"]) as src, \
               GrafanaClient(target_cfg["url"], target_cfg["token"]) as tgt:

        user_list, ds_list, dash_list, alert_list, cp_list = await _plan(src, selection)

        notif_policy_count = 1 if selection.notification_policy else 0
        total = (
            len(user_list) + len(ds_list) + len(dash_list) + len(alert_list)
            + len(cp_list) + notif_policy_count
        )
        done = 0

        logger.info(
            "migration starting: %d user(s), %d datasource(s), %d dashboard(s), "
            "%d alert group(s), %d contact point(s), notification_policy=%s",
            len(user_list), len(ds_list), len(dash_list),
            len(alert_list), len(cp_list), selection.notification_policy,
        )

        yield _event(
            "plan",
            totals={
                "users": len(user_list),
                "datasources": len(ds_list),
                "dashboards": len(dash_list),
                "alerts": len(alert_list),
                "contact_points": len(cp_list),
                "notification_policy": notif_policy_count,
                "total": total,
            },
        )

        # ----- users -----
        # Pre-fetch all existing target org users once to avoid per-user lookup
        # (lookup endpoint requires users:read permission; list_org_users only needs Org Admin)
        tgt_users_by_login: dict[str, dict] = {}
        if user_list:
            try:
                tgt_org_users = await tgt.list_org_users()
                # org/users response uses "userId" for the numeric id
                tgt_users_by_login = {u.get("login"): u for u in tgt_org_users if u.get("login")}
                logger.info("fetched %d existing user(s) from target org", len(tgt_users_by_login))
            except GrafanaError as e:
                logger.warning("could not fetch target org users: %s", e)

        for u in user_list:
            login = u.get("login", "")
            name = u.get("name") or login
            email = u.get("email", "")
            role = u.get("role", "Viewer")
            logger.debug("user '%s': checking target", login)
            try:
                existing = tgt_users_by_login.get(login)
                if existing:
                    user_id = existing.get("userId")
                    await tgt.update_org_user_role(user_id, role)
                    logger.info("user '%s': updated role to %s", login, role)
                    r = MigrateItemResult(kind="user", name=login, status="updated")
                else:
                    # Use invite (sendEmail=false) — only requires Org Admin.
                    # When the user logs in via Azure AD, Grafana matches by email
                    # and assigns the role from the invite automatically.
                    login_or_email = email if email else login
                    await tgt.invite_user(login_or_email, name, role)
                    logger.info("user '%s': invited with role %s (will activate on first login)", login, role)
                    r = MigrateItemResult(kind="user", name=login, status="created",
                                          message=f"Invited as {role} — activates on first Azure AD login")
            except GrafanaError as e:
                logger.error("user '%s': FAILED — %s", login, e)
                r = MigrateItemResult(kind="user", name=login, status="failed", message=str(e))
            done += 1
            summary[r.status] = summary.get(r.status, 0) + 1
            yield _result_event(r, done, total)

        # ----- datasources -----
        for ds in ds_list:
            name = ds.get("name", "?")
            payload = _prep_datasource(ds)
            logger.debug("datasource '%s': checking target", name)
            try:
                existing = await tgt.get_datasource_by_name(name)
                if existing:
                    if on_conflict == "skip":
                        logger.info("datasource '%s': skipped (exists, on_conflict=skip)", name)
                        r = MigrateItemResult(
                            kind="datasource", name=name, uid=existing.get("uid"),
                            status="skipped", message="already exists",
                        )
                    else:
                        payload["id"] = existing["id"]
                        payload["uid"] = existing.get("uid", payload.get("uid"))
                        await tgt.update_datasource(existing["uid"], payload)
                        logger.info("datasource '%s': updated (uid=%s)", name, existing.get("uid"))
                        r = MigrateItemResult(
                            kind="datasource", name=name, uid=existing.get("uid"),
                            status="updated",
                        )
                else:
                    created = await tgt.create_datasource(payload)
                    created_ds = created.get("datasource", {}) if isinstance(created, dict) else {}
                    logger.info("datasource '%s': created (uid=%s)", name, created_ds.get("uid"))
                    r = MigrateItemResult(
                        kind="datasource", name=name, uid=created_ds.get("uid"),
                        status="created",
                    )
            except GrafanaError as e:
                logger.error("datasource '%s': FAILED — %s", name, e)
                r = MigrateItemResult(
                    kind="datasource", name=name, status="failed", message=str(e),
                )
            done += 1
            summary[r.status] = summary.get(r.status, 0) + 1
            yield _result_event(r, done, total)

        # ----- dashboards (with folder creation) -----
        target_folders: dict[str, dict] = {}
        try:
            tgt_folders_list = await tgt.get_folders()
            target_folders = {f.get("uid"): f for f in tgt_folders_list if f.get("uid")}
            logger.info("fetched %d existing folder(s) from target", len(target_folders))
        except GrafanaError as e:
            logger.warning("could not fetch target folders: %s — folder creation may duplicate", e)
            target_folders = {}

        for item in dash_list:
            uid = item.get("uid")
            title = item.get("title", uid or "?")
            logger.debug("dashboard '%s' (uid=%s): fetching from source", title, uid)
            try:
                full = await src.get_dashboard(uid)
                dash = full.get("dashboard", {})
                meta = full.get("meta", {})
                dash["id"] = None
                _strip_library_panels(dash)
                folder_title = meta.get("folderTitle")
                folder_uid = await _ensure_folder(
                    tgt, target_folders,
                    folder_title, meta.get("folderUid"),
                )
                overwrite = on_conflict == "update"
                logger.debug("dashboard '%s': upserting into folder '%s' (uid=%s), overwrite=%s",
                             title, folder_title, folder_uid, overwrite)
                try:
                    await tgt.upsert_dashboard(dash, folder_uid=folder_uid, overwrite=overwrite)
                    status = "updated" if overwrite else "created"
                    logger.info("dashboard '%s' (uid=%s): %s", title, uid, status)
                    r = MigrateItemResult(kind="dashboard", name=title, uid=uid, status=status)
                except GrafanaError as e:
                    if e.status in (409, 412) and on_conflict == "skip":
                        logger.info("dashboard '%s': skipped (exists, on_conflict=skip)", title)
                        r = MigrateItemResult(
                            kind="dashboard", name=title, uid=uid,
                            status="skipped", message="exists, on_conflict=skip",
                        )
                    else:
                        raise
            except GrafanaError as e:
                logger.error("dashboard '%s' (uid=%s): FAILED — %s", title, uid, e)
                r = MigrateItemResult(
                    kind="dashboard", name=title, uid=uid, status="failed", message=str(e),
                )
            done += 1
            summary[r.status] = summary.get(r.status, 0) + 1
            yield _result_event(r, done, total)

        # ----- alert rule groups -----
        if alert_list:
            try:
                await tgt.list_alert_rules()
                logger.info("target ruler API is reachable — unified alerting is enabled")
            except GrafanaError as e:
                if e.status == 404:
                    msg = (
                        "Target Grafana ruler API returned 404. "
                        "Unified alerting is likely disabled on the target. "
                        "Set [unified_alerting] enabled=true and [alerting] enabled=false "
                        "in grafana.ini on the target, then restart Grafana."
                    )
                    logger.error(msg)
                    for namespace, group in alert_list:
                        key = f"{namespace}::{group.get('name', '?')}"
                        r = MigrateItemResult(
                            kind="alert", name=key, status="failed",
                            message="ruler API unavailable — enable unified alerting on target",
                        )
                        done += 1
                        summary["failed"] = summary.get("failed", 0) + 1
                        yield _result_event(r, done, total)
                    yield _event("done", summary=summary, total=total)
                    return
                else:
                    logger.warning("target ruler API preflight check failed (%s) — proceeding anyway", e.status)

        for namespace, group in alert_list:
            group_name = group.get("name", "?")
            key = f"{namespace}::{group_name}"
            logger.debug("alert group '%s': namespace='%s', %d rule(s)",
                         group_name, namespace, len(group.get("rules", [])))
            try:
                await _ensure_folder(tgt, target_folders, namespace, None)
                # Fetch existing rules in this group on the target to build a
                # title→UID map. Using target UIDs avoids "cannot find rule"
                # errors when re-running migration (previous run may have
                # auto-generated different UIDs than the source).
                existing_by_title: dict[str, str] = {}
                try:
                    tgt_group = await tgt.get_rule_group(namespace, group_name)
                    if tgt_group:
                        for r in tgt_group.get("rules", []):
                            ga = r.get("grafana_alert", {})
                            t, u = ga.get("title", ""), ga.get("uid", "")
                            if t and u:
                                existing_by_title[t] = u
                        logger.debug("alert group '%s': found %d existing rule(s) on target",
                                     group_name, len(existing_by_title))
                except GrafanaError:
                    pass
                logger.info("alert group '%s': posting to namespace (title) '%s'",
                            group_name, namespace)
                await tgt.post_rule_group(namespace, _prep_rule_group(group, existing_by_title))
                logger.info("alert group '%s': posted successfully", group_name)
                r = MigrateItemResult(kind="alert", name=key, status="updated")
            except GrafanaError as e:
                logger.error("alert group '%s': FAILED — status=%s message=%s",
                             group_name, e.status, e.message)
                r = MigrateItemResult(kind="alert", name=key, status="failed", message=str(e))
            done += 1
            summary[r.status] = summary.get(r.status, 0) + 1
            yield _result_event(r, done, total)

        # ----- mute timings (auto when notification_policy selected) -----
        if selection.notification_policy:
            try:
                mute_timings = await src.list_mute_timings()
                logger.info("migrating %d mute timing(s)", len(mute_timings))
                for mt in mute_timings:
                    mt_name = mt.get("name", "?")
                    try:
                        try:
                            await tgt.put_mute_timing(mt_name, mt)
                            logger.info("mute timing '%s': upserted", mt_name)
                            r = MigrateItemResult(kind="mute_timing", name=mt_name, status="updated")
                        except GrafanaError as e:
                            if e.status == 404:
                                await tgt.create_mute_timing(mt)
                                logger.info("mute timing '%s': created", mt_name)
                                r = MigrateItemResult(kind="mute_timing", name=mt_name, status="created")
                            else:
                                raise
                    except GrafanaError as e:
                        logger.error("mute timing '%s': FAILED — %s", mt_name, e)
                        r = MigrateItemResult(kind="mute_timing", name=mt_name,
                                              status="failed", message=str(e))
                    summary[r.status] = summary.get(r.status, 0) + 1
            except GrafanaError as e:
                logger.warning("could not fetch mute timings from source: %s", e)

        # ----- contact points -----
        if cp_list:
            try:
                tgt_cps = await tgt.list_contact_points()
                tgt_by_uid = {cp.get("uid"): cp for cp in tgt_cps if cp.get("uid")}
            except GrafanaError as e:
                logger.warning("could not fetch target contact points: %s", e)
                tgt_by_uid = {}

        for cp in cp_list:
            cp_uid = cp.get("uid", "")
            cp_name = cp.get("name", cp_uid)
            prepped = _prep_contact_point(cp)
            try:
                if cp_uid in tgt_by_uid:
                    await tgt.update_contact_point(cp_uid, prepped)
                    logger.info("contact point '%s' (uid=%s): updated", cp_name, cp_uid)
                    r = MigrateItemResult(kind="contact_point", name=cp_name, uid=cp_uid, status="updated")
                else:
                    await tgt.create_contact_point(prepped)
                    logger.info("contact point '%s' (uid=%s): created", cp_name, cp_uid)
                    r = MigrateItemResult(kind="contact_point", name=cp_name, uid=cp_uid, status="created")
            except GrafanaError as e:
                logger.error("contact point '%s': FAILED — %s", cp_name, e)
                r = MigrateItemResult(kind="contact_point", name=cp_name,
                                      status="failed", message=str(e))
            done += 1
            summary[r.status] = summary.get(r.status, 0) + 1
            yield _result_event(r, done, total)

        # ----- notification policy -----
        if selection.notification_policy:
            try:
                policy = await src.get_notification_policy()

                # Build the set of receiver names that exist on the target.
                # Also grab the target's current default receiver as a fallback
                # for any internal receivers (e.g. 'autogen-contact-point-default')
                # that Grafana creates automatically and are not exposed by the
                # provisioning API.
                tgt_cp_names: set[str] = set()
                tgt_fallback_receiver = ""
                try:
                    tgt_cps = await tgt.list_contact_points()
                    tgt_cp_names = {cp.get("name", "") for cp in tgt_cps}
                    tgt_policy_current = await tgt.get_notification_policy()
                    tgt_fallback_receiver = tgt_policy_current.get("receiver", "")
                    # Also include the fallback itself as valid
                    if tgt_fallback_receiver:
                        tgt_cp_names.add(tgt_fallback_receiver)
                    logger.debug("target contact point names: %s", tgt_cp_names)
                except GrafanaError as e:
                    logger.warning("could not fetch target contact points for policy validation: %s", e)

                import json as _json
                logger.debug("source notification policy (raw): %s", _json.dumps(policy))
                prepped = _prep_notification_policy(policy, tgt_cp_names, tgt_fallback_receiver)
                logger.debug("prepped notification policy: %s", _json.dumps(prepped))
                await tgt.put_notification_policy(prepped)
                logger.info("notification policy: migrated successfully")
                r = MigrateItemResult(kind="notification_policy", name="notification_policy", status="updated")
            except GrafanaError as e:
                logger.error("notification policy: FAILED — %s", e)
                r = MigrateItemResult(kind="notification_policy", name="notification_policy",
                                      status="failed", message=str(e))
            done += 1
            summary[r.status] = summary.get(r.status, 0) + 1
            yield _result_event(r, done, total)

        logger.info("migration done: created=%d updated=%d skipped=%d failed=%d",
                    summary["created"], summary["updated"], summary["skipped"], summary["failed"])
        yield _event("done", summary=summary, total=total)
