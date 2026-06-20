"""VOLTEDGE Dashboard — Role-based (Admin / Employee)"""

import streamlit as st
import sys
import base64
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


@st.cache_data(show_spinner=False)
def _load_logo_cached(path_str, _mtime):
    """Cached by path + modified-time so a replaced logo auto-refreshes."""
    p = Path(path_str)
    ext  = p.suffix.lstrip(".").lower()
    mime = "svg+xml" if ext == "svg" else ext
    return base64.b64encode(p.read_bytes()).decode(), mime


def _load_logo():
    """Return (base64, mime) for streamlit_app/assets/logo.* if present, else (None, None)."""
    for ext in ("png", "jpg", "jpeg", "webp", "svg"):
        p = Path(__file__).parent / "assets" / f"logo.{ext}"
        if p.exists():
            return _load_logo_cached(str(p), p.stat().st_mtime)
    return None, None

from modules.supabase_client import (
    get_supabase_client, get_projects, get_project_by_id,
    create_project, update_project, get_activity_logs, log_activity,
)
from modules.auth import (
    init_auth, handle_oauth_callback, login_form, logout,
    load_user_from_db, is_admin,
)
from modules.utils import format_currency
from modules.project_detail import render_project_detail
from modules.epc import render_epc_page
from modules.reports import render_reports

# ── Helper functions (must be defined before any tab code) ────────────────────

def _time_ago(ts_str):
    if not ts_str:
        return "-"
    try:
        from datetime import datetime, timezone
        ts   = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        s    = int((datetime.now(timezone.utc) - ts).total_seconds())
        if s < 60:    return f"{s}s ago"
        if s < 3600:  return f"{s//60}m ago"
        if s < 86400: return f"{s//3600}h ago"
        return f"{s//86400}d ago"
    except Exception:
        return "-"


