"""VOLTEDGE Dashboard — Role-based (Admin / Employee)"""

import streamlit as st
import sys
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from modules.supabase_client import (
    get_supabase_client, get_projects, get_project_by_id,
    create_project, update_project, get_activity_logs,
)
from modules.auth import (
    init_auth, handle_oauth_callback, login_form, logout,
    load_user_from_db, is_admin,
)
from modules.utils import format_currency
from modules.project_detail import render_project_detail

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
        proj_html    = f'<span style="color:#64748b"> · {project}</span>' if project else ""
        details_html = (f'<div style="font-size:0.72rem;color:#475569;margin-top:2px;'
                        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{details}</div>'
                        if details else "")
        html += f"""
        <div style="display:flex;align-items:flex-start;padding:10px 16px;border-bottom:1px solid #334155;gap:10px">
          <div style="flex-shrink:0;margin-top:2px">{avatar}</div>
          <div style="flex:1;min-width:0">
            <div style="font-size:0.82rem">
              <span style="font-weight:700;color:#f1f5f9">{name}</span>
              <span style="color:#94a3b8;font-size:0.75rem;margin-left:6px">{email}</span>
            </div>
            <div style="font-size:0.82rem;color:#cbd5e1;margin-top:2px">{icon} {action}{proj_html}</div>
            {details_html}
          </div>
          <div style="font-size:0.72rem;color:#475569;flex-shrink:0;white-space:nowrap">{ago}</div>
        </div>"""
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


