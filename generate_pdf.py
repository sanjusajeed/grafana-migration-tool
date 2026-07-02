"""
Generate Grafana Migration Tool  -  User Guide PDF.

Usage (from the project root):
    backend\\.venv\\Scripts\\python generate_pdf.py

Output: grafana_migration_guide.pdf
"""
from fpdf import FPDF
import os, sys

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
OUT_FILE = os.path.join(os.path.dirname(__file__), "grafana_migration_guide.pdf")

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
BLUE        = (37,  99, 235)   # brand blue
LIGHT_BLUE  = (239, 246, 255)  # very light blue bg
DARK        = (15,  23,  42)   # near-black headings
GRAY        = (100, 116, 139)  # body text
LIGHT_GRAY  = (241, 245, 249)  # section bg
WHITE       = (255, 255, 255)
GREEN       = (22, 163,  74)
ORANGE      = (234, 88,  12)
RED         = (220,  38,  38)
TEAL        = (13, 148, 136)
PURPLE      = (124,  58, 237)


FONTS_DIR = "C:/Windows/Fonts/"


class PDF(FPDF):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_font("Arial", "",  FONTS_DIR + "arial.ttf",   uni=True)
        self.add_font("Arial", "B", FONTS_DIR + "arialbd.ttf", uni=True)
        self.add_font("Arial", "I", FONTS_DIR + "ariali.ttf",  uni=True)
        self.add_font("Code", "", FONTS_DIR + "cour.ttf", uni=True)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_fill_color(*BLUE)
        self.rect(0, 0, 210, 10, "F")
        self.set_font("Arial", "B", 8)
        self.set_text_color(*WHITE)
        self.set_y(2)
        self.cell(0, 6, "Grafana Migration Tool  -  User Guide", align="C")
        self.set_text_color(*DARK)
        self.ln(6)

    def footer(self):
        self.set_y(-13)
        self.set_font("Arial", "", 8)
        self.set_text_color(*GRAY)
        self.cell(0, 6, f"Page {self.page_no()}", align="C")

    # ---- helpers ----

    def h1(self, text):
        self.ln(4)
        self.set_font("Arial", "B", 18)
        self.set_text_color(*DARK)
        self.cell(0, 10, text, ln=True)
        self.set_draw_color(*BLUE)
        self.set_line_width(0.8)
        self.line(self.get_x(), self.get_y(), self.get_x() + 170, self.get_y())
        self.ln(4)

    def h2(self, text):
        self.ln(3)
        self.set_font("Arial", "B", 13)
        self.set_text_color(*BLUE)
        self.cell(0, 8, text, ln=True)
        self.ln(1)

    def h3(self, text):
        self.set_font("Arial", "B", 10)
        self.set_text_color(*DARK)
        self.cell(0, 7, text, ln=True)

    def _mc(self, w, h, text, **kw):
        """multi_cell wrapper that always resets x to left margin afterward."""
        self.multi_cell(w, h, text, **kw)
        self.set_x(self.l_margin)

    def body(self, text, indent=0):
        self.set_font("Arial", "", 10)
        self.set_text_color(*GRAY)
        if indent:
            self.set_x(self.l_margin + indent)
        self._mc(0, 5.5, text)
        self.ln(1)

    def bullet(self, text, color=None):
        c = color or GRAY
        self.set_font("Arial", "", 10)
        self.set_text_color(*c)
        self._mc(0, 6, "  -  " + text)

    def note_box(self, text, bg=LIGHT_BLUE, border=BLUE):
        self.set_fill_color(*bg)
        self.set_draw_color(*border)
        self.set_line_width(0.3)
        self.set_font("Arial", "I", 9)
        self.set_text_color(*DARK)
        self._mc(0, 5.5, text, border=1, fill=True)
        self.ln(3)

    def tag(self, text, bg, fg=WHITE, w=None):
        self.set_font("Arial", "B", 8)
        self.set_fill_color(*bg)
        self.set_text_color(*fg)
        tw = w or (self.get_string_width(text) + 6)
        self.cell(tw, 6, text, fill=True, ln=False)
        self.set_text_color(*DARK)

    def section_divider(self):
        self.ln(4)
        self.set_draw_color(226, 232, 240)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def try_image(self, name, w=180):
        """Insert screenshot if it exists in ./screenshots/, else skip silently."""
        path = os.path.join(SCREENSHOTS_DIR, name)
        if os.path.isfile(path):
            self.image(path, x=15, w=w)
            self.ln(3)

    def code_block(self, lines):
        self.set_fill_color(30, 41, 59)
        self.set_draw_color(30, 41, 59)
        text = "\n".join(lines)
        self.set_font("Code", "", 8)
        self.set_text_color(*WHITE)
        self._mc(0, 4.5, text, fill=True, border=0)
        self.ln(3)
        self.set_text_color(*DARK)

    def status_badge(self, status):
        colors = {
            "created": GREEN,
            "updated": BLUE,
            "skipped": GRAY,
            "failed":  RED,
        }
        self.tag(f"  {status}  ", colors.get(status, GRAY))

    def kind_badge(self, kind):
        colors = {
            "user":                TEAL,
            "datasource":          PURPLE,
            "dashboard":           (79, 70, 229),
            "alert":               (219, 39, 119),
            "contact_point":       ORANGE,
            "mute_timing":         (202, 138, 4),
            "notification_policy": (8, 145, 178),
        }
        self.tag(f" {kind} ", colors.get(kind, GRAY))


