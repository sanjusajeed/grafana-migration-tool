# Grafana Migration Tool

API-driven migration utility for copying **users → datasources → dashboards → alert rules → mute timings → contact points → notification policy** from one Grafana instance to another. Uses only the Grafana REST API — no direct DB access required on either side.

- **Backend:** FastAPI (Python 3.10+)
- **Frontend:** React + Vite + Tailwind CSS
- **Transport:** HTTPS/HTTP with Bearer token auth
- **Streaming:** Live progress via NDJSON streaming response

---

## What gets migrated

| Item | Notes |
|------|-------|
| **Users** | Pre-creates users via org invite (`POST /api/org/invites`). Azure AD users auto-provision on first login with the correct role. Existing users get their role updated. Built-in `admin` is skipped. |
| **Datasources** | Full config copied; **secrets are not migrated** (re-enter credentials after migration). |
| **Dashboards** | Folders are created automatically. Library panel references are stripped to avoid import errors. |
| **Alert rule groups** | Re-migration safe: existing rule UIDs are looked up by title on the target so rules are updated, not duplicated. |
| **Mute timings** | Auto-included when Notification policy is selected. |
| **Contact points** | Migrated by UID; existing entries are updated, new ones are created. |
| **Notification policy** | Full routing tree copied. Internal Grafana receivers (`autogen-contact-point-default`) and routes with missing/null receivers are automatically replaced with the target's default receiver. |

**Not migrated:** datasource secrets, folder permissions, teams, org-level API keys, annotations, dashboard version history, playlists, library panels.

---

## Prerequisites

### Source Grafana
- Service Account with **Admin** role (required for `/api/org/users`, `/api/v1/provisioning/*`, alert rules).
- `Administration` → `Service accounts` → **Add service account** → role `Admin` → **Add service account token**.

### Target Grafana
- Service Account with **Admin** role (for creating folders, dashboards, datasources, contact points, policies).
- Same steps as above on the target instance.
- **Note:** User creation uses the org invite API (`POST /api/org/invites`), which only requires Org Admin — Grafana Server Admin is NOT needed.

### Runtime
- Python 3.10+
- Node 18+

---

## Running locally

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional — set LOG_LEVEL=INFO to reduce noise
python main.py
```

Backend listens on `http://localhost:8000`. Swagger UI: `http://localhost:8000/docs`.

### 2. Frontend

```bash
cd frontend
cp .env.example .env   # edit VITE_API_BASE if backend isn't on localhost:8000
npm install
npm run dev
```

Open `http://localhost:5173`.

---

## Using the UI

1. **Configure** source and target Grafana URLs + tokens in the Config panel.
2. Click **Fetch from source** — all sections populate automatically.
3. Select the items to migrate in each section (or use **Select all / Clear**):
   - **Users** — shows login, display name, and role.
   - **Datasources** — shows name, type, and whether it's the default.
   - **Dashboards** — shows title and folder.
   - **Alert rule groups** — shows group name, folder namespace, rule count, and interval.
   - **Contact points** — shows name and type (Teams, email, OpsGenie, etc.).
   - **Notification policy** — single checkbox; automatically includes all contact points and mute timings.
4. Pick **On conflict** → `update` (overwrite existing) or `skip` (leave existing untouched).
5. Click **Start migration**. Live progress streams per-item results with status badges.

Migration always runs in order: **users → datasources → folders → dashboards → alerts → mute timings → contact points → notification policy**. This preserves all cross-object references.

---

## Azure AD / SSO user migration

Because Azure AD handles authentication externally, passwords can't be set by the tool. Instead, users are pre-registered via Grafana's invite API:

- `POST /api/org/invites` with `sendEmail: false`
- When the user logs in for the first time via Azure AD SSO, Grafana matches their email to the pending invite and assigns the configured role (Viewer / Editor / Admin).
- If the user already exists on the target, only their role is updated.

This approach requires only **Org Admin** on the target — not Grafana Server Admin.

---

## API reference

All endpoints accept and return JSON. Source/target credentials are passed in the request body and never stored.

### `GET /health`
```json
{ "status": "ok" }
```

### `POST /verify`
```json
{ "url": "http://grafana:3000", "token": "glsa_..." }
```

### `POST /fetch/users`
### `POST /fetch/datasources`
### `POST /fetch/dashboards`
### `POST /fetch/alerts`
### `POST /fetch/contact-points`
```json
{ "source": { "url": "http://source:3000", "token": "glsa_..." } }
```