st.set_page_config(
    page_title="VOLTEDGE Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding-top: 1.2rem; padding-bottom: 1rem; }
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
</style>
""", unsafe_allow_html=True)

init_auth()
handle_oauth_callback()

# ── LOGIN ─────────────────────────────────────────────────────────────────────
if not st.session_state.get("authenticated", False):
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
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
        name = st.session_state.get("user_name") or st.session_state.get("user_email","User")
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


# ── PROJECT DETAIL (overrides tabs) ──────────────────────────────────────────
if st.session_state.get("selected_project_id"):
    pid     = st.session_state.selected_project_id
    project = get_project_by_id(supabase, pid)
    if project:
        render_header("detail")
        render_project_detail(supabase, project, role=role)
    else:
        st.session_state.selected_project_id = None
        st.rerun()
    st.stop()


# ── MAIN DASHBOARD ────────────────────────────────────────────────────────────
render_header("main")

# Build tab list based on role
if role == "admin":
    tabs = st.tabs(["🏠 Overview", "👥 Edit Customers", "📊 Report", "👤 Users", "⚙️ Settings"])
    t1, t2, t3, t4, t5 = tabs
else:
    tabs = st.tabs(["🏠 Overview", "👥 Edit Customers", "⚙️ Settings"])
    t1, t2, t5 = tabs
    t3 = None
    t4 = None


# ══════════════════════════════════════════════════════════════════════════════
#  OVERVIEW TAB
# ══════════════════════════════════════════════════════════════════════════════
with t1:
    # Project count metrics (both roles)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📊 Total Projects",  total)
    c2.metric("🔄 Active Projects", active)
    c3.metric("✅ Completed",        completed)
    c4.metric("❌ Cancelled",        cancelled)

    st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)

    # Financial row — ADMIN ONLY
    if role == "admin":
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("💰 Total Project Value", format_currency(total_cost))
        f2.metric("✅ Amount Received",      format_currency(total_paid))
        f3.metric("⏳ Balance Receivable",   format_currency(balance_due))
        f4.metric("📈 Completion Rate",      f"{comp_pct}%")
    else:
        st.metric("📈 Completion Rate", f"{comp_pct}%")

    st.markdown("<hr style='margin:16px 0'>", unsafe_allow_html=True)

    if not df.empty:
        ch1, ch2 = st.columns(2)

        with ch1:
            st.markdown("**Projects by Status**")
            sc  = df["project_status"].value_counts() if "project_status" in df.columns else pd.Series()
            clr = {"completed":"#22c55e","in_progress":"#3b82f6","planning":"#f59e0b",
                   "approved":"#8b5cf6","on_hold":"#f97316","cancelled":"#ef4444"}
            fig_d = go.Figure(go.Pie(
                labels=sc.index, values=sc.values, hole=0.62,
                marker_colors=[clr.get(s,"#94a3b8") for s in sc.index],
                textinfo="label+value", textfont_size=11,
            ))
            fig_d.add_annotation(text=f"<b>{total}</b><br>Total",
                                  x=0.5, y=0.5, font=dict(size=15,color="#f1f5f9"), showarrow=False)
            fig_d.update_layout(height=270, margin=dict(t=10,b=10,l=10,r=10),
                                paper_bgcolor="rgba(0,0,0,0)", font_color="#f1f5f9",
                                showlegend=True, legend=dict(bgcolor="rgba(0,0,0,0)", font_size=11))
            st.plotly_chart(fig_d, use_container_width=True)

        with ch2:
            st.markdown("**Projects by System Size**")
            if "system_size_kwp" in df.columns:
                bins   = [0, 3, 5, 10, 20, float("inf")]
                labels = ["1-3 kWp","3-5 kWp","5-10 kWp","10-20 kWp","20+ kWp"]
                df["_b"] = pd.cut(df["system_size_kwp"].fillna(0), bins=bins, labels=labels)
                sz = df["_b"].value_counts().reindex(labels, fill_value=0)
                fig_b = go.Figure(go.Bar(x=sz.index, y=sz.values,
                                         marker_color="#22c55e", text=sz.values, textposition="outside"))
                fig_b.update_layout(height=270, margin=dict(t=10,b=30,l=10,r=10),
                                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                    font_color="#f1f5f9",
                                    xaxis=dict(gridcolor="#334155"), yaxis=dict(gridcolor="#334155"))
                st.plotly_chart(fig_b, use_container_width=True)

        st.markdown("<hr style='margin:8px 0'>", unsafe_allow_html=True)
        st.markdown("**Recent Projects** — click 📂 to open project details")

        for _, row in df.head(10).iterrows():
            rc1, rc2, rc3, rc4, rc5 = st.columns([2.5, 1.5, 0.8, 1.5, 0.7])
            rc1.write(row.get("customer_name",""))
            rc2.write(row.get("location","") or "-")
            rc3.write(f"{row.get('system_size_kwp',0)} kWp")
            rc4.write(row.get("project_status","").replace("_"," ").title())
            if rc5.button("📂", key=f"ov_view_{row['id']}", help="Open project"):
                st.session_state.selected_project_id = row["id"]
                st.rerun()
    else:
        st.info("No project data yet. Add projects in the **Edit Customers** tab.")

    # ── Last Activity (admin only) ────────────────────────────────
    if role == "admin":
        st.markdown("<hr style='margin:16px 0'>", unsafe_allow_html=True)
        st.markdown("**🕐 Last Activity**")
        recent_logs = get_activity_logs(supabase, limit=8)
        if recent_logs:
            _render_activity_feed(recent_logs)
        else:
            st.caption("No activity recorded yet.")


# ══════════════════════════════════════════════════════════════════════════════
#  EDIT CUSTOMERS TAB
# ══════════════════════════════════════════════════════════════════════════════
with t2:
    st.markdown("#### 👥 Customer & Project Management")
    sub1, sub2 = st.tabs(["📋 View & Edit", "➕ Add New Project"])

    with sub1:
        if df.empty:
            st.info("No projects found.")
        else:
            sc1, sc2 = st.columns([2, 1])
            with sc1:
                search = st.text_input("🔍 Search", placeholder="Name or location…")
            with sc2:
                sopts = sorted(df["project_status"].dropna().unique().tolist()) if "project_status" in df.columns else []
                sf    = st.multiselect("Filter by Status", options=sopts)

            filtered = df.copy()
            if search:
                mask = pd.Series(False, index=filtered.index)
                for col in ("customer_name","location"):
                    if col in filtered.columns:
                        mask |= filtered[col].astype(str).str.contains(search, case=False, na=False)
                filtered = filtered[mask]
            if sf:
                filtered = filtered[filtered["project_status"].isin(sf)]

            st.caption(f"{len(filtered)} project(s) shown")

            for _, row in filtered.iterrows():
                pr1, pr2, pr3, pr4, pr5 = st.columns([2.5, 1.5, 0.8, 1.5, 0.7])
                pr1.write(row.get("customer_name",""))
                pr2.write(row.get("location","") or "-")
                pr3.write(f"{row.get('system_size_kwp',0)} kWp")
                pr4.write(row.get("project_status","").replace("_"," ").title())
                if pr5.button("📂", key=f"ec_view_{row['id']}"):
                    st.session_state.selected_project_id = row["id"]
                    st.rerun()

            # Quick edit — show financial fields only for admin
            st.markdown("---")
            st.markdown("**✏️ Quick Edit**")
            names    = filtered["customer_name"].fillna("Unknown").tolist() if "customer_name" in filtered.columns else []
            sel_name = st.selectbox("Select project", names, key="edit_sel")
            if sel_name:
                row      = filtered[filtered["customer_name"] == sel_name].iloc[0]
                statuses = ["planning","approved","in_progress","completed","on_hold","cancelled"]
                cur_s    = row.get("project_status","planning")
                with st.form("edit_project_form"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        new_status = st.selectbox("Status", statuses,
                            index=statuses.index(cur_s) if cur_s in statuses else 0)
                        new_loc    = st.text_input("Location", value=str(row.get("location","") or ""))
                        new_size   = st.number_input("System Size (kWp)", value=float(row.get("system_size_kwp",0) or 0), step=0.5)
                    with ec2:
                        if role == "admin":
                            new_cost  = st.number_input("Total Cost (₹)", value=float(row.get("total_cost",0) or 0), step=1000.0)
                            new_paid  = st.number_input("Amount Paid (₹)", value=float(row.get("amount_paid",0) or 0), step=1000.0)
                        new_notes = st.text_area("Notes", value=str(row.get("notes","") or ""))

                    if st.form_submit_button("💾 Save Changes", use_container_width=True):
                        payload = {
                            "project_status":  new_status,
                            "location":        new_loc,
                            "system_size_kwp": new_size,
                            "notes":           new_notes,
                        }
                        if role == "admin":
                            payload["total_cost"]  = new_cost
                            payload["amount_paid"] = new_paid
                            payload["balance"]     = new_cost - new_paid
                        update_project(supabase, row["id"], payload)
                        st.success("✅ Updated!")
                        st.rerun()

    with sub2:
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
            st.markdown("""<div style="background:#1e293b;border-radius:10px;padding:4px 14px 2px;margin-bottom:4px">
              <div style="display:flex;align-items:center;gap:8px;padding:10px 0 8px">
                <div style="background:#dc2626;color:#fff;border-radius:50%;width:22px;height:22px;
                  display:flex;align-items:center;justify-content:center;font-size:0.7rem;font-weight:700;flex-shrink:0">1</div>
                <span style="font-weight:700">Customer Information</span>
              </div></div>""", unsafe_allow_html=True)

            ci1, ci2, ci3 = st.columns([1.2, 1, 1])
            with ci1: np_name    = st.text_input("Customer Name *", placeholder="Enter full name",        key="np_name")
            with ci2: np_mobile  = st.text_input("Mobile Number *",  placeholder="+91 mobile number",     key="np_mobile")
            with ci3: np_altmob  = st.text_input("Alternative Mobile", placeholder="+91 alternate",       key="np_altmob")

            ci4, ci5, ci6 = st.columns([1.2, 1, 0.9])
            with ci4: np_email   = st.text_input("Email Address",    placeholder="Enter email",           key="np_email")
            with ci5: np_aadhar  = st.text_input("Aadhar Number",    placeholder="Enter Aadhar number",   key="np_aadhar")
            with ci6: np_elecbill= st.text_input("Electricity Bill ID", placeholder="Bill ID",            key="np_elecbill")

            st.markdown("<div style='margin-top:6px'></div>", unsafe_allow_html=True)

            # Section 2 — Site Info
            st.markdown("""<div style="background:#1e293b;border-radius:10px;padding:4px 14px 2px;margin-bottom:4px">
              <div style="display:flex;align-items:center;gap:8px;padding:10px 0 8px">
                <div style="background:#dc2626;color:#fff;border-radius:50%;width:22px;height:22px;
                  display:flex;align-items:center;justify-content:center;font-size:0.7rem;font-weight:700;flex-shrink:0">2</div>
                <span style="font-weight:700">Site Information</span>
              </div></div>""", unsafe_allow_html=True)

            np_addr = st.text_input("Installation Address *", placeholder="Enter complete installation address", key="np_addr")

            si1, si2, si3 = st.columns(3)
            with si1: np_village  = st.text_input("Village / Locality", placeholder="Village", key="np_village")
            with si2: np_taluka   = st.text_input("Taluka",             placeholder="Taluka",  key="np_taluka")
            with si3: np_district = st.text_input("District",           placeholder="District",key="np_district")

            si4, si5 = st.columns(2)
            with si4: np_pin    = st.text_input("Pincode",            placeholder="Pincode",              key="np_pin")
            with si5: np_latlng = st.text_input("Longitude, Latitude",placeholder="e.g. 72.8, 21.1",     key="np_latlng")

            # Created date
            st.markdown(f"""
            <div style="background:#1e293b;border-radius:8px;padding:12px 14px;margin-top:10px;display:flex;align-items:center;gap:10px">
              <span style="font-size:1.2rem">📅</span>
              <div><div style="color:#64748b;font-size:0.7rem;text-transform:uppercase">Created Date</div>
              <div style="font-weight:600">{_dt.date.today().strftime("%B %d, %Y")}</div></div>
            </div>""", unsafe_allow_html=True)

        # ── RIGHT ─────────────────────────────────────────────────
        with right_col:

            # Execution Partner
            st.markdown("""<div style="background:#1e293b;border-radius:10px;padding:12px 14px;margin-bottom:8px">
              <div style="color:#94a3b8;font-size:0.72rem;text-transform:uppercase;margin-bottom:6px">Execution Partner</div>""",
              unsafe_allow_html=True)
            np_exec = st.selectbox("", ["Voltedge", "Manual"], key="np_exec", label_visibility="collapsed")
            st.markdown("</div>", unsafe_allow_html=True)

            # Section 3 — Project Info
            st.markdown("""<div style="background:#1e293b;border-radius:10px;padding:4px 14px 2px;margin-bottom:4px">
              <div style="display:flex;align-items:center;gap:8px;padding:10px 0 8px">
                <div style="background:#dc2626;color:#fff;border-radius:50%;width:22px;height:22px;
                  display:flex;align-items:center;justify-content:center;font-size:0.7rem;font-weight:700;flex-shrink:0">3</div>
                <span style="font-weight:700">Project Information</span>
              </div></div>""", unsafe_allow_html=True)

            pi1, pi2 = st.columns(2)
            with pi1: np_size  = st.number_input("System Size (kWp) *", min_value=0.0, step=0.5, key="np_size")
            with pi2: np_conn  = st.selectbox("Connection Type *", ["On-Grid","Off-Grid","Hybrid"], key="np_conn")

            np_status = st.selectbox("Project Status", ["planning","approved","in_progress","completed","on_hold"], key="np_status")

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
            if role == "admin":
                np_cost    = st.number_input("TOTAL PROJECT COST (₹)",  min_value=0.0, step=1000.0, key="np_cost")
                np_advance = st.number_input("ADVANCE AMOUNT (₹)",      min_value=0.0, step=1000.0, key="np_advance")
                np_subsidy = st.number_input("SUBSIDY AMOUNT (₹)",      min_value=0.0, step=1000.0, key="np_subsidy")

                if _pm == "LOAN":
                    np_bankloan = st.number_input("BANK LOAN AMOUNT (₹)",      min_value=0.0, step=1000.0, key="np_bankloan")
                    np_bankquot = st.number_input("BANK QUOTATION AMOUNT (₹)", min_value=0.0, step=1000.0, key="np_bankquot")
                else:
                    np_bankloan = np_bankquot = 0.0
            else:
                np_cost = np_advance = np_subsidy = np_bankloan = np_bankquot = 0.0

            np_notes = st.text_area("Notes", placeholder="Any additional notes…", key="np_notes", height=60)

            # ── LOAN: Bank-side installments ─────────────────────
            if _pm == "LOAN":
                st.markdown("""
                <div style="background:#1e293b;border-radius:10px;padding:12px 14px;margin-top:8px">
                  <div style="display:flex;align-items:center;gap:8px;margin-bottom:2px">
                    <span style="font-size:1rem">🏦</span>
                    <span style="font-weight:700;font-size:0.85rem;text-transform:uppercase">Add Installment from Bank Side</span>
                  </div>
                  <div style="color:#64748b;font-size:0.72rem">(MOSTLY 2 — 70% &amp; 30%)</div>
                </div>""", unsafe_allow_html=True)

                if "bank_insts" not in st.session_state:
                    st.session_state.bank_insts = []

                if st.session_state.bank_insts:
                    _bh = '<div style="background:#0f172a;border-radius:8px;padding:8px 12px;margin-top:4px">'
                    for bi in st.session_state.bank_insts:
                        _bh += f'<div style="display:flex;justify-content:space-between;font-size:0.8rem;padding:5px 0;border-bottom:1px solid #1e293b"><span style="color:#94a3b8">#{bi["no"]}</span><span style="font-weight:600">{format_currency(bi["amount"])}</span><span style="color:#64748b">{bi["due_date"]}</span></div>'
                    _bh += '</div>'
                    st.markdown(_bh, unsafe_allow_html=True)
                    for i, bi in enumerate(st.session_state.bank_insts):
                        if st.button(f"🗑️ Remove Bank Inst #{bi['no']}", key=f"del_bi_{i}"):
                            st.session_state.bank_insts.pop(i); st.rerun()

                with st.form("bank_inst_form", clear_on_submit=True):
                    st.markdown("<div style='color:#64748b;font-size:0.75rem;margin-bottom:4px'>+ Add Installment — Amount & Date</div>", unsafe_allow_html=True)
                    bic1, bic2, bic3 = st.columns(3)
                    with bic1: bi_no  = st.number_input("Inst #", min_value=1, value=len(st.session_state.bank_insts)+1, key="bi_no")
                    with bic2: bi_amt = st.number_input("Amount (₹)", min_value=0.0, step=5000.0, key="bi_amt")
                    with bic3: bi_due = st.date_input("Date", key="bi_due")
                    if st.form_submit_button("➕ Add Bank Installment", use_container_width=True):
                        st.session_state.bank_insts.append({"no": int(bi_no), "amount": bi_amt, "due_date": str(bi_due), "status": "pending"})
                        st.rerun()

            # ── CASH: Customer-side installments ─────────────────
            st.markdown("""
            <div style="background:#1e293b;border-radius:10px;padding:12px 14px;margin-top:8px">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:2px">
                <span style="font-size:1rem">🏛️</span>
                <span style="font-weight:700;font-size:0.85rem;text-transform:uppercase">Add Installments from Customer Side</span>
              </div>
              <div style="color:#64748b;font-size:0.72rem">(MOSTLY 3)</div>
            </div>""", unsafe_allow_html=True)

            if st.session_state.draft_insts:
                _ih = '<div style="background:#0f172a;border-radius:8px;padding:8px 12px;margin-top:4px">'
                for inst in st.session_state.draft_insts:
                    _clr = "#22c55e" if inst["status"] == "paid" else "#f59e0b"
                    _ih += f'<div style="display:flex;justify-content:space-between;font-size:0.8rem;padding:5px 0;border-bottom:1px solid #1e293b"><span style="color:#94a3b8">#{inst["no"]}</span><span style="font-weight:600">{format_currency(inst["amount"])}</span><span style="color:#64748b">{inst["due_date"]}</span><span style="color:{_clr}">{inst["status"].title()}</span></div>'
                _ih += '</div>'
                st.markdown(_ih, unsafe_allow_html=True)
                for i, inst in enumerate(st.session_state.draft_insts):
                    if st.button(f"🗑️ Remove #{inst['no']}", key=f"del_ci_{i}"):
                        st.session_state.draft_insts.pop(i); st.rerun()

            with st.form("cust_inst_form", clear_on_submit=True):
                st.markdown("<div style='color:#64748b;font-size:0.75rem;margin-bottom:4px'>+ Add Installment — Amount & Date</div>", unsafe_allow_html=True)
                cic1, cic2, cic3 = st.columns(3)
                with cic1: di_no  = st.number_input("Inst #", min_value=1, value=len(st.session_state.draft_insts)+1, key="di_no")
                with cic2: di_amt = st.number_input("Amount (₹)", min_value=0.0, step=5000.0, key="di_amt")
                with cic3: di_due = st.date_input("Date", key="di_due")
                di_st = st.selectbox("Status", ["pending","paid"], key="di_st")
                if st.form_submit_button("➕ Add Customer Installment", use_container_width=True):
                    st.session_state.draft_insts.append({"no": int(di_no), "amount": di_amt, "due_date": str(di_due), "status": di_st})
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
                        "system_size_kwp":      st.session_state.get("np_size", 0),
                        "connection_type":      st.session_state.get("np_conn","On-Grid"),
                        "project_status":       st.session_state.get("np_status","planning"),
                        "payment_mode":         st.session_state.get("np_pay_mode","CASH"),
                        "total_cost":           np_cost,
                        "amount_paid":          np_advance,
                        "advance_amount":       np_advance,
                        "subsidy_amount":       np_subsidy,
                        "bank_loan_amount":     np_bankloan,
                        "bank_quotation_amount":np_bankquot,
                        "balance":              np_cost - np_advance,
                        "net_payable":          np_cost - np_subsidy,
                        "notes":                st.session_state.get("np_notes",""),
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
                        st.success("✅ Project created! Open it via 📂 to manage steps & documents.")
                        st.rerun()
        with scol2:
            if st.button("🗑️  Clear", use_container_width=True, key="clear_project_btn"):
                for k in ["np_name","np_mobile","np_altmob","np_email","np_aadhar","np_elecbill",
                          "np_addr","np_village","np_taluka","np_district","np_pin","np_latlng",
                          "np_exec","np_size","np_conn","np_status","np_notes","draft_insts"]:
                    st.session_state.pop(k, None)
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  REPORT TAB — ADMIN ONLY
# ══════════════════════════════════════════════════════════════════════════════
if t3 is not None:
    with t3:
        st.markdown("#### 📊 Financial & Project Reports")
        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("💰 Total Project Value", format_currency(total_cost))
        rc2.metric("✅ Total Received",       format_currency(total_paid))
        rc3.metric("⏳ Outstanding Balance",  format_currency(balance_due))

        st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)

        if not df.empty:
            if "project_status" in df.columns:
                st.markdown("**Summary by Status**")
                grp = df.groupby("project_status").agg(
                    Count=("project_status","count"),
                    **{"Total Cost":  ("total_cost",  lambda x: x.fillna(0).sum())},
                    **{"Amount Paid": ("amount_paid", lambda x: x.fillna(0).sum())},
                    **{"Balance":     ("balance",     lambda x: x.fillna(0).sum())},
                ).reset_index()
                grp.rename(columns={"project_status":"Status"}, inplace=True)
                for col in ("Total Cost","Amount Paid","Balance"):
                    grp[col] = grp[col].apply(lambda x: format_currency(float(x)))
                st.dataframe(grp, use_container_width=True, hide_index=True)

            st.markdown("<hr style='margin:12px 0'>", unsafe_allow_html=True)
            fin_cols = [c for c in ["customer_name","location","system_size_kwp","project_status","total_cost","amount_paid","balance"] if c in df.columns]
            fin_df   = df[fin_cols].copy()
            ren      = {"customer_name":"Customer","location":"Location","system_size_kwp":"kWp",
                        "project_status":"Status","total_cost":"Total Cost","amount_paid":"Paid","balance":"Balance"}
            fin_df.rename(columns=ren, inplace=True)
            for col in ("Total Cost","Paid","Balance"):
                if col in fin_df.columns:
                    fin_df[col] = fin_df[col].apply(lambda x: format_currency(float(x)) if pd.notna(x) else "₹0")
            st.dataframe(fin_df, use_container_width=True, hide_index=True)

            raw = df[fin_cols].copy(); raw.rename(columns=ren, inplace=True)
            st.download_button("⬇️ Export CSV", raw.to_csv(index=False).encode("utf-8"),
                               "voltedge_report.csv", "text/csv", use_container_width=True)

            if all(c in df.columns for c in ("customer_name","total_cost","amount_paid")):
                st.markdown("**Payment Collection Analysis**")
                top = df.nlargest(min(10, len(df)), "total_cost")
                fig_pay = go.Figure()
                fig_pay.add_trace(go.Bar(name="Total Cost",  x=top["customer_name"], y=top["total_cost"].fillna(0),  marker_color="#3b82f6"))
                fig_pay.add_trace(go.Bar(name="Amount Paid", x=top["customer_name"], y=top["amount_paid"].fillna(0), marker_color="#22c55e"))
                fig_pay.add_trace(go.Bar(name="Balance",     x=top["customer_name"], y=top["balance"].fillna(0),     marker_color="#ef4444"))
                fig_pay.update_layout(barmode="group", height=350,
                                      margin=dict(t=10,b=60,l=10,r=10),
                                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                      font_color="#f1f5f9",
                                      xaxis=dict(gridcolor="#334155", tickangle=-30),
                                      yaxis=dict(gridcolor="#334155"),
                                      legend=dict(bgcolor="rgba(0,0,0,0)"))
                st.plotly_chart(fig_pay, use_container_width=True)
        else:
            st.info("No data available.")


# ══════════════════════════════════════════════════════════════════════════════
#  USERS TAB — ADMIN ONLY
# ══════════════════════════════════════════════════════════════════════════════
if t4 is not None:
    with t4:
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
                        st.success(f"✅ {u.get('name','')} approved!")
                        st.rerun()
                with pc5:
                    if st.button("❌ Reject", key=f"reject_{u['id']}", use_container_width=True):
                        supabase.table("app_users").update({"status": "rejected"}).eq("id", u["id"]).execute()
                        st.warning(f"❌ {u.get('name','')} rejected.")
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
                    st.rerun()
            with uc5:
                if u.get("email") != "voltedgeenergysolutions011@gmail.com":
                    if st.button("🚫 Revoke", key=f"revoke_{u['id']}", use_container_width=True):
                        supabase.table("app_users").update({"status": "rejected"}).eq("id", u["id"]).execute()
                        st.rerun()

        if rejected_users:
            with st.expander(f"Rejected Users ({len(rejected_users)})"):
                for u in rejected_users:
                    rc1, rc2, rc3, rc4 = st.columns([2, 2.5, 1.2, 1.2])
                    rc1.write(u.get("name",""))
                    rc2.write(u.get("email",""))
                    rc3.write("Rejected")
                    if rc4.button("🔁 Re-approve", key=f"reapprove_{u['id']}"):
                        supabase.table("app_users").update({"status":"approved","role":"employee"}).eq("id",u["id"]).execute()
                        st.rerun()

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
            log_limit = st.selectbox("Show", [25, 50, 100], key="log_limit")

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
#  SETTINGS TAB
# ══════════════════════════════════════════════════════════════════════════════
with t5:
    st.markdown("#### ⚙️ Settings & Profile")
    sc1, sc2 = st.columns(2)
    with sc1:
        st.markdown("**👤 Your Profile**")
        pic = st.session_state.get("user_picture","")
        if pic:
            st.image(pic, width=72)
        st.write(f"**Name:** {st.session_state.get('user_name','N/A')}")
        st.write(f"**Email:** {st.session_state.get('user_email','N/A')}")
        st.write(f"**Role:** {role.title()}")
        st.write(f"**Status:** {status.title()}")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Sign Out", use_container_width=True, key="settings_logout"):
            logout()
    with sc2:
        st.markdown("**📱 App Info**")
        st.info("**VOLTEDGE Energy Solutions**\nSolar Project Dashboard v2.0\n\n- Framework: Streamlit\n- Database: Supabase\n- Auth: Google OAuth 2.0")
        qs1, qs2 = st.columns(2)
        qs1.metric("Total Projects", total)
        qs2.metric("Completion",     f"{comp_pct}%")