# ===========================================================================
# Build document
# ===========================================================================

pdf = PDF(orientation="P", unit="mm", format="A4")
pdf.set_auto_page_break(auto=True, margin=18)
pdf.set_margins(15, 15, 15)

# ---------------------------------------------------------------------------
# Cover page
# ---------------------------------------------------------------------------
pdf.add_page()

# Blue header band
pdf.set_fill_color(*BLUE)
pdf.rect(0, 0, 210, 70, "F")

pdf.set_y(18)
pdf.set_font("Arial", "B", 28)
pdf.set_text_color(*WHITE)
pdf.cell(0, 12, "Grafana Migration Tool", align="C", ln=True)

pdf.set_font("Arial", "", 13)
pdf.set_text_color(186, 230, 253)
pdf.cell(0, 8, "Complete User Guide", align="C", ln=True)

pdf.set_y(75)
pdf.try_image("01_config_panel.png", w=175)

pdf.set_y(pdf.get_y() + 5)
pdf.set_font("Arial", "", 10)
pdf.set_text_color(*GRAY)
pdf.cell(0, 6, "Migrate users, datasources, dashboards, alert rules,", align="C", ln=True)
pdf.cell(0, 6, "contact points, and notification policies between Grafana instances.", align="C", ln=True)

pdf.ln(10)
pdf.set_font("Arial", "B", 9)
pdf.set_text_color(*DARK)
pdf.cell(0, 6, "Internal Tool  |  2026", align="C", ln=True)

# ---------------------------------------------------------------------------
# Page 2  -  Overview
# ---------------------------------------------------------------------------
pdf.add_page()
pdf.h1("Overview")
pdf.body(
    "The Grafana Migration Tool copies Grafana objects from a source instance to a target "
    "instance using the Grafana REST API. No direct database access is required on either side. "
    "All operations are performed through API tokens with Admin-level permissions."
)

pdf.h2("What Gets Migrated")

rows = [
    ("Users",               TEAL,            "Pre-created via org invite. Azure AD users activate on first SSO login with the correct role."),
    ("Datasources",         PURPLE,          "Full config copied. Secrets must be re-entered manually after migration."),
    ("Dashboards",          (79, 70, 229),   "Folders auto-created. Library panel references stripped to prevent import errors."),
    ("Alert rule groups",   (219, 39, 119),  "Re-migration safe  -  existing rules updated by title lookup, not duplicated."),
    ("Mute timings",        (202, 138, 4),   "Auto-included when Notification policy is selected."),
    ("Contact points",      ORANGE,          "Updated by UID if they exist; created if new."),
    ("Notification policy", (8, 145, 178),   "Full routing tree copied. Invalid receivers replaced with target default automatically."),
]