def _render_activity_feed(logs):
    icons = {"project":"📁","step":"🔧","note":"📝","document":"📄","installment":"💳","user":"👤"}
    html  = '<div style="background:#1e293b;border-radius:10px;padding:4px 0">'
    for log in logs:
        icon    = icons.get(log.get("entity_type",""), "⚡")
        name    = log.get("user_name","Unknown")
        email   = log.get("user_email","")
        action  = log.get("action","")
        project = log.get("project_name","")
        details = log.get("details","") or ""
        ago     = _time_ago(log.get("created_at",""))
        pic     = log.get("user_picture","")
        avatar  = (f'<img src="{pic}" style="width:28px;height:28px;border-radius:50%;vertical-align:middle">'
                   if pic else '<span style="width:28px;height:28px;border-radius:50%;background:#334155;'
                               'display:inline-flex;align-items:center;justify-content:center;font-size:0.7rem">👤</span>')
        # escape any HTML in user-entered fields so logged content can't break/show as markup
        import html as _html
        action  = _html.escape(str(action))
        details = _html.escape(str(details))
        name    = _html.escape(str(name))
        email   = _html.escape(str(email))
        project = _html.escape(str(project))
        proj_html    = f'<span style="color:#64748b"> · {project}</span>' if project else ""
        details_html = (f'<div style="font-size:0.72rem;color:#475569;margin-top:2px;'
                        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{details}</div>'
                        if details else "")
        # compact, single-line HTML (no leading indentation → markdown renders as HTML, not a code block)
        html += (
            '<div style="display:flex;align-items:flex-start;padding:10px 16px;border-bottom:1px solid #334155;gap:10px">'
            f'<div style="flex-shrink:0;margin-top:2px">{avatar}</div>'
            '<div style="flex:1;min-width:0">'
            f'<div style="font-size:0.82rem"><span style="font-weight:700;color:#f1f5f9">{name}</span>'
            f'<span style="color:#94a3b8;font-size:0.75rem;margin-left:6px">{email}</span></div>'
            f'<div style="font-size:0.82rem;color:#cbd5e1;margin-top:2px">{icon} {action}{proj_html}</div>'
            f'{details_html}'
            '</div>'
            f'<div style="font-size:0.72rem;color:#475569;flex-shrink:0;white-space:nowrap">{ago}</div>'
            '</div>'
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


st.set_page_config(
    page_title="VOLTEDGE Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  #MainMenu, footer { visibility: hidden; }
  /* Deep-navy theme to match the reference design */
  .stApp { background: #0a1322 !important; }
  [data-testid="stAppViewContainer"], [data-testid="stMain"] { background: #0a1322 !important; }
  /* Keep header transparent so the sidebar expand arrow stays usable */
  header[data-testid="stHeader"] { background: transparent !important; }
  /* Hide only the Deploy button / status widget, NOT the sidebar toggle */
  [data-testid="stToolbarActions"], [data-testid="stStatusWidget"],
  [data-testid="stDeployButton"], [data-testid="stMainMenu"] { display: none !important; }
  /* Always allow reopening a collapsed sidebar (cover known testids across versions) */
  [data-testid="stSidebarCollapsedControl"],
  [data-testid="collapsedControl"],
  [data-testid="stSidebarCollapseButton"],
  [data-testid="stExpandSidebarButton"] {
      visibility: visible !important; display: flex !important; opacity: 1 !important; z-index: 999999 !important;
  }
  .block-container { padding-top: 1.2rem; padding-bottom: 1rem; }

  /* ── Sidebar styling ───────────────────────────────────────── */
  /* Hide Streamlit's auto multipage nav (old pages/ scaffolding) */
  section[data-testid="stSidebar"] [data-testid="stSidebarNav"] { display: none !important; }
  section[data-testid="stSidebar"] {
      background: #0a1322; border-right: 1px solid #1e293b; width: 260px !important;
  }
  section[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
  /* nav buttons */
  section[data-testid="stSidebar"] div[class*="st-key-nav_"] button {
      background: transparent !important; border: none !important; box-shadow: none !important;
      justify-content: flex-start !important; color: #94a3b8 !important;
      font-weight: 600 !important; border-radius: 8px !important; padding: 8px 14px !important;
  }
  section[data-testid="stSidebar"] div[class*="st-key-nav_"] button:hover {
      background: #1e293b !important; color: #f1f5f9 !important;
  }
  section[data-testid="stSidebar"] div[class*="st-key-nav_"] button[kind="primary"],
  section[data-testid="stSidebar"] div[class*="st-key-subnav_"] button[kind="primary"] {
      background: linear-gradient(90deg, #5b1212, #7f1d1d) !important;
      color: #fca5a5 !important; border: 1px solid #b91c1c !important;
      border-radius: 10px !important; font-weight: 700 !important;
  }
  section[data-testid="stSidebar"] div[class*="st-key-subnav_"] button {
      background: transparent !important; border: none !important; box-shadow: none !important;
      justify-content: flex-start !important; color: #cbd5e1 !important;
      font-weight: 500 !important; font-size: 0.86rem !important; padding: 7px 14px 7px 26px !important;
  }
  section[data-testid="stSidebar"] div[class*="st-key-subnav_"] button:hover { color: #f1f5f9 !important; background:#1e293b !important; }

  /* Logout as a red text link, not a boxed button */
  section[data-testid="stSidebar"] div[class*="st-key-sidebar_logout"] button {
      background: transparent !important; border: none !important; box-shadow: none !important;
      color: #ef4444 !important; justify-content: flex-start !important;
      font-weight: 700 !important; padding: 6px 10px !important;
  }
  section[data-testid="stSidebar"] div[class*="st-key-sidebar_logout"] button:hover { color: #f87171 !important; }

  /* Add-Project section cards (bordered containers keyed npcard_*) */
  div[class*="st-key-npcard_"] {
      background: #0d1a2e !important; border: 1px solid #16304d !important;
      border-radius: 12px !important; padding: 10px 16px 4px !important; margin-bottom: 10px !important;
  }
  .stTabs [data-baseweb="tab-list"] {
      gap: 6px; background: #1e293b; padding: 6px; border-radius: 10px;
  }
  .stTabs [data-baseweb="tab"] {
      border-radius: 8px; padding: 6px 22px;
      color: #94a3b8; font-weight: 600; font-size: 0.9rem; background: transparent;
  }
  .stTabs [aria-selected="true"] { background: #dc2626 !important; color: #fff !important; }
  div[data-testid="metric-container"] {
      background: #1e293b; border-radius: 10px;
      padding: 16px 20px; border-left: 3px solid #dc2626;
  }
  div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
  hr { border-color: #1e293b; }

  /* Customer-name cells render as hyperlinks, not button boxes */
  div[class*="st-key-qe_name_"] button {
      background: transparent !important; border: none !important; box-shadow: none !important;
      padding: 4px 0 !important; min-height: 0 !important;
      justify-content: flex-start !important;
  }
  div[class*="st-key-qe_name_"] button p {
      color: #f1f5f9 !important; font-size: 0.82rem !important; font-weight: 600 !important;
      text-align: left !important; margin: 0 !important;
  }
  div[class*="st-key-qe_name_"] button:hover p { color: #f97316 !important; text-decoration: underline !important; }

  /* DUE AMOUNT sort header — looks like the other orange headers */
  div[class*="st-key-sort_due"] button {
      background: transparent !important; border: none !important; box-shadow: none !important;
      padding: 6px 0 !important; min-height: 0 !important;
      justify-content: flex-start !important;
  }
  div[class*="st-key-sort_due"] button p {
      color: #f97316 !important; font-size: 0.7rem !important; font-weight: 700 !important;
      text-align: left !important; margin: 0 !important;
  }
  div[class*="st-key-sort_due"] button:hover p { color: #fb923c !important; }
</style>
""", unsafe_allow_html=True)

init_auth()
handle_oauth_callback()

# ── LOGIN ─────────────────────────────────────────────────────────────────────
if not st.session_state.get("authenticated", False):
    # Clean standalone first page — hide the (empty) sidebar & its toggle
    st.markdown("""
    <style>
      section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display:none !important; }
      [data-testid="stAppViewContainer"] > .main { background: radial-gradient(1200px 600px at 50% -10%, #102036 0%, #0a1322 60%); }
    </style>""", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        _lb64, _lmime = _load_logo()
        if _lb64:
            st.markdown(
                f'<div style="text-align:center;padding:90px 0 14px">'
                f'<img src="data:image/{_lmime};base64,{_lb64}" style="width:100%;max-width:340px">'
                f'<div style="color:#94a3b8;margin-top:14px;font-size:1rem;letter-spacing:0.5px">Solar Project Management Dashboard</div></div>',
                unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="text-align:center;padding:60px 0 28px">
              <div style="font-size:3rem">⚡</div>
              <div style="font-size:2rem;font-weight:800;color:#dc2626;letter-spacing:1px">VOLTEDGE</div>
              <div style="color:#64748b;margin-top:4px;font-size:0.95rem">Energy Solutions · Solar Dashboard</div>
            </div>
            """, unsafe_allow_html=True)
        login_form()
    st.stop()

# ── LOAD USER FROM DB ─────────────────────────────────────────────────────────
supabase = get_supabase_client()
user_row = load_user_from_db(supabase)

role   = st.session_state.get("user_role",   "employee")
status = st.session_state.get("user_status", "pending")

# ── PENDING APPROVAL SCREEN ───────────────────────────────────────────────────
if status == "pending":
    _, mid, _ = st.columns([1, 1.5, 1])
    with mid:
        name = st.session_state.get("user_name","")
        pic  = st.session_state.get("user_picture","")
        if pic:
            st.image(pic, width=64)
        st.markdown(f"""
        <div style="text-align:center;padding:20px 0">
          <div style="font-size:1.5rem;font-weight:700">👋 Hi, {name}!</div>
          <div style="margin:16px 0;padding:20px;background:#1e293b;border-radius:12px;
                      border-left:4px solid #f59e0b">
            <div style="font-size:1.1rem;font-weight:700;color:#f59e0b">⏳ Awaiting Admin Approval</div>
            <div style="color:#94a3b8;margin-top:8px;font-size:0.9rem">
              Your account request has been sent to the admin.<br>
              You'll be able to access the dashboard once approved.
            </div>
          </div>
          <div style="color:#64748b;font-size:0.82rem">Signed in as: {st.session_state.get('user_email','')}</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🔄 Refresh Status", use_container_width=True):
            st.rerun()
        if st.button("🚪 Sign Out", use_container_width=True):
            logout()
    st.stop()

# ── REJECTED SCREEN ───────────────────────────────────────────────────────────
if status == "rejected":
    _, mid, _ = st.columns([1, 1.5, 1])
    with mid:
        st.markdown("""
        <div style="text-align:center;padding:40px 0">
          <div style="font-size:2rem">🚫</div>
          <div style="font-size:1.2rem;font-weight:700;color:#ef4444;margin:10px 0">Access Denied</div>
          <div style="color:#64748b;font-size:0.9rem">
            Your access request was rejected.<br>Please contact the admin.
          </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🚪 Sign Out", use_container_width=True):
            logout()
    st.stop()

# ── LOAD PROJECT DATA ─────────────────────────────────────────────────────────
projects    = get_projects(supabase) or []
df          = pd.DataFrame(projects) if projects else pd.DataFrame()

total       = len(projects)
active      = sum(1 for p in projects if p.get("project_status") in ("in_progress","planning","approved"))
completed   = sum(1 for p in projects if p.get("project_status") == "completed")
cancelled   = sum(1 for p in projects if p.get("project_status") == "cancelled")
total_cost  = sum(float(p.get("total_cost",  0) or 0) for p in projects)
total_paid  = sum(float(p.get("amount_paid", 0) or 0) for p in projects)
balance_due = sum(float(p.get("balance",     0) or 0) for p in projects)
comp_pct    = round(completed / total * 100, 1) if total else 0.0


# ── SHARED HEADER ─────────────────────────────────────────────────────────────
def render_header(extra_key=""):
    hc1, hc2 = st.columns([4, 1])
    with hc1:
        name = st.session_state.get("user_code", "VE-001")
        pic  = st.session_state.get("user_picture","")
        role_badge = "🔴 Admin" if role == "admin" else "🟡 Employee"
        if pic:
            pc, tc = st.columns([0.08, 0.92])
            with pc: st.image(pic, width=42)
            with tc:
                st.markdown(
                    f"<div style='line-height:1.2;padding-top:4px'>"
                    f"<span style='color:#64748b;font-size:0.75rem'>WELCOME BACK,</span><br>"
                    f"<span style='font-size:1.45rem;font-weight:800'>⚡ {name}</span>"
                    f"<span style='background:#1e293b;color:#94a3b8;font-size:0.72rem;"
                    f"padding:2px 10px;border-radius:20px;margin-left:10px'>{role_badge}</span></div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f"<div style='line-height:1.2;padding-top:6px'>"
                f"<span style='color:#64748b;font-size:0.75rem'>WELCOME BACK,</span><br>"
                f"<span style='font-size:1.45rem;font-weight:800'>⚡ {name}</span>"
                f"<span style='background:#1e293b;color:#94a3b8;font-size:0.72rem;"
                f"padding:2px 10px;border-radius:20px;margin-left:10px'>{role_badge}</span></div>",
                unsafe_allow_html=True,
            )
    with hc2:
        if st.button("🚪 Logout", use_container_width=True, key=f"logout_{extra_key}"):
            logout()
    st.markdown("<hr style='margin:8px 0 14px'>", unsafe_allow_html=True)


# ── LEFT SIDEBAR NAVIGATION ───────────────────────────────────────────────────
def render_sidebar():
    if "nav" not in st.session_state:
        st.session_state.nav = "Overview"
    cur = st.session_state.nav

    with st.sidebar:
        # Logo — use real logo image if provided, else fallback badge
        _logo_b64, _logo_mime = _load_logo()
        if _logo_b64:
            st.markdown(
                f'<div style="padding:8px 4px 18px;text-align:center">'
                f'<img src="data:image/{_logo_mime};base64,{_logo_b64}" style="width:100%;max-width:215px">'
                f'</div>', unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="display:flex;align-items:center;gap:12px;padding:6px 6px 20px">
              <div style="background:#0b1626;border:2.5px solid #16a34a;color:#16a34a;font-weight:800;
                          border-radius:50%;width:46px;height:46px;display:flex;align-items:center;
                          justify-content:center;font-size:1.05rem;flex-shrink:0">VE</div>
              <div style="line-height:1.15">
                <div style="font-weight:800;font-size:1.2rem;color:#f1f5f9;letter-spacing:0.5px">VOLT<span style="color:#16a34a">EDGE</span></div>
                <div style="font-size:0.55rem;color:#64748b;letter-spacing:2px">— ENERGY SOLUTIONS —</div>
              </div>
            </div>""", unsafe_allow_html=True)

        def nav_btn(label, icon, key, chevron=False):
            txt = f"{icon}  {label}" + ("   ⌄" if chevron else "")
            if st.button(txt, key=f"nav_{key}", use_container_width=True,
                         type="primary" if cur == label else "secondary"):
                st.session_state.nav = label
                st.session_state.selected_project_id = None
                st.rerun()

        def subnav_btn(label, icon, key):
            if st.button(f"{icon}  {label}", key=f"subnav_{key}", use_container_width=True,
                         type="primary" if cur == label else "secondary"):
                st.session_state.nav = label
                st.session_state.selected_project_id = None
                st.rerun()

        nav_btn("Overview", "🏠", "overview", chevron=True)

        # Edit Customers — group row (navigates to Customer List)
        _ec_active = cur in ("Customer List", "Add Project")
        if st.button("👥  Edit Customers   ⌄", key="nav_editcust", use_container_width=True,
                     type="primary" if _ec_active else "secondary"):
            st.session_state.nav = "Customer List"
            st.session_state.selected_project_id = None
            st.rerun()
        subnav_btn("Customer List", "☰", "custlist")
        subnav_btn("Add Project",   "＋", "addproj")

        if role == "admin":
            nav_btn("Report", "📊", "report")
            nav_btn("EPC Partners", "🏭", "epc")
            nav_btn("Users",  "👤", "users")
        nav_btn("Settings", "⚙️", "settings")

        # user card pinned near bottom
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        st.markdown("<hr style='margin:8px 0;border-color:#1e293b'>", unsafe_allow_html=True)
        uname = st.session_state.get("user_name") or st.session_state.get("user_email", "User")
        ucode = st.session_state.get("user_code", "VE-001")
        urole = "Admin" if role == "admin" else "Engineer"
        upic  = st.session_state.get("user_picture", "")
        ava   = (f'<img src="{upic}" style="width:44px;height:44px;border-radius:50%;object-fit:cover">' if upic
                 else '<div style="width:44px;height:44px;border-radius:50%;background:#16a34a;display:flex;align-items:center;justify-content:center;font-weight:700;color:#fff;font-size:1.1rem">'
                      + (uname[:1].upper() if uname else "U") + '</div>')
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;padding:6px 8px 4px">
          {ava}
          <div style="line-height:1.25">
            <div style="font-weight:700;font-size:0.95rem;color:#f1f5f9">{ucode}</div>
            <div style="font-size:0.74rem;color:#94a3b8">{urole}</div>
            <div style="font-size:0.68rem;color:#22c55e">● Online</div>
          </div>
        </div>""", unsafe_allow_html=True)
        if st.button("⏻  Logout", key="sidebar_logout", use_container_width=True):
            logout()

    return st.session_state.nav


nav = render_sidebar()

# ── PROJECT DETAIL (overrides pages) ─────────────────────────────────────────
if st.session_state.get("selected_project_id"):
    pid     = st.session_state.selected_project_id
    project = get_project_by_id(supabase, pid)
    if project:
        render_project_detail(supabase, project, role=role)
    else:
        st.session_state.selected_project_id = None
        st.rerun()
    st.stop()


# ── MAIN DASHBOARD ────────────────────────────────────────────────────────────
render_header("main")


# ══════════════════════════════════════════════════════════════════════════════
#  OVERVIEW PAGE
# ══════════════════════════════════════════════════════════════════════════════
if nav == "Overview":
    from datetime import datetime as _dtnow
    _now = _dtnow.now()

    # ── compute stats ─────────────────────────────────────────────
    _mon = _now.strftime("%Y-%m")
    completed_month = sum(1 for p in projects
                          if p.get("project_status") == "completed"
                          and str(p.get("updated_at") or p.get("created_at") or "")[:7] == _mon) or completed
    subsidy_pending   = sum(1 for p in projects
                            if float(p.get("subsidy_amount", 0) or 0) > 0
                            and (p.get("subsidy_status") or "pending") != "disbursed")
    subsidy_disbursed = sum(1 for p in projects
                            if (p.get("subsidy_status") or "").lower() == "disbursed")
    try:
        _pend_inst = supabase.table("installments").select("project_id,due_date,status").execute().data or []
    except Exception:
        _pend_inst = []
    _today = _now.strftime("%Y-%m-%d")
    due_by_proj = {}
    for i in _pend_inst:
        if i.get("status") == "pending" and i.get("due_date"):
            _pi, _d = i.get("project_id"), str(i["due_date"])[:10]
            if _pi and (_pi not in due_by_proj or _d < due_by_proj[_pi]):
                due_by_proj[_pi] = _d

    def _stat_card(icon, icon_bg, value, label, sub):
        return f"""<div style="background:#0f1b2e;border:1px solid #1e293b;border-radius:12px;
                    padding:16px;display:flex;align-items:center;gap:14px;margin-bottom:12px">
          <div style="background:{icon_bg};width:46px;height:46px;border-radius:12px;flex-shrink:0;
                      display:flex;align-items:center;justify-content:center;font-size:1.3rem">{icon}</div>
          <div style="line-height:1.25">
            <div style="font-size:1.55rem;font-weight:800;color:#f1f5f9">{value}</div>
            <div style="font-size:0.84rem;color:#cbd5e1">{label}</div>
            <div style="font-size:0.68rem;color:#64748b">{sub}</div>
          </div></div>"""

    # ── Stat cards (left 2x2) + Recent Activity (right) ───────────
    left, right = st.columns([2, 1.35])
    with left:
        sc_a, sc_b = st.columns(2)
        sc_a.markdown(_stat_card("💼", "#2563eb", active,            "Active Projects",   "In Progress"), unsafe_allow_html=True)
        sc_b.markdown(_stat_card("✅", "#16a34a", completed_month,   "Completed",         "This month"),  unsafe_allow_html=True)
        sc_c, sc_d = st.columns(2)
        sc_c.markdown(_stat_card("🏛️", "#16a34a", subsidy_disbursed, "Subsidy Disbursed", "Received"),    unsafe_allow_html=True)
        sc_d.markdown(_stat_card("⏳", "#f59e0b", subsidy_pending,   "Subsidy",           "Pending"),     unsafe_allow_html=True)

        # Projects by Status — fills the space under the stat cards
        if not df.empty and "project_status" in df.columns:
            with st.container(border=True, key="npcard_pie"):
                st.markdown('<div style="font-weight:700;font-size:0.9rem;color:#e2e8f0;margin-bottom:4px">📊 PROJECTS BY STATUS</div>', unsafe_allow_html=True)
                _sc  = df["project_status"].value_counts()
                _clr = {"completed":"#22c55e","in_progress":"#3b82f6","planning":"#f59e0b",
                        "approved":"#8b5cf6","on_hold":"#f97316","cancelled":"#ef4444"}
                _figd = go.Figure(go.Pie(
                    labels=_sc.index, values=_sc.values, hole=0.62,
                    marker_colors=[_clr.get(s, "#94a3b8") for s in _sc.index],
                    textinfo="label+value", textfont_size=10,
                ))
                _figd.add_annotation(text=f"<b>{total}</b><br>Total", x=0.5, y=0.5,
                                     font=dict(size=14, color="#f1f5f9"), showarrow=False)
                _figd.update_layout(height=240, margin=dict(t=6, b=6, l=6, r=6),
                                    paper_bgcolor="rgba(0,0,0,0)", font_color="#f1f5f9",
                                    showlegend=True, legend=dict(bgcolor="rgba(0,0,0,0)", font_size=10))
                st.plotly_chart(_figd, use_container_width=True, key="ov_pie")

    with right:
        st.markdown('<div style="background:#0f1b2e;border:1px solid #1e293b;border-radius:12px;padding:16px 18px">', unsafe_allow_html=True)
        st.markdown('<div style="font-weight:700;font-size:0.9rem;color:#e2e8f0;margin-bottom:10px">📋 RECENT ACTIVITY</div>', unsafe_allow_html=True)
        recent_logs = get_activity_logs(supabase, limit=6)
        if recent_logs:
            _dotclr = ["#22c55e", "#3b82f6", "#f59e0b", "#22c55e", "#8b5cf6", "#ef4444"]
            html = ""
            for idx, lg in enumerate(recent_logs):
                _tm = ""
                try:
                    _tm = _dtnow.fromisoformat(str(lg.get("created_at")).replace("Z", "+00:00")).strftime("%I:%M %p")
                except Exception:
                    _tm = ""
                proj = f" for {lg.get('project_name')}" if lg.get("project_name") else ""
                html += (f'<div style="display:flex;gap:10px;align-items:flex-start;padding:7px 0">'
                         f'<div style="width:9px;height:9px;border-radius:50%;background:{_dotclr[idx % len(_dotclr)]};margin-top:5px;flex-shrink:0"></div>'
                         f'<div><span style="color:#94a3b8;font-size:0.72rem">{_tm}</span>'
                         f'<div style="color:#cbd5e1;font-size:0.78rem">{lg.get("action","")}{proj}</div></div></div>')
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#475569;font-size:0.82rem">No recent activity.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── MY PRIORITY QUEUE ─────────────────────────────────────────
    st.markdown("<div style='margin-top:6px'></div>", unsafe_allow_html=True)
    qh1, qh2 = st.columns([3, 1])
    qh1.markdown('<div style="font-weight:700;font-size:0.95rem;color:#e2e8f0;padding-top:6px">🗂️ MY PRIORITY QUEUE</div>', unsafe_allow_html=True)
    with qh2:
        if st.button("View All Projects ›", key="ov_view_all", use_container_width=True):
            st.session_state.nav = "Customer List"; st.rerun()

    # current stage per project (one query for the queue projects)
    _stage_map = {"in_progress": "In Progress", "planning": "Planning", "approved": "Approved",
                  "on_hold": "On Hold", "completed": "Completed", "cancelled": "Cancelled"}
    queue = [p for p in projects if p.get("project_status") not in ("completed", "cancelled")][:8] or projects[:8]
    _stage_by_proj = {}
    try:
        _ids = [p["id"] for p in queue]
        if _ids:
            _srows = supabase.table("project_steps").select("project_id,step_no,step_name,status")\
                .in_("project_id", _ids).order("step_no").execute().data or []
            for p in queue:
                ps = [s for s in _srows if s.get("project_id") == p["id"]]
                cur = next((s for s in ps if s.get("status") == "in_progress"), None) \
                    or next((s for s in ps if s.get("status") == "pending"), None)
                if cur:
                    _stage_by_proj[p["id"]] = cur.get("step_name", "")
    except Exception:
        pass

    # table header
    st.markdown("""
    <div style="display:flex;background:#0f1b2e;border:1px solid #1e293b;border-radius:8px 8px 0 0;padding:9px 14px;font-size:0.68rem;font-weight:700;color:#64748b;text-transform:uppercase">
      <span style="flex:1.2">Project ID</span><span style="flex:1.5">Customer Name</span>
      <span style="flex:1.3">Mobile Number</span><span style="flex:1.5">Current Stage</span>
      <span style="flex:1.5">Next Action</span><span style="flex:1">Due Date</span><span style="flex:0.4"></span>
    </div>""", unsafe_allow_html=True)

    if not queue:
        st.info("No projects yet. Add one in **Add Project**.")
    for p in queue:
        code  = p.get("project_code") or f"EPC-{str(p['id'])[:8].upper()}"
        stage = _stage_by_proj.get(p["id"]) or _stage_map.get(p.get("project_status", ""), "—")
        nxt   = "Follow-up required" if p.get("project_status") not in ("completed", "cancelled") else "—"
        due   = due_by_proj.get(p["id"], "—")
        if due == _today:
            due_disp = '<span style="color:#ef4444;font-weight:700">Today</span>'
        elif due != "—":
            due_disp = f'<span style="color:#f59e0b">{due}</span>'
        else:
            due_disp = '<span style="color:#64748b">—</span>'
        rcq = st.columns([1.2, 1.5, 1.3, 1.5, 1.5, 1, 0.4])
        rcq[0].markdown(f"<div style='font-size:0.78rem;color:#3b82f6;font-weight:600;padding-top:8px'>{code}</div>", unsafe_allow_html=True)
        rcq[1].markdown(f"<div style='font-size:0.8rem;padding-top:8px'>{p.get('customer_name','')}</div>", unsafe_allow_html=True)
        rcq[2].markdown(f"<div style='font-size:0.78rem;color:#94a3b8;padding-top:8px'>📞 {p.get('mobile','') or '-'}</div>", unsafe_allow_html=True)
        rcq[3].markdown(f"<div style='font-size:0.78rem;padding-top:8px'>{stage}</div>", unsafe_allow_html=True)
        rcq[4].markdown(f"<div style='font-size:0.78rem;color:#cbd5e1;padding-top:8px'>{nxt}</div>", unsafe_allow_html=True)
        rcq[5].markdown(f"<div style='font-size:0.78rem;padding-top:8px'>{due_disp}</div>", unsafe_allow_html=True)
        if rcq[6].button("📂", key=f"ovq_{p['id']}", help="Open project"):
            st.session_state.selected_project_id = p["id"]; st.rerun()

    # ══════════════════════════════════════════════════════════════
    #  ADMIN-ONLY OVERVIEW EXTRAS (employees never see this)
    # ══════════════════════════════════════════════════════════════
    if role == "admin":
        st.markdown("<hr style='margin:20px 0 10px;border-color:#16304d'>", unsafe_allow_html=True)
        st.markdown("### 🛡️ Admin Insights")

        # ── Company financial KPIs ────────────────────────────────
        _coll = round(total_paid / total_cost * 100, 1) if total_cost else 0
        fk = st.columns(4)
        fk[0].markdown(_stat_card("💰", "#2563eb", format_currency(total_cost),  "Total Project Value", f"{total} projects"), unsafe_allow_html=True)
        fk[1].markdown(_stat_card("✅", "#16a34a", format_currency(total_paid),  "Amount Received",     f"Collection {_coll}%"), unsafe_allow_html=True)
        fk[2].markdown(_stat_card("⏳", "#dc2626", format_currency(balance_due), "Outstanding Due",     "to be collected"), unsafe_allow_html=True)
        fk[3].markdown(_stat_card("📈", "#a78bfa", f"{comp_pct}%",               "Completion Rate",     f"{completed} done"), unsafe_allow_html=True)

        # ── Employee performance ──────────────────────────────────
        st.markdown("<div style='margin-top:6px'></div>", unsafe_allow_html=True)
        st.markdown("#### 👷 Employee Performance")
        try:
            _all_u = supabase.table("app_users").select("*").execute().data or []
        except Exception:
            _all_u = []
        emp_users      = [u for u in _all_u if u.get("status") == "approved" and u.get("role") != "admin"]
        pending_count  = sum(1 for u in _all_u if u.get("status") == "pending")

        from collections import defaultdict as _dd
        logs_all = get_activity_logs(supabase, limit=500)
        by_email = _dd(lambda: {"actions": 0, "projects": set(), "last": None})
        for lg in logs_all:                       # logs are newest-first
            em = lg.get("user_email")
            if not em:
                continue
            d = by_email[em]
            d["actions"] += 1
            if lg.get("project_name"):
                d["projects"].add(lg.get("project_name"))
            if d["last"] is None:
                d["last"] = lg.get("created_at")

        if pending_count:
            st.warning(f"🔔 {pending_count} user(s) awaiting approval — see the **Users** page.")

        if emp_users:
            perf_rows = []
            for u in emp_users:
                em = u.get("email")
                d  = by_email.get(em, {"actions": 0, "projects": set(), "last": None})
                perf_rows.append({
                    "Employee": u.get("name") or em,
                    "Code":     u.get("employee_code", "-"),
                    "Actions":  d["actions"],
                    "Projects Touched": len(d["projects"]),
                    "Last Active": _time_ago(d["last"]) if d["last"] else "—",
                })
            perf_rows.sort(key=lambda r: r["Actions"], reverse=True)
            pcol1, pcol2 = st.columns([1.3, 1])
            with pcol1:
                st.dataframe(pd.DataFrame(perf_rows), use_container_width=True, hide_index=True)
            with pcol2:
                _names = [r["Employee"] for r in perf_rows][:8]
                _acts  = [r["Actions"] for r in perf_rows][:8]
                _figp = go.Figure(go.Bar(y=_names, x=_acts, orientation="h", marker_color="#3b82f6",
                                         text=_acts, textposition="outside"))
                _figp.update_layout(height=max(180, 34 * len(_names)), margin=dict(t=10, b=10, l=10, r=10),
                                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                    font_color="#cbd5e1", showlegend=False,
                                    xaxis=dict(gridcolor="#16304d", title="Actions"),
                                    yaxis=dict(autorange="reversed"))
                st.plotly_chart(_figp, use_container_width=True, key="ov_emp_perf")
        else:
            st.caption("No approved employees yet.")


# ══════════════════════════════════════════════════════════════════════════════
#  EDIT CUSTOMERS PAGES (Customer List / Add Project)
# ══════════════════════════════════════════════════════════════════════════════
if nav in ("Customer List", "Add Project"):

    if nav == "Customer List":
        # ── Top bar ──────────────────────────────────────────────
        tb1, tb2, tb3 = st.columns([1.2, 2.5, 1.5])
        with tb1:
            if st.button("＋ Add New Project", use_container_width=True, type="primary", key="goto_add"):
                st.session_state.nav = "Add Project"; st.rerun()
        with tb2:
            ec_search = st.text_input("", placeholder="🔍  Search Customer Name / Mobile / Project ID / EPC Name...",
                                      key="ec_search", label_visibility="collapsed")
        with tb3:
            ec_status = st.selectbox("", ["All Status","Active","Completed","Cancelled"],
                                     key="ec_status", label_visibility="collapsed")

        # ── Filter data ──────────────────────────────────────────
        filtered = df.copy() if not df.empty else pd.DataFrame()
        if not filtered.empty:
            # derived display IDs so search can match the EPC name / Project ID shown in the table
            filtered["_epc_disp"] = filtered.apply(
                lambda r: r.get("project_code") or f"EPC-{str(r['id'])[:8].upper()}", axis=1)
            filtered["_pid_disp"] = filtered.apply(
                lambda r: r.get("project_code") or f"PRJ-{str(r['id'])[:6].upper()}", axis=1)
            if ec_search:
                mask = pd.Series(False, index=filtered.index)
                for col in ("customer_name","mobile","project_code","epc_name","_epc_disp","_pid_disp"):
                    if col in filtered.columns:
                        mask |= filtered[col].astype(str).str.contains(ec_search, case=False, na=False)
                filtered = filtered[mask]
            if ec_status == "Active":
                filtered = filtered[filtered["project_status"].isin(["planning","approved","in_progress","on_hold"])]
            elif ec_status == "Completed":
                filtered = filtered[filtered["project_status"] == "completed"]
            elif ec_status == "Cancelled":
                filtered = filtered[filtered["project_status"] == "cancelled"]

            # Sort by due amount (balance) — direction toggled via header arrow
            if "balance" in filtered.columns:
                filtered["_bal_sort"] = pd.to_numeric(filtered["balance"], errors="coerce").fillna(0)
                _asc = st.session_state.get("ec_sort_dir", "desc") == "asc"
                filtered = filtered.sort_values("_bal_sort", ascending=_asc)

        st.markdown(f"<div style='color:#64748b;font-size:0.8rem;margin:6px 0'>Total: {len(filtered)} Projects</div>", unsafe_allow_html=True)

        # reset to page 1 whenever the search/filter/sort changes
        _filter_sig = f"{ec_search}|{ec_status}|{st.session_state.get('ec_sort_dir','desc')}"
        if st.session_state.get("ec_filter_sig") != _filter_sig:
            st.session_state.ec_filter_sig = _filter_sig
            st.session_state.ec_page = 1

        # ── Two-column layout: list + quick edit ─────────────────
        list_col, qe_col = st.columns([2, 1])

        with list_col:
            # Table header — DUE AMOUNT has a clickable sort arrow
            hd1,hd2,hd3,hd4,hd5,hd6,hd7 = st.columns([1.6,1,1,1,0.9,0.9,0.4])
            _hstyle = "font-size:0.7rem;font-weight:700;color:#f97316;padding-top:6px"
            hd1.markdown(f"<div style='{_hstyle}'>PROJECT NAME</div>", unsafe_allow_html=True)
            hd2.markdown(f"<div style='{_hstyle}'>PROJECT ID</div>", unsafe_allow_html=True)
            hd3.markdown(f"<div style='{_hstyle}'>MOBILE</div>", unsafe_allow_html=True)
            hd4.markdown(f"<div style='{_hstyle}'>EPC NAME</div>", unsafe_allow_html=True)
            with hd5:
                _dir   = st.session_state.get("ec_sort_dir", "desc")
                _arrow = "▼" if _dir == "desc" else "▲"
                if st.button(f"DUE AMOUNT {_arrow}", key="sort_due", help="Sort by due amount"):
                    st.session_state.ec_sort_dir = "asc" if _dir == "desc" else "desc"
                    st.rerun()
            hd6.markdown(f"<div style='{_hstyle}'>STATUS</div>", unsafe_allow_html=True)
            hd7.markdown(f"<div style='{_hstyle}'>ACTION</div>", unsafe_allow_html=True)

            if filtered.empty:
                st.info("No projects found.")
            else:
                PAGE_SIZE = 20
                _n     = len(filtered)
                _pages = max(1, (_n + PAGE_SIZE - 1) // PAGE_SIZE)
                _pg    = min(max(1, int(st.session_state.get("ec_page", 1))), _pages)
                st.session_state.ec_page = _pg
                _start = (_pg - 1) * PAGE_SIZE
                _page_df = filtered.iloc[_start:_start + PAGE_SIZE]
                for _, row in _page_df.iterrows():
                    _st    = row.get("project_status","")
                    _bal   = float(row.get("balance", 0) or 0)
                    _code  = row.get("project_code") or f"EPC-{str(row['id'])[:8].upper()}"
                    _cid   = row.get("project_code") or f"PRJ-{str(row['id'])[:6].upper()}"
                    if _st == "completed":
                        _badge = '<span style="background:#16a34a;color:#fff;padding:2px 7px;border-radius:4px;font-size:0.65rem;font-weight:700">COMPLETED</span>'
                    elif _st == "cancelled":
                        _badge = '<span style="background:#dc2626;color:#fff;padding:2px 7px;border-radius:4px;font-size:0.65rem;font-weight:700">CANCELLED</span>'
                    else:
                        _badge = '<span style="background:#2563eb;color:#fff;padding:2px 7px;border-radius:4px;font-size:0.65rem;font-weight:700">ACTIVE</span>'

                    rc1,rc2,rc3,rc4,rc5,rc6,rc7 = st.columns([1.6,1,1,1,0.9,0.9,0.4])
                    if rc1.button(row.get("customer_name","") or "(no name)",
                                  key=f"qe_name_{row['id']}", use_container_width=True,
                                  help="Click to edit in Quick Edit"):
                        st.session_state.qe_pid = row["id"]; st.rerun()
                    rc2.markdown(f"<div style='padding-top:6px;font-size:0.75rem;color:#94a3b8'>{_cid}</div>", unsafe_allow_html=True)
                    rc3.markdown(f"<div style='padding-top:6px;font-size:0.75rem'>{row.get('mobile','') or '-'}</div>", unsafe_allow_html=True)
                    rc4.markdown(f"<div style='padding-top:6px;font-size:0.75rem;color:#64748b'>{_code}</div>", unsafe_allow_html=True)
                    rc5.markdown(f"<div style='padding-top:6px;font-size:0.8rem;font-weight:600'>₹ {_bal:,.0f}</div>", unsafe_allow_html=True)
                    rc6.markdown(f"<div style='padding-top:4px'>{_badge}</div>", unsafe_allow_html=True)
                    if rc7.button("📂", key=f"open_detail_{row['id']}", help="Open full project details"):
                        st.session_state.selected_project_id = row["id"]; st.rerun()

                # ── Pagination controls (20 per page) ─────────────
                if _pages > 1:
                    st.markdown(
                        f"<div style='color:#64748b;font-size:0.72rem;margin:8px 0 4px'>"
                        f"Showing {_start+1}–{min(_start+PAGE_SIZE, _n)} of {_n} · Page {_pg} of {_pages}</div>",
                        unsafe_allow_html=True)
                    _win = 7
                    _lo  = max(1, _pg - _win // 2)
                    _hi  = min(_pages, _lo + _win - 1)
                    _lo  = max(1, _hi - _win + 1)
                    _nums = list(range(_lo, _hi + 1))
                    _pcols = st.columns(len(_nums) + 2)
                    if _pcols[0].button("‹", key="ec_prev", disabled=_pg <= 1, use_container_width=True):
                        st.session_state.ec_page = _pg - 1; st.rerun()
                    for _i, _num in enumerate(_nums, start=1):
                        if _pcols[_i].button(str(_num), key=f"ec_pg_{_num}", use_container_width=True,
                                             type="primary" if _num == _pg else "secondary"):
                            st.session_state.ec_page = _num; st.rerun()
                    if _pcols[-1].button("›", key="ec_next", disabled=_pg >= _pages, use_container_width=True):
                        st.session_state.ec_page = _pg + 1; st.rerun()

        # ── Quick Edit panel ──────────────────────────────────────
        with qe_col:
          with st.container(border=True, key="npcard_quickedit"):
            st.markdown("""
            <div style="border-left:3px solid #f97316;padding-left:10px;margin-bottom:12px">
              <span style="font-weight:700;font-size:1rem">Quick Edit</span>
            </div>""", unsafe_allow_html=True)

            qe_pid  = st.session_state.get("qe_pid")
            qe_proj = next((p for p in projects if p.get("id") == qe_pid), None) if qe_pid else None

            if not qe_proj:
                st.markdown("""
                <div style="text-align:center;color:#475569;padding:10px 0">
                  <div style="font-size:1.5rem;margin-bottom:8px">📂</div>
                  <div style="font-size:0.82rem">Choose Project on Left<br>(click project name)</div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='font-weight:600;margin-bottom:8px;color:#f97316'>{qe_proj.get('customer_name','')}</div>", unsafe_allow_html=True)

                # ── Status buttons ────────────────────────────────
                st.markdown("<div style='font-size:0.78rem;color:#94a3b8;margin-bottom:6px'>Status</div>", unsafe_allow_html=True)
                _cur = qe_proj.get("project_status","")
                _is_done = _cur == "completed"
                _is_act  = _cur in ("planning","approved","in_progress","on_hold")
                _is_can  = _cur == "cancelled"

                qs1, qs2, qs3 = st.columns(3)
                with qs1:
                    if st.button("COMPLETED", key="qe_done", use_container_width=True,
                                 type="primary" if _is_done else "secondary"):
                        update_project(supabase, qe_pid, {"project_status":"completed"})
                        log_activity(supabase,"Status → Completed",entity_type="project",
                                     project_id=qe_pid,project_name=qe_proj.get("customer_name"))
                        st.toast("✅ Status → Completed", icon="✅"); st.rerun()
                with qs2:
                    if st.button("ACTIVE", key="qe_act", use_container_width=True,
                                 type="primary" if _is_act else "secondary"):
                        update_project(supabase, qe_pid, {"project_status":"in_progress"})
                        log_activity(supabase,"Status → Active",entity_type="project",
                                     project_id=qe_pid,project_name=qe_proj.get("customer_name"))
                        st.toast("✅ Status → Active", icon="✅"); st.rerun()
                with qs3:
                    if st.button("CANCELLED", key="qe_can", use_container_width=True,
                                 type="primary" if _is_can else "secondary"):
                        update_project(supabase, qe_pid, {"project_status":"cancelled"})
                        log_activity(supabase,"Status → Cancelled",entity_type="project",
                                     project_id=qe_pid,project_name=qe_proj.get("customer_name"))
                        st.toast("✅ Status → Cancelled", icon="✅"); st.rerun()

                # ── Notes ─────────────────────────────────────────
                st.markdown("<div style='font-size:0.78rem;color:#94a3b8;margin:10px 0 4px'>Notes</div>", unsafe_allow_html=True)
                qe_notes = st.text_area("", placeholder="Enter notes about the project...",
                                         value=str(qe_proj.get("notes","") or ""),
                                         key="qe_notes", label_visibility="collapsed", height=90)

                # ── Add Payment / Installment (linked to Financial Progress) ──
                _qe_total = float(qe_proj.get("total_cost", 0) or 0)
                _qe_paid  = sum(float(i.get("amount", 0) or 0) for i in
                                (supabase.table("installments").select("amount").eq("project_id", qe_pid).execute().data or []))
                _qe_due   = _qe_total - _qe_paid
                st.markdown(
                    f"<div style='font-size:0.78rem;color:#94a3b8;margin:10px 0 4px'>Add Payment / Installment</div>"
                    f"<div style='font-size:0.7rem;color:#64748b;margin-bottom:4px'>Received: "
                    f"<b style='color:#22c55e'>₹{_qe_paid:,.0f}</b> · Due: <b style='color:#ef4444'>₹{_qe_due:,.0f}</b></div>",
                    unsafe_allow_html=True)
                with st.form("qe_add_pay_form", clear_on_submit=True):
                    qa1, qa2 = st.columns(2)
                    with qa1:
                        qe_ptype = st.selectbox("Type", ["Advance Payment", "Installment", "Subsidy"], key="qe_pay_type_sel")
                    with qa2:
                        qe_pamt  = st.number_input("Amount (₹)", min_value=0.0, step=1000.0, value=None, placeholder="0", key="qe_p_amt") or 0.0
                    qe_pdate = st.date_input("Payment Date", key="qe_p_date")
                    if st.form_submit_button("➕ Add Payment", use_container_width=True):
                        if qe_pamt <= 0:
                            st.error("Enter an amount.")
                        else:
                            existing = supabase.table("installments").select("installment_no").eq("project_id", qe_pid).execute().data or []
                            next_no  = max([e.get("installment_no",0) for e in existing], default=0) + 1
                            _row = {"project_id": qe_pid, "installment_no": next_no,
                                    "amount": qe_pamt, "due_date": str(qe_pdate), "status": "paid"}
                            try:
                                supabase.table("installments").insert({**_row, "payment_type": qe_ptype}).execute()
                            except Exception:
                                supabase.table("installments").insert(_row).execute()
                            _new_paid = _qe_paid + qe_pamt
                            update_project(supabase, qe_pid, {"amount_paid": _new_paid, "balance": _qe_total - _new_paid})
                            log_activity(supabase, f"Payment: {qe_ptype}", entity_type="installment",
                                         project_id=qe_pid, project_name=qe_proj.get("customer_name"),
                                         details=f"₹{qe_pamt:,.0f} · {qe_pdate}")
                            st.toast("✅ Payment added!", icon="✅")
                            st.rerun()

                # ── Save ──────────────────────────────────────────
                if st.button("💾 Save Changes", use_container_width=True, type="primary", key="qe_save"):
                    update_project(supabase, qe_pid, {"notes": qe_notes})
                    st.toast("✅ Saved!", icon="✅")
                    st.rerun()

    if nav == "Add Project":
        import datetime as _dt
        st.markdown("""
        <div style="margin-bottom:18px">
          <div style="font-size:1.3rem;font-weight:800">Add New Solar Project / Customer</div>
          <div style="color:#64748b;font-size:0.85rem">Enter customer and project details to create a new solar EPC project</div>
        </div>""", unsafe_allow_html=True)

        # init session state
        if "draft_insts" not in st.session_state:
            st.session_state.draft_insts = []
        if "np_pay_mode" not in st.session_state:
            st.session_state.np_pay_mode = "CASH"

        left_col, right_col = st.columns([1.15, 1])

        # ── LEFT ──────────────────────────────────────────────────
        with left_col:

            # Section 1 — Customer Info
            with st.container(border=True, key="npcard_cust"):
                st.markdown("""<div style="display:flex;align-items:center;gap:8px;padding:2px 0 8px">
                    <div style="background:#dc2626;color:#fff;border-radius:50%;width:22px;height:22px;
                      display:flex;align-items:center;justify-content:center;font-size:0.7rem;font-weight:700;flex-shrink:0">1</div>
                    <span style="font-weight:700">Customer Information</span></div>""", unsafe_allow_html=True)

                ci1, ci2, ci3 = st.columns([1.2, 1, 1])
                with ci1: np_name    = st.text_input("Customer Name *", placeholder="Enter full name",        key="np_name")
                with ci2: np_mobile  = st.text_input("Mobile Number *",  placeholder="+91 mobile number",     key="np_mobile")
                with ci3: np_altmob  = st.text_input("Alternative Mobile", placeholder="+91 alternate",       key="np_altmob")

                ci4, ci5, ci6 = st.columns([1.2, 1, 0.9])
                with ci4: np_email   = st.text_input("Email Address",    placeholder="Enter email",           key="np_email")
                with ci5: np_aadhar  = st.text_input("Aadhar Number",    placeholder="Enter Aadhar number",   key="np_aadhar")
                with ci6: np_elecbill= st.text_input("Electricity Bill ID", placeholder="Bill ID",            key="np_elecbill")

            # Section 2 — Site Info
            with st.container(border=True, key="npcard_site"):
                st.markdown("""<div style="display:flex;align-items:center;gap:8px;padding:2px 0 8px">
                    <div style="background:#dc2626;color:#fff;border-radius:50%;width:22px;height:22px;
                      display:flex;align-items:center;justify-content:center;font-size:0.7rem;font-weight:700;flex-shrink:0">2</div>
                    <span style="font-weight:700">Site Information</span></div>""", unsafe_allow_html=True)

                np_addr = st.text_input("Installation Address *", placeholder="Enter complete installation address", key="np_addr")

                si1, si2, si3 = st.columns(3)
                with si1: np_village  = st.text_input("Village / Locality", placeholder="Village", key="np_village")
                with si2: np_taluka   = st.text_input("Taluka",             placeholder="Taluka",  key="np_taluka")
                with si3: np_district = st.text_input("District",           placeholder="District",key="np_district")

                si4, si5 = st.columns(2)
                with si4: np_pin    = st.text_input("Pincode",            placeholder="Pincode",              key="np_pin")
                with si5: np_latlng = st.text_input("Longitude, Latitude",placeholder="e.g. 72.8, 21.1",     key="np_latlng")

                st.markdown("<div style='color:#64748b;font-size:0.7rem;text-transform:uppercase;margin:6px 0 2px'>📅 Created Date</div>", unsafe_allow_html=True)
                np_created_date = st.date_input("", value=_dt.date.today(), key="np_created_date", label_visibility="collapsed")

        # ── RIGHT ─────────────────────────────────────────────────
        with right_col:

            # Execution Partner — Voltedge + EPC partners from the EPC page
            with st.container(border=True, key="npcard_exec"):
                st.markdown("<div style='color:#94a3b8;font-size:0.72rem;text-transform:uppercase;margin:2px 0 4px'>Execution Partner</div>", unsafe_allow_html=True)
                try:
                    _epc_rows = supabase.table("epcs").select("name").order("name").execute().data or []
                except Exception:
                    _epc_rows = []
                _exec_opts = ["Voltedge"] + [e["name"] for e in _epc_rows
                                             if e.get("name") and e["name"].lower() != "voltedge"]
                np_exec = st.selectbox("", _exec_opts, key="np_exec", label_visibility="collapsed")

            # Section 3 — Project Info
            with st.container(border=True, key="npcard_proj"):
                st.markdown("""<div style="display:flex;align-items:center;gap:8px;padding:2px 0 8px">
                    <div style="background:#dc2626;color:#fff;border-radius:50%;width:22px;height:22px;
                      display:flex;align-items:center;justify-content:center;font-size:0.7rem;font-weight:700;flex-shrink:0">3</div>
                    <span style="font-weight:700">Project Information</span></div>""", unsafe_allow_html=True)

                pi1, pi2 = st.columns(2)
                with pi1: np_size  = st.number_input("System Size (kWp) *", min_value=0.0, step=0.5, value=None, placeholder="0", key="np_size")
                with pi2: np_conn  = st.selectbox("Connection Type *", ["On-Grid","Off-Grid","Hybrid"], key="np_conn")

                _status_disp = st.selectbox("Project Status", ["Active","Completed"], key="np_status")
                np_status    = "completed" if _status_disp == "Completed" else "in_progress"

            # ── Payment Mode — 2 buttons only ───────────────────
            _pm = st.session_state.get("np_pay_mode", "CASH")
            st.markdown("<div style='color:#94a3b8;font-size:0.78rem;margin:8px 0 6px;text-transform:uppercase'>PAYMENT MODE</div>", unsafe_allow_html=True)
            pm1, pm2 = st.columns(2)
            with pm1:
                if st.button("CASH", use_container_width=True, key="pm_cash",
                             type="primary" if _pm == "CASH" else "secondary"):
                    st.session_state.np_pay_mode = "CASH"; st.rerun()
            with pm2:
                if st.button("LOAN", use_container_width=True, key="pm_loan",
                             type="primary" if _pm == "LOAN" else "secondary"):
                    st.session_state.np_pay_mode = "LOAN"; st.rerun()

            st.markdown("<div style='margin-top:6px'></div>", unsafe_allow_html=True)

            # ── Financial fields — differ by mode ───────────────
            if "np_subsidy_status" not in st.session_state:
                st.session_state.np_subsidy_status = "pending"

            if True:  # CASH/LOAN financial widget — identical for admin and employee
                # Total Project Cost — manual, always first (above Advance)
                np_cost    = st.number_input("TOTAL PROJECT COST (₹)", min_value=0.0, step=1000.0, value=None, placeholder="0", key="np_cost") or 0.0
                np_advance = st.number_input("ADVANCE AMOUNT (₹)",     min_value=0.0, step=1000.0, value=None, placeholder="0", key="np_advance") or 0.0

                # Subsidy — compact field + Pending / Disbursed toggle beside it
                st.markdown("<div style='color:#94a3b8;font-size:0.78rem;margin:6px 0 2px;text-transform:uppercase'>Subsidy Amount (₹)</div>", unsafe_allow_html=True)
                sb1, sb2, sb3 = st.columns([1.4, 0.8, 0.9])
                with sb1:
                    np_subsidy = st.number_input("", min_value=0.0, step=1000.0, value=None, placeholder="0",
                                                 key="np_subsidy", label_visibility="collapsed") or 0.0
                with sb2:
                    if st.button("Pending", use_container_width=True, key="sub_pending",
                                 type="primary" if st.session_state.np_subsidy_status == "pending" else "secondary"):
                        st.session_state.np_subsidy_status = "pending"; st.rerun()
                with sb3:
                    if st.button("Disbursed", use_container_width=True, key="sub_disbursed",
                                 type="primary" if st.session_state.np_subsidy_status == "disbursed" else "secondary"):
                        st.session_state.np_subsidy_status = "disbursed"; st.rerun()

                _sub_status  = st.session_state.np_subsidy_status
                _sub_counted = np_subsidy if _sub_status == "disbursed" else 0.0

                if _pm == "LOAN":
                    np_bankloan = st.number_input("BANK LOAN AMOUNT (₹)",      min_value=0.0, step=1000.0, value=None, placeholder="0", key="np_bankloan") or 0.0
                    np_bankquot = st.number_input("BANK QUOTATION AMOUNT (₹)", min_value=0.0, step=1000.0, value=None, placeholder="0", key="np_bankquot") or 0.0
                    _inst_src = st.session_state.get("bank_insts", [])
                else:
                    np_bankloan = np_bankquot = 0.0
                    _inst_src = st.session_state.get("draft_insts", [])

                # Only PAID installments reduce the due amount; pending ones don't count yet
                _inst_sum = sum(float(i.get("amount", 0) or 0) for i in _inst_src if i.get("status") == "paid")

                # ── Due Amount = Cost − Advance − Subsidy(if disbursed) − PAID Installments ──
                np_balance = np_cost - np_advance - _sub_counted - _inst_sum
                _sub_note  = "incl. subsidy" if _sub_status == "disbursed" else "subsidy pending — excluded"
                _due_clr   = "#22c55e" if np_balance >= 0 else "#ef4444"
                st.markdown(f"""
                <div style="background:#0f172a;border-radius:8px;padding:10px 14px;margin-top:8px;border-left:3px solid {_due_clr}">
                  <div style="color:#64748b;font-size:0.68rem;text-transform:uppercase">Due Amount (auto)</div>
                  <div style="font-size:1.15rem;font-weight:800;color:{_due_clr}">{format_currency(np_balance)}</div>
                  <div style="color:#64748b;font-size:0.68rem">Cost − Advance − Subsidy − Paid Installments · {_sub_note}</div>
                </div>""", unsafe_allow_html=True)
            else:
                np_cost = np_advance = np_subsidy = np_bankloan = np_bankquot = 0.0
                _sub_status = "pending"
                np_balance = 0.0

            np_notes = st.text_area("Notes", placeholder="Any additional notes…", key="np_notes", height=60)

            # ── Installments — LOAN=Bank Side only, CASH=Customer Side only ──
            if _pm == "LOAN":
                if "bank_insts" not in st.session_state:
                    st.session_state.bank_insts = []
                inst_list_key = "bank_insts"
                inst_label    = "🏦 ADD INSTALLMENT FROM BANK SIDE"
                inst_sub      = "(MOSTLY 2 — 70% & 30%)"
                inst_form_key = "bank_inst_form"
                inst_del_key  = "del_bi"
            else:
                inst_list_key = "draft_insts"
                inst_label    = "🏛️ ADD INSTALLMENTS FROM CUSTOMER SIDE"
                inst_sub      = "(MOSTLY 3)"
                inst_form_key = "cust_inst_form"
                inst_del_key  = "del_ci"

            _inst_list = st.session_state.get(inst_list_key, [])

            st.markdown(f"""
            <div style="background:#1e293b;border-radius:10px;padding:12px 14px;margin-top:10px">
              <div style="font-weight:700;font-size:0.85rem;text-transform:uppercase">{inst_label}</div>
              <div style="color:#64748b;font-size:0.72rem">{inst_sub}</div>
            </div>""", unsafe_allow_html=True)

            # LOAN: bank installments must tally to the bank loan amount
            if _pm == "LOAN":
                _bankloan_now = float(st.session_state.get("np_bankloan", 0) or 0)
                _bank_used    = sum(float(i.get("amount", 0) or 0) for i in _inst_list)
                _bank_rem     = _bankloan_now - _bank_used
                if _bankloan_now <= 0:
                    _tally = "<b style='color:#94a3b8'>enter Bank Loan Amount above ↑</b>"
                elif abs(_bank_rem) < 0.01:
                    _tally = "<b style='color:#22c55e'>✓ Tallied</b>"
                elif _bank_rem < 0:
                    _tally = "<b style='color:#ef4444'>⚠ Exceeds loan</b>"
                else:
                    _tally = f"<b style='color:#f59e0b'>Remaining {format_currency(_bank_rem)}</b>"
                st.markdown(
                    f"<div style='font-size:0.72rem;color:#94a3b8;margin:6px 2px'>"
                    f"Installments: <b>{format_currency(_bank_used)}</b> / Bank Loan {format_currency(_bankloan_now)} · {_tally}</div>",
                    unsafe_allow_html=True)

            # Existing installments — delete button INLINE on same row
            for i, inst in enumerate(_inst_list):
                _clr = "#22c55e" if inst.get("status") == "paid" else "#f59e0b"
                rc1, rc2, rc3, rc4, rc5 = st.columns([0.4, 1.2, 1.2, 0.8, 0.5])
                rc1.markdown(f"<div style='padding-top:8px;font-size:0.8rem;color:#94a3b8'>#{inst['no']}</div>", unsafe_allow_html=True)
                rc2.markdown(f"<div style='padding-top:8px;font-size:0.8rem;font-weight:600'>{format_currency(inst['amount'])}</div>", unsafe_allow_html=True)
                rc3.markdown(f"<div style='padding-top:8px;font-size:0.8rem;color:#64748b'>{inst['due_date']}</div>", unsafe_allow_html=True)
                rc4.markdown(f"<div style='padding-top:8px;font-size:0.8rem;color:{_clr}'>{inst.get('status','pending').title()}</div>", unsafe_allow_html=True)
                if rc5.button("🗑️", key=f"{inst_del_key}_{i}", use_container_width=True):
                    st.session_state[inst_list_key].pop(i); st.rerun()

            # Add installment form — installment # is auto-incremented
            _next_no = len(_inst_list) + 1
            with st.form(inst_form_key, clear_on_submit=True):
                st.markdown(f"<div style='color:#64748b;font-size:0.75rem;margin-bottom:4px'>+ Add Installment #{_next_no} — Amount & Date</div>", unsafe_allow_html=True)
                fc1, fc2 = st.columns([1.4, 1])
                with fc1: f_amt = st.number_input("Amount (₹)", min_value=0.0, step=5000.0, value=None, placeholder="0", key=f"{inst_form_key}_amt")
                with fc2: f_due = st.date_input("Date", key=f"{inst_form_key}_due")
                f_st = st.selectbox("Status", ["pending","paid"], key=f"{inst_form_key}_st")
                if st.form_submit_button("➕ Add Installment", use_container_width=True):
                    f_amt = f_amt or 0.0
                    if f_amt <= 0:
                        st.error("❌ Enter an installment amount.")
                        st.stop()
                    # LOAN: bank installments total must not exceed bank loan amount
                    _bankloan_chk = float(st.session_state.get("np_bankloan", 0) or 0)
                    if _pm == "LOAN" and _bankloan_chk > 0:
                        _used = sum(float(i.get("amount", 0) or 0) for i in st.session_state.get(inst_list_key, []))
                        if _used + f_amt > _bankloan_chk + 0.001:
                            st.error(f"❌ Exceeds bank loan. Remaining capacity: {format_currency(_bankloan_chk - _used)}")
                            st.stop()
                    st.session_state[inst_list_key].append({
                        "no": _next_no, "amount": f_amt,
                        "due_date": str(f_due), "status": f_st
                    })
                    st.rerun()

        # ── SAVE button ────────────────────────────────────────────
        st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
        scol1, scol2 = st.columns([3, 1])
        with scol1:
            if st.button("💾  SAVE Project", use_container_width=True, key="save_project_btn",
                         type="primary"):
                if not st.session_state.get("np_name","").strip():
                    st.error("❌ Customer name is required.")
                else:
                    result = create_project(supabase, {
                        "customer_name":        st.session_state.np_name.strip(),
                        "mobile":               st.session_state.get("np_mobile",""),
                        "alt_mobile":           st.session_state.get("np_altmob",""),
                        "email":                st.session_state.get("np_email",""),
                        "aadhar_number":        st.session_state.get("np_aadhar",""),
                        "electricity_bill_id":  st.session_state.get("np_elecbill",""),
                        "location":             st.session_state.get("np_addr",""),
                        "installation_address": st.session_state.get("np_addr",""),
                        "village":              st.session_state.get("np_village",""),
                        "taluka":               st.session_state.get("np_taluka",""),
                        "district":             st.session_state.get("np_district",""),
                        "pincode":              st.session_state.get("np_pin",""),
                        "longitude_latitude":   st.session_state.get("np_latlng",""),
                        "execution_partner":    st.session_state.get("np_exec","Voltedge"),
                        "system_size_kwp":      st.session_state.get("np_size", 0) or 0,
                        "connection_type":      st.session_state.get("np_conn","On-Grid"),
                        "project_status":       np_status,
                        "payment_mode":         st.session_state.get("np_pay_mode","CASH"),
                        "total_cost":           np_cost,
                        "amount_paid":          np_cost - np_balance,
                        "advance_amount":       np_advance,
                        "subsidy_amount":       np_subsidy,
                        "subsidy_status":       st.session_state.get("np_subsidy_status","pending"),
                        "bank_loan_amount":     np_bankloan,
                        "bank_quotation_amount":np_bankquot,
                        "balance":              np_balance,
                        "net_payable":          np_cost - np_subsidy,
                        "notes":                st.session_state.get("np_notes",""),
                        "created_at":           str(st.session_state.get("np_created_date", _dt.date.today())),
                    })
                    if result:
                        # Save customer-side installments
                        for inst in st.session_state.get("draft_insts", []):
                            supabase.table("installments").insert({
                                "project_id": result["id"], "installment_no": inst["no"],
                                "amount": inst["amount"], "due_date": inst["due_date"], "status": inst["status"],
                            }).execute()
                        # Save bank-side installments
                        for inst in st.session_state.get("bank_insts", []):
                            supabase.table("installments").insert({
                                "project_id": result["id"], "installment_no": inst["no"],
                                "amount": inst["amount"], "due_date": inst["due_date"], "status": inst["status"],
                            }).execute()
                        st.session_state.draft_insts = []
                        st.session_state.bank_insts  = []
                        st.toast(f"✅ Project saved for {result.get('customer_name','customer')}!", icon="✅")
                        st.rerun()
                    else:
                        st.error("❌ Project was NOT saved — see the error above. Fix the database column and try again.")
        with scol2:
            if st.button("🗑️  Clear", use_container_width=True, key="clear_project_btn"):
                for k in ["np_name","np_mobile","np_altmob","np_email","np_aadhar","np_elecbill",
                          "np_addr","np_village","np_taluka","np_district","np_pin","np_latlng",
                          "np_exec","np_size","np_conn","np_status","np_notes","draft_insts"]:
                    st.session_state.pop(k, None)
                st.toast("🗑️ Form cleared", icon="🗑️"); st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  REPORT PAGE — ADMIN ONLY
# ══════════════════════════════════════════════════════════════════════════════
if role == "admin" and nav == "Report":
    render_reports(supabase, projects, df)


# ══════════════════════════════════════════════════════════════════════════════
#  USERS PAGE — ADMIN ONLY
# ══════════════════════════════════════════════════════════════════════════════
if role == "admin" and nav == "Users":
    if True:
        st.markdown("#### 👤 User Management")

        try:
            all_users = supabase.table("app_users").select("*").order("created_at", desc=True).execute().data or []
        except Exception as e:
            st.error(f"Could not load users: {e}")
            all_users = []

        pending_users  = [u for u in all_users if u.get("status") == "pending"]
        approved_users = [u for u in all_users if u.get("status") == "approved"]
        rejected_users = [u for u in all_users if u.get("status") == "rejected"]

        # Pending approvals — highlighted
        if pending_users:
            st.markdown(f"### 🔔 Pending Approvals ({len(pending_users)})")
            for u in pending_users:
                pc1, pc2, pc3, pc4, pc5 = st.columns([0.5, 2, 2.5, 1.2, 1.2])
                with pc1:
                    if u.get("picture"):
                        st.image(u["picture"], width=36)
                with pc2:
                    st.write(f"**{u.get('name','Unknown')}**")
                with pc3:
                    st.write(u.get("email",""))
                with pc4:
                    if st.button("✅ Approve", key=f"approve_{u['id']}", use_container_width=True):
                        supabase.table("app_users").update({
                            "status": "approved", "role": "employee"
                        }).eq("id", u["id"]).execute()
                        st.toast(f"✅ {u.get('name','')} approved!", icon="✅")
                        st.rerun()
                with pc5:
                    if st.button("❌ Reject", key=f"reject_{u['id']}", use_container_width=True):
                        supabase.table("app_users").update({"status": "rejected"}).eq("id", u["id"]).execute()
                        st.toast(f"❌ {u.get('name','')} rejected.", icon="❌")
                        st.rerun()
            st.markdown("<hr style='margin:12px 0'>", unsafe_allow_html=True)
        else:
            st.success("✅ No pending approvals")
            st.markdown("<hr style='margin:12px 0'>", unsafe_allow_html=True)

        # All approved users
        st.markdown(f"**Approved Users ({len(approved_users)})**")
        for u in approved_users:
            uc1, uc2, uc3, uc4, uc5 = st.columns([0.5, 2, 2.5, 1.2, 1.2])
            with uc1:
                if u.get("picture"):
                    st.image(u["picture"], width=36)
            with uc2:
                st.write(f"**{u.get('name','Unknown')}**")
            with uc3:
                st.write(u.get("email",""))
            with uc4:
                cur_role = u.get("role","employee")
                new_role = st.selectbox("Role", ["employee","admin"],
                    index=0 if cur_role=="employee" else 1,
                    key=f"role_{u['id']}", label_visibility="collapsed")
                if new_role != cur_role:
                    supabase.table("app_users").update({"role": new_role}).eq("id", u["id"]).execute()
                    st.toast(f"✅ Role updated → {new_role}", icon="✅"); st.rerun()
            with uc5:
                if u.get("email") != "voltedgeenergysolutions011@gmail.com":
                    if st.button("🚫 Revoke", key=f"revoke_{u['id']}", use_container_width=True):
                        supabase.table("app_users").update({"status": "rejected"}).eq("id", u["id"]).execute()
                        st.toast("🚫 Access revoked", icon="🚫"); st.rerun()

        if rejected_users:
            with st.expander(f"Rejected Users ({len(rejected_users)})"):
                for u in rejected_users:
                    rc1, rc2, rc3, rc4 = st.columns([2, 2.5, 1.2, 1.2])
                    rc1.write(u.get("name",""))
                    rc2.write(u.get("email",""))
                    rc3.write("Rejected")
                    if rc4.button("🔁 Re-approve", key=f"reapprove_{u['id']}"):
                        supabase.table("app_users").update({"status":"approved","role":"employee"}).eq("id",u["id"]).execute()
                        st.toast("✅ Re-approved", icon="✅"); st.rerun()

        # ── Full Activity Log ─────────────────────────────────────
        st.markdown("<hr style='margin:20px 0'>", unsafe_allow_html=True)
        st.markdown("#### 🕐 Employee Activity Log")

        # Filter controls
        lc1, lc2, lc3 = st.columns([2, 2, 1])
        with lc1:
            filter_user = st.selectbox(
                "Filter by Employee",
                ["All Employees"] + [f"{u.get('name','')} ({u.get('email','')})" for u in approved_users if u.get("email") != "voltedgeenergysolutions011@gmail.com"],
                key="log_user_filter"
            )
        with lc2:
            filter_type = st.selectbox(
                "Filter by Action Type",
                ["All Actions", "project", "step", "note", "document", "installment"],
                key="log_type_filter"
            )
        with lc3:
            log_limit = st.selectbox("Show", [10, 25, 50, 100], key="log_limit")

        # Extract email from filter selection
        filter_email = None
        if filter_user != "All Employees":
            filter_email = filter_user.split("(")[-1].rstrip(")")

        all_logs = get_activity_logs(supabase, limit=log_limit, user_email=filter_email)

        # Filter by type if selected
        if filter_type != "All Actions":
            all_logs = [l for l in all_logs if l.get("entity_type") == filter_type]

        # Show stats row
        if all_logs:
            unique_users    = len(set(l.get("user_email") for l in all_logs))
            project_actions = sum(1 for l in all_logs if l.get("entity_type") == "project")
            step_actions    = sum(1 for l in all_logs if l.get("entity_type") == "step")

            ls1, ls2, ls3, ls4 = st.columns(4)
            ls1.metric("Total Actions",    len(all_logs))
            ls2.metric("Active Users",     unique_users)
            ls3.metric("Project Changes",  project_actions)
            ls4.metric("Step Updates",     step_actions)

            st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
            _render_activity_feed(all_logs)
        else:
            st.info("No activity logs found for the selected filter.")


# ══════════════════════════════════════════════════════════════════════════════
#  EPC PARTNERS PAGE — ADMIN ONLY
# ══════════════════════════════════════════════════════════════════════════════
if role == "admin" and nav == "EPC Partners":
    render_epc_page(supabase, projects)


# ══════════════════════════════════════════════════════════════════════════════
#  SETTINGS PAGE
# ══════════════════════════════════════════════════════════════════════════════
if nav == "Settings":
    _uname = st.session_state.get("user_name", "N/A")
    _umail = st.session_state.get("user_email", "N/A")
    _upic  = st.session_state.get("user_picture", "")
    _eid   = st.session_state.get("user_code", "VE-001")
    _role_badge = ("<span style='background:#dc262622;color:#ef4444;border:1px solid #dc2626;"
                   "padding:2px 10px;border-radius:6px;font-size:0.72rem;font-weight:700'>🔴 Admin</span>"
                   if role == "admin" else
                   "<span style='background:#2563eb22;color:#3b82f6;border:1px solid #2563eb;"
                   "padding:2px 10px;border-radius:6px;font-size:0.72rem;font-weight:700'>🔵 Employee</span>")
    _stat_badge = ("<span style='background:#16a34a22;color:#22c55e;border:1px solid #16a34a;"
                   f"padding:2px 10px;border-radius:6px;font-size:0.72rem;font-weight:700'>✓ {status.title()}</span>")
    _avatar = (f"<img src='{_upic}' style='width:120px;height:120px;border-radius:14px;object-fit:cover'>"
               if _upic else
               f"<div style='width:120px;height:120px;border-radius:14px;background:#16a34a;display:flex;"
               f"align-items:center;justify-content:center;font-size:3rem;font-weight:800;color:#fff'>{(_uname[:1].upper() if _uname else 'U')}</div>")

    st.markdown("""
    <div style="margin-bottom:14px">
      <div style="font-size:1.4rem;font-weight:800;color:#f1f5f9">SETTINGS</div>
      <div style="color:#64748b;font-size:0.85rem">Manage your profile and account settings.</div>
    </div>""", unsafe_allow_html=True)

    set_col, _ = st.columns([1.4, 1])
    with set_col:
        # PROFILE INFORMATION card
        st.markdown(f"""
        <div style="background:#0f1b2e;border:1px solid #1e293b;border-radius:12px;padding:18px 20px">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px">
            <span>👤</span><span style="font-weight:700;color:#e2e8f0;letter-spacing:0.5px">PROFILE INFORMATION</span>
          </div>
          <div style="display:flex;gap:22px;align-items:flex-start">
            <div>{_avatar}</div>
            <div style="flex:1">
              <div style="margin-bottom:12px"><div style="color:#64748b;font-size:0.68rem;text-transform:uppercase">Name</div>
                <div style="color:#f1f5f9;font-weight:600">{_uname}</div></div>
              <div style="margin-bottom:12px"><div style="color:#64748b;font-size:0.68rem;text-transform:uppercase">Email</div>
                <div style="color:#3b82f6;font-weight:600">{_umail}</div></div>
              <div style="margin-bottom:12px"><div style="color:#64748b;font-size:0.68rem;text-transform:uppercase">Employee ID</div>
                <div style="color:#f1f5f9;font-weight:600">{_eid}</div></div>
              <div style="margin-bottom:12px"><div style="color:#64748b;font-size:0.68rem;text-transform:uppercase">Role</div>
                <div style="margin-top:3px">{_role_badge}</div></div>
              <div><div style="color:#64748b;font-size:0.68rem;text-transform:uppercase">Status</div>
                <div style="margin-top:3px">{_stat_badge}</div></div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

        # Stat cards
        st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
        stc1, stc2 = st.columns(2)
        stc1.markdown(f"""
        <div style="background:#0f1b2e;border:1px solid #1e293b;border-radius:12px;padding:16px;display:flex;align-items:center;gap:14px">
          <div style="background:#2563eb;width:46px;height:46px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.2rem">💼</div>
          <div><div style="color:#64748b;font-size:0.74rem">Projects Assigned</div>
          <div style="font-size:1.5rem;font-weight:800;color:#f1f5f9">{total}</div></div>
        </div>""", unsafe_allow_html=True)
        stc2.markdown(f"""
        <div style="background:#0f1b2e;border:1px solid #1e293b;border-radius:12px;padding:16px;display:flex;align-items:center;gap:14px">
          <div style="background:#16a34a;width:46px;height:46px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.2rem">📊</div>
          <div><div style="color:#64748b;font-size:0.74rem">Active Projects</div>
          <div style="font-size:1.5rem;font-weight:800;color:#f1f5f9">{active}</div></div>
        </div>""", unsafe_allow_html=True)

        # Logout card
        st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div style="background:#0f1b2e;border:1px solid #1e293b;border-radius:12px;padding:14px 16px;display:flex;align-items:center;gap:14px">
          <div style="background:#dc262622;width:46px;height:46px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.2rem">🚪</div>
          <div><div style="color:#f1f5f9;font-weight:700;font-size:0.9rem">Logout</div>
          <div style="color:#64748b;font-size:0.74rem">Sign out from your account</div></div>
        </div>""", unsafe_allow_html=True)
        if st.button("🚪  Sign Out", use_container_width=True, key="settings_logout"):
            logout()

    # Footer
    st.markdown("""
    <div style="text-align:center;margin-top:30px;padding-top:14px;border-top:1px solid #1e293b">
      <div style="color:#3b82f6;font-weight:700;font-size:0.85rem">VoltEdge ERP v2.0</div>
      <div style="color:#475569;font-size:0.72rem">© 2026 VoltEdge Energy Solutions. All rights reserved.</div>
    </div>""", unsafe_allow_html=True)