### `POST /migrate`

Streams NDJSON events. One event per line.

```json
{
  "source": { "url": "http://source:3000", "token": "glsa_src" },
  "target": { "url": "http://target:3000", "token": "glsa_tgt" },
  "selection": {
    "users": ["john.doe", "jane.smith"],
    "all_users": false,
    "datasources": ["prom-uid"],
    "all_datasources": false,
    "dashboards": ["abc123"],
    "all_dashboards": false,
    "alerts": ["MyFolder::my-group"],
    "all_alerts": false,
    "contact_points": ["uid1", "uid2"],
    "all_contact_points": false,
    "notification_policy": true
  },
  "on_conflict": "update"
}
```

**Event types streamed back:**

```jsonc
// Plan event (first)
{ "type": "plan", "totals": { "users": 5, "datasources": 3, "dashboards": 10, "alerts": 4, "contact_points": 28, "notification_policy": 1, "total": 51 } }

// Item event (one per migrated item)
{ "type": "item", "result": { "kind": "dashboard", "name": "API SLO", "status": "created" }, "progress": { "done": 3, "total": 51 } }

// Done event (last)
{ "type": "done", "summary": { "created": 30, "updated": 20, "skipped": 0, "failed": 1 } }

// Error event (if something goes wrong mid-stream)
{ "type": "error", "message": "..." }
```

Result `kind` values: `user`, `datasource`, `folder`, `dashboard`, `alert`, `mute_timing`, `contact_point`, `notification_policy`.

Result `status` values: `created`, `updated`, `skipped`, `failed`.

---

## Example cURL

```bash
# Verify target connection
curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"url":"http://target:3000","token":"glsa_xxx"}'

# List users on source
curl -X POST http://localhost:8000/fetch/users \
  -H "Content-Type: application/json" \
  -d '{"source":{"url":"http://source:3000","token":"glsa_xxx"}}'

# List contact points on source
curl -X POST http://localhost:8000/fetch/contact-points \
  -H "Content-Type: application/json" \
  -d '{"source":{"url":"http://source:3000","token":"glsa_xxx"}}'

# Migrate everything
curl -X POST http://localhost:8000/migrate \
  -H "Content-Type: application/json" \
  -d '{
    "source":{"url":"http://source:3000","token":"glsa_src"},
    "target":{"url":"http://target:3000","token":"glsa_tgt"},
    "selection":{
      "all_users":true,
      "all_datasources":true,
      "all_dashboards":true,
      "all_alerts":true,
      "all_contact_points":true,
      "notification_policy":true
    },
    "on_conflict":"update"
  }'
```

---

## Known limitations

- **Datasource secrets** (passwords, API keys, private tokens) are never returned by Grafana's API. After migration, open each datasource on the target and re-enter credentials, then click **Save & test**.
- **Folder permissions** are not migrated. Recreate via the target UI if needed.
- **Teams and org-level API keys** are not migrated.
- **Annotations and dashboard version history** are not migrated (and are typically very large — prune them on the source before a DB-level migration if needed).
- **Library panels** — references are stripped from dashboards during import; the library panel itself is not migrated.
- **Alert rule re-migration** is safe: the tool looks up existing rule UIDs on the target by title before posting, so rules are updated rather than duplicated.
- **Notification policy receiver validation** — any receiver in the source policy that doesn't exist on the target (including Grafana's internal `autogen-contact-point-default`) is replaced with the target's current default receiver. Routes with no receiver key are also fixed automatically.

---

## Project layout

```
grafana-migration/
├── backend/
│   ├── main.py              # FastAPI endpoints + NDJSON streaming
│   ├── grafana_client.py    # httpx-based Grafana REST client (all API methods)
│   ├── migrator.py          # Migration orchestration (all phases in order)
│   ├── models.py            # Pydantic request/response models
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.jsx                      # Main app: state, fetch handlers, migration run
    │   ├── api/client.js                # Fetch helpers + NDJSON stream parser
    │   └── components/
    │       ├── ConfigPanel.jsx          # Source/target URL + token inputs
    │       ├── ItemList.jsx             # Reusable selectable list with select-all
    │       └── MigrationProgress.jsx   # Live progress bars + per-item detail table
    ├── index.html
    └── package.json
```