pdf.set_font("Arial", "B", 9)
pdf.set_fill_color(*BLUE)
pdf.set_text_color(*WHITE)
pdf.cell(35, 7, "Item", fill=True, border=0)
pdf.cell(145, 7, "Details", fill=True, border=0, ln=True)

for name, color, detail in rows:
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(226, 232, 240)
    pdf.set_text_color(*color)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(35, 7, f"  {name}", fill=True, border="LTB")
    pdf.set_text_color(*DARK)
    pdf.set_font("Arial", "", 9)
    pdf.cell(145, 7, detail, fill=True, border="RTB", ln=True)

pdf.ln(4)
pdf.note_box(
    "NOT migrated: datasource secrets, folder permissions, teams, API keys, annotations, "
    "dashboard version history, library panels, playlists."
)

pdf.h2("Architecture")
pdf.body("Backend: FastAPI (Python 3.10+)  •  Frontend: React + Vite + Tailwind CSS")
pdf.body("Migration order: users → datasources → folders → dashboards → alerts → mute timings → contact points → notification policy")

# ---------------------------------------------------------------------------
# Page 3  -  Prerequisites & Setup
# ---------------------------------------------------------------------------
pdf.add_page()
pdf.h1("Prerequisites & Setup")

pdf.h2("API Tokens Required")
pdf.body("Both source and target Grafana instances need an Admin-level service account token.")
pdf.body("Administration → Service accounts → Add service account → role: Admin → Add service account token → copy the glsa_… value.")

pdf.note_box(
    "User migration uses POST /api/org/invites (Org Admin only)  -  Grafana Server Admin is NOT required.\n"
    "The source token needs Admin role to read /api/org/users and /api/v1/provisioning/* endpoints."
)

pdf.h2("Running Locally")

pdf.h3("Backend")
pdf.code_block([
    "cd backend",
    "python -m venv .venv",
    ".venv\\Scripts\\activate          # Windows",
    "# source .venv/bin/activate     # macOS / Linux",
    "pip install -r requirements.txt",
    "python main.py",
    "",
    "# Swagger UI: http://localhost:8000/docs",
])

pdf.h3("Frontend")
pdf.code_block([
    "cd frontend",
    "npm install",
    "npm run dev",
    "",
    "# Open: http://localhost:5173",
])

# ---------------------------------------------------------------------------
# Page 4  -  UI Walkthrough: Config + Fetch
# ---------------------------------------------------------------------------
pdf.add_page()
pdf.h1("UI Walkthrough")

pdf.h2("Step 1  -  Configure Source & Target")
pdf.body(
    "Enter the Grafana URL and API token for both the source (where data comes from) and "
    "the target (where data will be written). Click Test connection to verify each before proceeding."
)
pdf.try_image("01_config_panel.png")

pdf.h2("Step 2  -  Fetch from Source")
pdf.body(
    "Click Fetch from source. All six sections (Users, Datasources, Dashboards, Alert rule groups, "
    "Contact points) populate automatically in parallel. The count badge next to each section "
    "title updates to show how many items were found."
)
pdf.try_image("02_fetch_bar.png")

# ---------------------------------------------------------------------------
# Page 5  -  UI sections
# ---------------------------------------------------------------------------
pdf.add_page()
pdf.h2("Users Section")
pdf.body(
    "Lists all users from the source org (built-in admin excluded). Each row shows the "
    "display name, login, and role badge. Select individual users or use Select all."
)
pdf.try_image("03_users_section.png")

pdf.h2("Datasources Section")
pdf.body(
    "Shows all datasources with name, type badge, and whether it is the org default. "
    "Datasource secrets are NOT copied  -  you must re-enter credentials on the target after migration."
)
pdf.try_image("04_datasources_section.png")

# ---------------------------------------------------------------------------
# Page 6
# ---------------------------------------------------------------------------
pdf.add_page()
pdf.h2("Dashboards Section")
pdf.body(
    "Lists all dashboards with title and folder name. Folders are created automatically on "
    "the target if they do not exist. Library panel references are stripped during import "
    "to prevent 500 errors."
)
pdf.try_image("05_dashboards_section.png")

pdf.h2("Alert Rule Groups Section")
pdf.body(
    "Shows alert rule groups with group name, folder namespace badge, rule count, and "
    "evaluation interval. Re-migration is safe: existing rules are updated by title lookup "
    "and will not be duplicated."
)
pdf.try_image("06_alerts_section.png")

# ---------------------------------------------------------------------------
# Page 7
# ---------------------------------------------------------------------------
pdf.add_page()
pdf.h2("Contact Points Section")
pdf.body(
    "Lists all contact points (Teams, email, OpsGenie, PagerDuty, etc.) from the source. "
    "Existing contact points on the target are updated by UID; new ones are created. "
    "Select individual contact points or use Select all."
)
pdf.try_image("07_contact_points_section.png")

pdf.h2("Notification Policy")
pdf.body(
    "A single checkbox  -  Grafana has exactly one notification policy (the global alert routing tree). "
    "Checking this copies the entire routing tree and automatically includes all contact points "
    "and mute timings. No separate selection is needed."
)
pdf.try_image("08_notification_policy.png")
pdf.note_box(
    "Any receiver in the source policy that does not exist on the target (including Grafana's "
    "internal 'autogen-contact-point-default') is automatically replaced with the target's "
    "current default receiver. Routes with a missing or null receiver are also fixed."
)

# ---------------------------------------------------------------------------
# Page 8  -  Running a migration
# ---------------------------------------------------------------------------
pdf.add_page()
pdf.h1("Running a Migration")

pdf.h2("Step 3  -  Select Items")
pdf.body(
    "In each section, check the items you want to migrate. Use Select all for a full migration. "
    "You can filter the list by typing in the Filter… box."
)

pdf.h2("Step 4  -  On Conflict")
pdf.body("Choose what to do when an item already exists on the target:")
pdf.bullet("Update existing   -  overwrite the target item with the source version.")
pdf.bullet("Skip existing     -  leave the target item untouched.")
pdf.ln(3)

pdf.h2("Step 5  -  Start Migration")
pdf.body(
    "Click Start migration. Results stream live in the Progress panel. "
    "The Percentage tab shows per-kind progress bars. "
    "The Status tab shows every item with its kind badge and outcome badge."
)

pdf.ln(2)
pdf.h3("Status badges")
pdf.ln(2)
for s in ("created", "updated", "skipped", "failed"):
    pdf.status_badge(s)
    pdf.cell(4)
pdf.ln(8)

pdf.h3("Kind badges")
pdf.ln(2)
for k in ("user", "datasource", "dashboard", "alert", "contact_point", "mute_timing", "notification_policy"):
    pdf.kind_badge(k)
    pdf.cell(3)
pdf.ln(8)

pdf.h2("Migration Order")
pdf.body(
    "Items are always migrated in this order to preserve all references:\n"
    "1. Users\n"
    "2. Datasources\n"
    "3. Folders (auto-created as needed)\n"
    "4. Dashboards\n"
    "5. Alert rule groups\n"
    "6. Mute timings\n"
    "7. Contact points\n"
    "8. Notification policy"
)

# ---------------------------------------------------------------------------
# Page 9  -  Azure AD
# ---------------------------------------------------------------------------
pdf.add_page()
pdf.h1("Azure AD / SSO User Migration")

pdf.body(
    "Because Azure AD handles authentication externally, passwords cannot be set by the tool. "
    "Users are pre-registered via Grafana's org invite API:"
)

pdf.bullet("POST /api/org/invites is called with sendEmail: false  -  no email is sent.")
pdf.bullet("When the user logs in for the first time via Azure AD SSO, Grafana matches their email to the pending invite and assigns the configured role (Viewer / Editor / Admin).")
pdf.bullet("If the user already exists on the target, only their role is updated via PATCH /api/org/users/{userId}.")
pdf.bullet("The built-in admin user is always skipped.")
pdf.ln(3)

pdf.note_box(
    "This approach requires only Org Admin on the target service account.\n"
    "Grafana Server Admin is NOT needed  -  the tool never calls /api/admin/users."
)

pdf.h2("What happens after first login")
pdf.body(
    "1. User visits the target Grafana and clicks 'Sign in with Microsoft'.\n"
    "2. Azure AD authenticates them and redirects back.\n"
    "3. Grafana finds the pending invite matching their email.\n"
    "4. The user is added to the org with the role specified during migration.\n"
    "5. All dashboards and folders the role permits are immediately accessible."
)

# ---------------------------------------------------------------------------
# Page 10  -  API Reference
# ---------------------------------------------------------------------------
pdf.add_page()
pdf.h1("API Reference")

pdf.body("All endpoints accept JSON. Credentials are passed in the request body and never stored.")

endpoints = [
    ("GET",  "/health",               "Returns {\"status\": \"ok\"}"),
    ("POST", "/verify",               "Test a Grafana URL + token combination"),
    ("POST", "/fetch/users",          "List org users from source (admin excluded)"),
    ("POST", "/fetch/datasources",    "List datasources from source"),
    ("POST", "/fetch/dashboards",     "List dashboards from source"),
    ("POST", "/fetch/alerts",         "List alert rule groups from source"),
    ("POST", "/fetch/contact-points", "List contact points from source"),
    ("POST", "/migrate",              "Run migration, returns NDJSON stream"),
]

pdf.set_font("Arial", "B", 9)
pdf.set_fill_color(*BLUE)
pdf.set_text_color(*WHITE)
pdf.cell(15, 7, "Method", fill=True)
pdf.cell(65, 7, "Path", fill=True)
pdf.cell(100, 7, "Description", fill=True)
pdf.ln()

for method, path, desc in endpoints:
    mc = GREEN if method == "GET" else BLUE
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(226, 232, 240)
    pdf.set_text_color(*mc)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(15, 6, method, fill=True, border="LTB")
    pdf.set_text_color(*DARK)
    pdf.set_font("Courier", "", 9)
    pdf.cell(65, 6, path, fill=True, border="TB")
    pdf.set_font("Arial", "", 9)
    pdf.cell(100, 6, desc, fill=True, border="RTB")
    pdf.ln()

pdf.ln(4)
pdf.h2("Migrate request body")
pdf.code_block([
    '{',
    '  "source": {"url": "https://monitoring.example.com", "token": "glsa_src"},',
    '  "target": {"url": "http://monitoring-backup.example.com", "token": "glsa_tgt"},',
    '  "selection": {',
    '    "users":              ["john.doe", "jane.smith"],',
    '    "all_users":          false,',
    '    "datasources":        ["prom-uid", "loki-uid"],',
    '    "all_datasources":    false,',
    '    "dashboards":         ["abc123"],',
    '    "all_dashboards":     false,',
    '    "alerts":             ["MyFolder::my-group"],',
    '    "all_alerts":         false,',
    '    "contact_points":     ["uid1", "uid2"],',
    '    "all_contact_points": false,',
    '    "notification_policy": true',
    '  },',
    '  "on_conflict": "update"',
    '}',
])

pdf.h2("NDJSON stream events")
pdf.code_block([
    '// Plan (first event)',
    '{"type":"plan","totals":{"users":5,"datasources":3,"dashboards":10,"alerts":4,"contact_points":28,"notification_policy":1,"total":51}}',
    '',
    '// Item (one per migrated object)',
    '{"type":"item","result":{"kind":"dashboard","name":"API SLO","status":"created"},"progress":{"done":3,"total":51}}',
    '',
    '// Done (last event)',
    '{"type":"done","summary":{"created":30,"updated":20,"skipped":0,"failed":1}}',
    '',
    '// Error (mid-stream failure)',
    '{"type":"error","message":"..."}',
])

# ---------------------------------------------------------------------------
# Page 11  -  Known Limitations
# ---------------------------------------------------------------------------
pdf.add_page()
pdf.h1("Known Limitations")

limits = [
    ("Datasource secrets",
     "Grafana's API never returns secureJsonData on GET. After migration, open each "
     "datasource on the target and re-enter credentials (passwords, API keys, private tokens), "
     "then click Save & test."),
    ("Folder permissions",
     "Folder-level permissions (ACLs) are not migrated. Recreate them via the target UI "
     "under Dashboards → Manage → Folder settings."),
    ("Library panels",
     "Library panel references are stripped from dashboards during import to prevent 500 errors. "
     "The library panels themselves are not migrated."),
    ("Teams & org API keys",
     "Grafana teams and org-level API keys are not migrated."),
    ("Annotations & version history",
     "Not migrated. These can be very large (13 GB+ for busy instances). "
     "For a full lift-and-shift, use a DB-level migration instead."),
    ("Alert rule re-migration",
     "Safe by design. The tool looks up existing rule UIDs on the target by title before "
     "posting, so rules are updated rather than creating duplicates."),
    ("Notification policy receivers",
     "Any receiver not present on the target (including Grafana's internal "
     "'autogen-contact-point-default') is automatically replaced with the target's current "
     "default receiver. Routes with no receiver key are also fixed."),
]

for title, detail in limits:
    pdf.set_fill_color(*LIGHT_GRAY)
    pdf.set_draw_color(203, 213, 225)
    pdf.set_line_width(0.3)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 7, f"  {title}", fill=True, border=1, ln=True)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*GRAY)
    pdf.multi_cell(0, 5, f"  {detail}")
    pdf.ln(2)

# ---------------------------------------------------------------------------
# Page 12  -  Project Layout
# ---------------------------------------------------------------------------
pdf.add_page()
pdf.h1("Project Layout")

pdf.code_block([
    "grafana-migration/",
    "+-- backend/",
    "|   +-- main.py              # FastAPI endpoints + NDJSON streaming",
    "|   +-- grafana_client.py    # httpx Grafana REST client (all API methods)",
    "|   +-- migrator.py          # Migration orchestration (all phases)",
    "|   +-- models.py            # Pydantic request/response models",
    "|   `-- requirements.txt",
    "+-- frontend/",
    "|   +-- src/",
    "|   |   +-- App.jsx                      # Main app: state, fetch, migration",
    "|   |   +-- api/client.js                # Fetch helpers + NDJSON parser",
    "|   |   `-- components/",
    "|   |       +-- ConfigPanel.jsx          # Source/target URL + token inputs",
    "|   |       +-- ItemList.jsx             # Reusable selectable list",
    "|   |       `-- MigrationProgress.jsx    # Live progress + detail table",
    "|   +-- index.html",
    "|   `-- package.json",
    "+-- README.md",
    "`-- generate_pdf.py          # This script",
])

pdf.h2("Key API methods in grafana_client.py")
methods = [
    ("list_org_users()",                   "GET /api/org/users  -  fetch all users in org"),
    ("invite_user(email, name, role)",     "POST /api/org/invites  -  pre-register user (Org Admin only)"),
    ("update_org_user_role(id, role)",     "PATCH /api/org/users/{id}  -  update existing user's role"),
    ("list_contact_points()",              "GET /api/v1/provisioning/contact-points"),
    ("create_contact_point(cp)",           "POST /api/v1/provisioning/contact-points"),
    ("update_contact_point(uid, cp)",      "PUT /api/v1/provisioning/contact-points/{uid}"),
    ("get_notification_policy()",         "GET /api/v1/provisioning/policies"),
    ("put_notification_policy(policy)",   "PUT /api/v1/provisioning/policies"),
    ("list_mute_timings()",               "GET /api/v1/provisioning/mute-timings"),
    ("get_rule_group(ns, group)",         "GET /api/ruler/grafana/api/v1/rules/{ns}/{group}"),
    ("post_rule_group(ns, group)",        "POST /api/ruler/grafana/api/v1/rules/{ns}"),
]
for sig, desc in methods:
    pdf.set_font("Courier", "", 9)
    pdf.set_text_color(*BLUE)
    pdf.cell(82, 5.5, sig)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 5.5, desc, ln=True)

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
pdf.output(OUT_FILE)
print(f"PDF saved to: {OUT_FILE}")
print(f"\nTo include actual screenshots, save PNG files to: {SCREENSHOTS_DIR}/")
print("Expected screenshot filenames:")
for name in [
    "01_config_panel.png",
    "02_fetch_bar.png",
    "03_users_section.png",
    "04_datasources_section.png",
    "05_dashboards_section.png",
    "06_alerts_section.png",
    "07_contact_points_section.png",
    "08_notification_policy.png",
]:
    print(f"  {name}")
