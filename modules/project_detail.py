"""Project Detail View — full per-project dashboard (card layout)"""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timezone
from .utils import format_currency
from .supabase_client import log_activity

DEFAULT_STEPS = [
    (1,  "Survey & Engineering"),
    (2,  "Document Collection"),
    (3,  "National Portal Application"),
    (4,  "Loan Approval"),
    (5,  "MSEDCL Approval (Net Metering)"),
    (6,  "Structure Fabrication"),
    (7,  "Installation & Commissioning"),
    (8,  "Net Meter Installation"),
    (9,  "Subsidy Process"),
    (10, "Project Handover"),
]

STEP_ICONS = ["📐", "📋", "🖥️", "🏦", "🏛️", "🔧", "⚙️", "🔌", "🎁", "📦"]

DEFAULT_DOCS = [
    "WCR", "ANNEXURE I", "DCR CERTIFICATE",
    "NET METER AGREEMENT", "DATA SHEET", "SITE PHOTOS",
]


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_or_create_docs(supabase, project_id):
    rows = supabase.table("project_documents").select("*").eq("project_id", project_id).execute().data
    if not rows:
        supabase.table("project_documents").insert([
            {"project_id": project_id, "doc_name": d, "status": "pending"}
            for d in DEFAULT_DOCS
        ]).execute()
        rows = supabase.table("project_documents").select("*").eq("project_id", project_id).execute().data
    return rows or []

def _get_or_create_steps(supabase, project_id):
    rows = supabase.table("project_steps").select("*").eq("project_id", project_id).order("step_no").execute().data
    if not rows:
        supabase.table("project_steps").insert([
            {"project_id": project_id, "step_no": n, "step_name": name,
             "status": "pending", "progress_percent": 0}
            for n, name in DEFAULT_STEPS
        ]).execute()
        rows = supabase.table("project_steps").select("*").eq("project_id", project_id).order("step_no").execute().data
    else:
        # Normalize step names to the current milestone set (keeps status/dates intact)
        name_by_no = {n: name for n, name in DEFAULT_STEPS}
        changed = False
        for r in rows:
            want = name_by_no.get(r.get("step_no"))
            if want and r.get("step_name") != want:
                supabase.table("project_steps").update({"step_name": want}).eq("id", r["id"]).execute()
                r["step_name"] = want
                changed = True
        if changed:
            rows = supabase.table("project_steps").select("*").eq("project_id", project_id).order("step_no").execute().data
    return rows or []


def _get_installments(supabase, project_id):
    return supabase.table("installments").select("*").eq("project_id", project_id).order("installment_no").execute().data or []


def _get_notes(supabase, project_id):
    return supabase.table("project_notes").select("*").eq("project_id", project_id).order("created_at", desc=True).execute().data or []


def _get_project_logs(supabase, project_id, limit=6):
    try:
        return supabase.table("activity_logs").select("*").eq("project_id", project_id)\
            .order("created_at", desc=True).limit(limit).execute().data or []
    except Exception:
        return []


def _fmt_date(val):
    if not val:
        return "-"
    s = str(val)
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d.strftime("%b %d, %Y")
    except Exception:
        return s[:10]


def _fmt_datetime(val):
    if not val:
        return "-"
    try:
        d = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        return d.strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return str(val)[:16]


CARD = "background:#0f1b2e;border:1px solid #1e293b;border-radius:12px;padding:16px 18px"


def _section_title(icon, text, accent="#3b82f6"):
    return (f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:12px'>"
            f"<span style='font-size:1rem'>{icon}</span>"
            f"<span style='font-weight:700;font-size:0.92rem;color:#e2e8f0;letter-spacing:0.5px'>{text}</span></div>")


def _kv(label, value, vcolor="#f1f5f9"):
    return (f"<div style='margin-bottom:12px'>"
            f"<div style='color:#64748b;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.5px'>{label}</div>"
            f"<div style='color:{vcolor};font-size:0.9rem;font-weight:600;margin-top:2px'>{value}</div></div>")


def _status_pill(status):
    s = (status or "").lower()
    if s == "completed":
        return '<span style="background:#16a34a22;color:#22c55e;border:1px solid #16a34a;padding:3px 12px;border-radius:6px;font-size:0.72rem;font-weight:700">Completed</span>'
    if s in ("cancelled", "rejected"):
        return '<span style="background:#dc262622;color:#ef4444;border:1px solid #dc2626;padding:3px 12px;border-radius:6px;font-size:0.72rem;font-weight:700">Cancelled</span>'
    return '<span style="background:#2563eb22;color:#3b82f6;border:1px solid #2563eb;padding:3px 12px;border-radius:6px;font-size:0.72rem;font-weight:700">In Progress</span>'


# ── main renderer ─────────────────────────────────────────────────────────────

def render_project_detail(supabase, project, role="admin"):
    """Render the full project detail dashboard for one project."""

    pid          = project["id"]
    steps        = _get_or_create_steps(supabase, pid)
    installments = _get_installments(supabase, pid)
    docs         = _get_or_create_docs(supabase, pid)
    notes        = _get_notes(supabase, pid)
    logs         = _get_project_logs(supabase, pid)

    done_steps   = sum(1 for s in steps if s.get("status") == "completed")
    progress     = int(done_steps / len(steps) * 100) if steps else 0
    project_code = project.get("project_code") or f"EPC-{str(pid)[:8].upper()}"

    # current stage = first in-progress, else first pending, else last
    cur_stage = next((s for s in steps if s.get("status") == "in_progress"), None) \
        or next((s for s in steps if s.get("status") == "pending"), None) \
        or (steps[-1] if steps else None)

    is_admin = (role == "admin")

    # ── top bar ──────────────────────────────────────────────────
    tb1, tb2 = st.columns([3, 1])
    with tb1:
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:10px'>"
            f"<span style='color:#64748b;font-size:0.85rem'>Edit Customers</span>"
            f"<span style='color:#475569'>›</span>"
            f"<span style='font-weight:800;font-size:1.15rem;color:#3b82f6'>📂 PROJECT DETAILS</span></div>",
            unsafe_allow_html=True)
    with tb2:
        if st.button("← Back", key="back_to_dash", use_container_width=True):
            st.session_state.selected_project_id = None
            st.rerun()
    st.markdown(
        f"<div style='color:#64748b;font-size:0.72rem;margin:2px 0 12px'>Last updated: {_fmt_datetime(project.get('updated_at') or project.get('created_at'))}</div>",
        unsafe_allow_html=True)

    # ── PROJECT SUMMARY ──────────────────────────────────────────
    st.markdown(f"<div style='{CARD}'>", unsafe_allow_html=True)
    st.markdown(_section_title("📑", "PROJECT SUMMARY"), unsafe_allow_html=True)
    s1, s2, s3, s4 = st.columns([1.3, 1.3, 1, 1])
    with s1:
        st.markdown(_kv("Project ID", project_code, "#f97316"), unsafe_allow_html=True)
        st.markdown(_kv("Last Updated On", _fmt_datetime(project.get("updated_at") or project.get("created_at"))), unsafe_allow_html=True)
    with s2:
        st.markdown(_kv("Customer Name", project.get("customer_name", "-") or "-"), unsafe_allow_html=True)
        cur_name = cur_stage.get("step_name", "-") if cur_stage else "-"
        cur_no   = cur_stage.get("step_no", "-") if cur_stage else "-"
        st.markdown(_kv("Current Stage", f"#{cur_no} · {cur_name}"), unsafe_allow_html=True)
    with s3:
        fig_p = go.Figure(go.Pie(
            values=[max(progress, 1), 100 - max(progress, 1)], hole=0.7,
            marker_colors=["#22c55e", "#1e293b"], showlegend=False,
            textinfo="none", direction="clockwise", sort=False,
        ))
        fig_p.add_annotation(text=f"<b>{progress}%</b><br><span style='font-size:9px'>Complete</span>",
                             x=0.5, y=0.5, showarrow=False, font=dict(size=16, color="#f1f5f9"))
        fig_p.update_layout(height=120, margin=dict(t=2, b=2, l=2, r=2), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_p, use_container_width=True, key="summary_donut")
    with s4:
        st.markdown(_kv("Project Status", _status_pill(project.get("project_status"))), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:14px'></div>", unsafe_allow_html=True)

    # ── CUSTOMER INFO | PROJECT INFO ─────────────────────────────
    ci, pi = st.columns(2)
    with ci:
        st.markdown(f"<div style='{CARD}'>", unsafe_allow_html=True)
        st.markdown(_section_title("👤", "CUSTOMER INFORMATION"), unsafe_allow_html=True)
        r1, r2, r3 = st.columns(3)
        r1.markdown(_kv("Customer Name 🔒", project.get("customer_name", "-") or "-"), unsafe_allow_html=True)
        r2.markdown(_kv("Mobile Number", project.get("mobile", "-") or "-"), unsafe_allow_html=True)
        r3.markdown(_kv("Email", project.get("email", "-") or "-"), unsafe_allow_html=True)
        r4, r5, r6 = st.columns(3)
        r4.markdown(_kv("Alternate Mobile", project.get("alt_mobile", "-") or "-"), unsafe_allow_html=True)
        r5.markdown(_kv("Aadhar Number", project.get("aadhar_number", "-") or "-"), unsafe_allow_html=True)
        r6.markdown(_kv("PAN Number", project.get("pan_number", "-") or "-"), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        with st.expander("✏️ Edit Customer Information"):
            with st.form("edit_cust_form"):
                e_name = st.text_input("Customer Name", value=project.get("customer_name", "") or "")
                e_mob  = st.text_input("Mobile Number",  value=project.get("mobile", "") or "")
                e_alt  = st.text_input("Alternate Mobile", value=project.get("alt_mobile", "") or "")
                e_mail = st.text_input("Email", value=project.get("email", "") or "")
                e_aad  = st.text_input("Aadhar Number", value=project.get("aadhar_number", "") or "")
                e_pan  = st.text_input("PAN Number", value=project.get("pan_number", "") or "")
                e_bill = st.text_input("Electricity Bill ID", value=project.get("electricity_bill_id", "") or "")
                if st.form_submit_button("💾 Save"):
                    supabase.table("projects").update({
                        "customer_name": e_name, "mobile": e_mob, "alt_mobile": e_alt,
                        "email": e_mail, "aadhar_number": e_aad, "pan_number": e_pan,
                        "electricity_bill_id": e_bill,
                    }).eq("id", pid).execute()
                    log_activity(supabase, "Edited customer info", entity_type="project",
                                 project_id=pid, project_name=e_name)
                    st.success("✅ Saved!"); st.rerun()

    with pi:
        st.markdown(f"<div style='{CARD}'>", unsafe_allow_html=True)
        st.markdown(_section_title("📋", "PROJECT INFORMATION"), unsafe_allow_html=True)
        p1, p2, p3 = st.columns(3)
        p1.markdown(_kv("System Size (kWp)", f"{project.get('system_size_kwp', 0) or 0} kWp"), unsafe_allow_html=True)
        p2.markdown(_kv("Connection Type", project.get("connection_type", "-") or "-"), unsafe_allow_html=True)
        p3.markdown(_kv("Execution Partner", project.get("execution_partner", "-") or "-"), unsafe_allow_html=True)
        p4, p5, p6 = st.columns(3)
        p4.markdown(_kv("Discom", project.get("discom", "MSEDCL") or "MSEDCL"), unsafe_allow_html=True)
        p5.markdown(_kv("Project Created On 🔒", _fmt_date(project.get("created_at"))), unsafe_allow_html=True)
        p6.markdown(_kv("Project Status", _status_pill(project.get("project_status"))), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        with st.expander("✏️ Edit Project Information"):
            with st.form("edit_proj_form"):
                pe1, pe2 = st.columns(2)
                with pe1:
                    e_size = st.number_input("System Size (kWp)", min_value=0.0, step=0.5,
                                             value=float(project.get("system_size_kwp", 0) or 0))
                    e_conn = st.selectbox("Connection Type", ["On-Grid", "Off-Grid", "Hybrid"],
                                          index=["On-Grid", "Off-Grid", "Hybrid"].index(project.get("connection_type") or "On-Grid")
                                          if (project.get("connection_type") in ["On-Grid", "Off-Grid", "Hybrid"]) else 0)
                with pe2:
                    e_exec  = st.text_input("Execution Partner", value=project.get("execution_partner", "") or "")
                    e_disc  = st.text_input("Discom", value=project.get("discom", "MSEDCL") or "MSEDCL")
                eb1, eb2 = st.columns(2)
                with eb1:
                    e_bank  = st.text_input("Bank Name", value=project.get("bank_name", "") or "")
                with eb2:
                    e_lstat = st.selectbox("Loan Status", ["—", "Applied", "Approved", "Disbursed", "Rejected"],
                                           index=(["—", "Applied", "Approved", "Disbursed", "Rejected"].index(project.get("loan_status"))
                                                  if project.get("loan_status") in ["—", "Applied", "Approved", "Disbursed", "Rejected"] else 0))
                e_pstat = st.selectbox("Project Status", ["Active", "Completed", "Cancelled"],
                                       index={"completed": 1, "cancelled": 2}.get((project.get("project_status") or "").lower(), 0))
                if st.form_submit_button("💾 Save"):
                    _map = {"Active": "in_progress", "Completed": "completed", "Cancelled": "cancelled"}
                    supabase.table("projects").update({
                        "system_size_kwp": e_size, "connection_type": e_conn,
                        "execution_partner": e_exec, "discom": e_disc,
                        "bank_name": e_bank, "loan_status": e_lstat,
                        "project_status": _map[e_pstat],
                    }).eq("id", pid).execute()
                    log_activity(supabase, "Edited project info", entity_type="project",
                                 project_id=pid, project_name=project.get("customer_name"))
                    st.success("✅ Saved!"); st.rerun()

    st.markdown("<div style='margin-top:14px'></div>", unsafe_allow_html=True)

    # ── PROJECT WORKFLOW & MILESTONES ────────────────────────────
    st.markdown(f"<div style='{CARD}'>", unsafe_allow_html=True)
    st.markdown(_section_title("🛠️", "PROJECT WORKFLOW & MILESTONES"), unsafe_allow_html=True)
    cols = st.columns(len(steps[:10]))
    for i, step in enumerate(steps[:10]):
        sstatus = step.get("status", "pending")
        if sstatus == "completed":
            ring, badge, lbl = "#22c55e", "#16a34a", '<span style="color:#22c55e;font-size:0.6rem;font-weight:700">✓ Completed</span>'
        elif sstatus == "in_progress":
            ring, badge, lbl = "#3b82f6", "#2563eb", '<span style="color:#3b82f6;font-size:0.6rem;font-weight:700">● In Progress</span>'
        else:
            ring, badge, lbl = "#475569", "#1e293b", '<span style="color:#ef4444;font-size:0.6rem;font-weight:700">Pending</span>'
        date_txt  = _fmt_date(step.get("end_date") or step.get("start_date"))
        card_bdr  = ring if sstatus != "pending" else "#1e293b"
        with cols[i]:
            st.markdown(f"""
            <div style="text-align:center;border:1px solid {card_bdr};border-radius:10px;
                        padding:10px 4px 8px;background:#0b1626;min-height:118px;position:relative">
              <div style="background:{badge};border:2px solid {ring};border-radius:50%;
                          width:24px;height:24px;line-height:20px;font-size:0.66rem;font-weight:700;color:#fff;
                          margin:0 auto 6px">{step.get('step_no', i+1)}</div>
              <div style="font-size:0.95rem;margin-bottom:2px">{STEP_ICONS[i] if i < len(STEP_ICONS) else '•'}</div>
              <div style="font-size:0.58rem;font-weight:700;color:#cbd5e1;line-height:1.15;min-height:26px">{step.get('step_name','')}</div>
              <div style="font-size:0.54rem;color:#64748b;margin:2px 0">{date_txt}</div>
              {lbl}
            </div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("📈 Update Progress / Step Status"):
        opts   = [f"{s['step_no']}. {s['step_name']}" for s in steps]
        chosen = st.selectbox("Step", opts, key="upd_step_sel")
        idx    = int(chosen.split(".")[0]) - 1
        sel    = steps[idx]
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            new_st = st.selectbox("Status", ["pending", "in_progress", "completed"],
                                  index=["pending", "in_progress", "completed"].index(sel.get("status", "pending")),
                                  key="upd_status")
        with sc2:
            new_sd = st.date_input("Start Date", value=None, key="upd_sd")
        with sc3:
            new_ed = st.date_input("End Date", value=None, key="upd_ed")
        if st.button("💾 Update Step", key="upd_step_btn"):
            payload = {"status": new_st, "progress_percent": 100 if new_st == "completed" else (50 if new_st == "in_progress" else 0)}
            if new_sd: payload["start_date"] = str(new_sd)
            if new_ed: payload["end_date"]   = str(new_ed)
            supabase.table("project_steps").update(payload).eq("id", sel["id"]).execute()
            log_activity(supabase, f"Workflow updated to {sel['step_name']} ({new_st})", entity_type="step",
                         project_id=pid, project_name=project.get("customer_name"))
            st.success("✅ Step updated!"); st.rerun()

    # ── BOTTOM 3-COLUMN GRID: Financials | Documents | Timeline+Notes ──
    st.markdown("<div style='margin-top:14px'></div>", unsafe_allow_html=True)
    fin_col, doc_col, time_col = st.columns([2.1, 1.1, 1.2])

    with fin_col:
        _render_financials(supabase, project, installments)

    with doc_col:
        _render_documents(supabase, project, docs)

    with time_col:
        _render_timeline_notes(supabase, project, logs, notes)

    # ── SAVE CHANGES ─────────────────────────────────────────────
    st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
    sv1, sv2 = st.columns([4, 1])
    with sv2:
        if st.button("💾 SAVE CHANGES", type="primary", use_container_width=True, key="detail_save"):
            st.toast("✅ All edits are saved per section as you make them.")


def _render_documents(supabase, project, docs):
    pid = project["id"]
    st.markdown(f"<div style='{CARD}'>", unsafe_allow_html=True)
    st.markdown(_section_title("📄", "DOCUMENTS CHECKLIST", "#8b5cf6"), unsafe_allow_html=True)
    html = ""
    for i, doc in enumerate(docs, start=1):
        uploaded = doc.get("status") == "uploaded"
        clr  = "#22c55e" if uploaded else "#ef4444"
        bg   = "#16a34a22" if uploaded else "#dc262622"
        lbl  = "Uploaded" if uploaded else "Pending"
        html += (f'<div style="display:flex;justify-content:space-between;align-items:center;'
                 f'padding:7px 0;border-bottom:1px solid #1e293b">'
                 f'<span style="color:#cbd5e1;font-size:0.78rem">{i}. {doc.get("doc_name","")}</span>'
                 f'<span style="background:{bg};color:{clr};padding:2px 9px;border-radius:5px;'
                 f'font-size:0.66rem;font-weight:700">{lbl}</span></div>')
    st.markdown(html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    with st.expander("📤 Update Documents"):
        for doc in docs:
            dc1, dc2 = st.columns([2, 1])
            with dc1:
                st.markdown(f"<span style='font-size:0.82rem'>{doc.get('doc_name','')}</span>", unsafe_allow_html=True)
            with dc2:
                cur = doc.get("status", "pending")
                new_s = st.selectbox("", ["pending", "uploaded"],
                                     index=0 if cur == "pending" else 1,
                                     key=f"doc_{doc['id']}", label_visibility="collapsed")
            if new_s != cur:
                supabase.table("project_documents").update({"status": new_s}).eq("id", doc["id"]).execute()
                log_activity(supabase, f"Document '{doc.get('doc_name','')}' → {new_s}", entity_type="document",
                             project_id=pid, project_name=project.get("customer_name"))
                st.rerun()


def _render_timeline_notes(supabase, project, logs, notes):
    pid = project["id"]
    # PROJECT TIMELINE
    st.markdown(f"<div style='{CARD}'>", unsafe_allow_html=True)
    st.markdown(_section_title("🕐", "PROJECT TIMELINE"), unsafe_allow_html=True)
    if logs:
        html = ""
        for lg in logs:
            html += f"""
            <div style="border-left:2px solid #2563eb;padding:0 0 12px 14px;position:relative">
              <div style="position:absolute;left:-5px;top:2px;width:8px;height:8px;border-radius:50%;background:#3b82f6"></div>
              <div style="font-size:0.68rem;color:#94a3b8">{_fmt_datetime(lg.get('created_at'))}</div>
              <div style="font-size:0.78rem;color:#e2e8f0">{lg.get('action','')}</div>
              <div style="font-size:0.66rem;color:#64748b">{lg.get('user_name','') or ''}</div>
            </div>"""
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.markdown("<div style='color:#475569;font-size:0.82rem'>No activity recorded yet.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # INTERNAL NOTES
    st.markdown("<div style='margin-top:14px'></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='{CARD}'>", unsafe_allow_html=True)
    st.markdown(_section_title("📝", "INTERNAL NOTES", "#f59e0b"), unsafe_allow_html=True)
    if notes:
        latest = notes[0]
        st.markdown(f"<div style='font-size:0.82rem;color:#cbd5e1;line-height:1.6'>{latest.get('note','')}</div>", unsafe_allow_html=True)
        if latest.get("next_action"):
            st.markdown(f"<div style='margin-top:8px;border-left:3px solid #f59e0b;padding-left:10px;font-size:0.78rem;color:#f59e0b'>Next: {latest.get('next_action')}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='color:#475569;font-size:0.66rem;margin-top:8px'>Last note added: {_fmt_datetime(latest.get('created_at'))}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='color:#475569;font-size:0.82rem'>No notes yet.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    with st.expander("➕ Add / Edit Note"):
        with st.form("add_note_form"):
            note_txt   = st.text_area("Note", key="note_txt")
            action_txt = st.text_input("Next Action", key="action_txt")
            if st.form_submit_button("💾 Save Note"):
                if note_txt.strip():
                    supabase.table("project_notes").insert({
                        "project_id": pid, "note": note_txt.strip(), "next_action": action_txt.strip(),
                    }).execute()
                    log_activity(supabase, "Added note", entity_type="note",
                                 project_id=pid, project_name=project.get("customer_name"),
                                 details=note_txt.strip()[:150])
                    st.success("✅ Note saved!"); st.rerun()


def _render_financials(supabase, project, installments):
    pid       = project["id"]
    total     = float(project.get("total_cost", 0) or 0)
    received  = float(project.get("amount_paid", 0) or 0)
    pending   = float(project.get("balance", total - received) or 0)
    pay_mode  = (project.get("payment_mode") or "Cash").title()
    rec_pct   = round(received / total * 100, 1) if total else 0
    pen_pct   = round(pending  / total * 100, 1) if total else 0

    # FINANCIAL PROGRESS metrics
    st.markdown(f"<div style='{CARD}'>", unsafe_allow_html=True)
    st.markdown(_section_title("💰", "FINANCIAL PROGRESS", "#22c55e"), unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns(4)
    f1.markdown(_kv("Project Value", format_currency(total), "#3b82f6"), unsafe_allow_html=True)
    f2.markdown(_kv("Received", f"{format_currency(received)}<br><span style='color:#22c55e;font-size:0.7rem'>{rec_pct}%</span>", "#22c55e"), unsafe_allow_html=True)
    f3.markdown(_kv("Pending", f"{format_currency(pending)}<br><span style='color:#ef4444;font-size:0.7rem'>{pen_pct}%</span>", "#ef4444"), unsafe_allow_html=True)
    _lstat = project.get("loan_status") or ("Approved" if float(project.get("bank_loan_amount", 0) or 0) > 0 else "—")
    f4.markdown(_kv("Payment Mode",
                    f"{pay_mode}<br>"
                    f"<span style='color:#22c55e;font-size:0.68rem'>Loan: {_lstat}</span><br>"
                    f"<span style='color:#64748b;font-size:0.68rem'>Bank: {project.get('bank_name','-') or '-'}</span>"),
                unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:14px'></div>", unsafe_allow_html=True)

    ps, su = st.columns([1.6, 1])
    # PAYMENT SUMMARY table
    with ps:
        st.markdown(f"<div style='{CARD}'>", unsafe_allow_html=True)
        st.markdown(_section_title("📊", "PAYMENT SUMMARY"), unsafe_allow_html=True)

        rows = []
        adv = float(project.get("advance_amount", 0) or 0)
        if adv > 0:
            rows.append(("Advance Payment", adv, _fmt_date(project.get("created_at")), "paid"))
        sub = float(project.get("subsidy_amount", 0) or 0)
        if sub > 0:
            sub_paid = (project.get("subsidy_status") or "").lower() == "disbursed"
            rows.append(("Subsidy Amount", sub, "-", "paid" if sub_paid else "pending"))
        loan = float(project.get("bank_loan_amount", 0) or 0)
        if loan > 0:
            rows.append(("Loan Disbursement (Bank)", loan, "-", "pending"))
        for inst in installments:
            rows.append((f"Installment {inst.get('installment_no','')}",
                         float(inst.get("amount", 0) or 0),
                         _fmt_date(inst.get("due_date")),
                         inst.get("status", "pending")))

        html = ('<div style="display:flex;font-size:0.66rem;color:#64748b;font-weight:700;'
                'padding:4px 0;border-bottom:1px solid #1e293b;text-transform:uppercase">'
                '<span style="flex:0.4">#</span><span style="flex:2">Particulars</span>'
                '<span style="flex:1.2;text-align:right">Amount</span>'
                '<span style="flex:1.2;text-align:center">Paid On</span>'
                '<span style="flex:1;text-align:right">Status</span></div>')
        tot_amt = tot_paid = 0.0
        for i, (lbl, amt, paid_on, stt) in enumerate(rows, start=1):
            tot_amt += amt
            paid = (stt or "").lower() == "paid"
            if paid:
                tot_paid += amt
            sclr = "#22c55e" if paid else "#ef4444"
            html += (f'<div style="display:flex;font-size:0.76rem;padding:7px 0;border-bottom:1px solid #1e293b;align-items:center">'
                     f'<span style="flex:0.4;color:#64748b">{i}</span>'
                     f'<span style="flex:2;color:#cbd5e1">{lbl}</span>'
                     f'<span style="flex:1.2;text-align:right;color:#f1f5f9;font-weight:600">{format_currency(amt)}</span>'
                     f'<span style="flex:1.2;text-align:center;color:#64748b;font-size:0.72rem">{paid_on}</span>'
                     f'<span style="flex:1;text-align:right;color:{sclr};font-weight:700;font-size:0.72rem">{"Paid" if paid else "Pending"}</span></div>')
        if not rows:
            html += '<div style="color:#475569;font-size:0.8rem;padding:10px 0">No payment records yet.</div>'
        pct = round(tot_paid / tot_amt * 100, 1) if tot_amt else 0
        html += (f'<div style="display:flex;font-size:0.8rem;padding:8px 0 0;font-weight:800;color:#f1f5f9">'
                 f'<span style="flex:0.4"></span><span style="flex:2">TOTAL</span>'
                 f'<span style="flex:1.2;text-align:right">{format_currency(tot_amt)}</span>'
                 f'<span style="flex:1.2;text-align:center;color:#22c55e">{format_currency(tot_paid)}</span>'
                 f'<span style="flex:1;text-align:right;color:#f59e0b">{pct}%</span></div>')
        st.markdown(html, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        with st.expander("➕ Add Payment / Installment"):
            with st.form("add_inst_form_detail"):
                ai1, ai2 = st.columns(2)
                with ai1:
                    iamt = st.number_input("Amount (₹)", min_value=0.0, step=5000.0, value=None, placeholder="0", key="iamt") or 0.0
                    idue = st.date_input("Date", key="idue")
                with ai2:
                    ist  = st.selectbox("Status", ["pending", "paid"], key="ist")
                if st.form_submit_button("💾 Add"):
                    if iamt > 0:
                        existing = supabase.table("installments").select("installment_no").eq("project_id", pid).execute().data or []
                        nxt = max([e.get("installment_no", 0) for e in existing], default=0) + 1
                        supabase.table("installments").insert({
                            "project_id": pid, "installment_no": nxt,
                            "amount": iamt, "due_date": str(idue), "status": ist,
                        }).execute()
                        log_activity(supabase, f"Added payment #{nxt}", entity_type="installment",
                                     project_id=pid, project_name=project.get("customer_name"),
                                     details=f"₹{iamt:,.0f} · {ist}")
                        st.success("✅ Added!"); st.rerun()

    # SUBSIDY INFORMATION
    with su:
        st.markdown(f"<div style='{CARD}'>", unsafe_allow_html=True)
        st.markdown(_section_title("🏛️", "SUBSIDY INFORMATION", "#f59e0b"), unsafe_allow_html=True)
        sub_amt    = float(project.get("subsidy_amount", 0) or 0)
        sub_status = (project.get("subsidy_status") or "pending").lower()
        applied    = "✅ Yes" if sub_amt > 0 else "❌ No"
        received_s = "✅ Yes" if sub_status == "disbursed" else "❌ No"
        st.markdown(_kv("Amount Expected", format_currency(sub_amt), "#f59e0b"), unsafe_allow_html=True)
        st.markdown(_kv("Applied", applied), unsafe_allow_html=True)
        st.markdown(_kv("Received", received_s), unsafe_allow_html=True)
        st.markdown(_kv("Loan Status", "Approved" if float(project.get('bank_loan_amount',0) or 0) > 0 else "—"), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        with st.expander("✏️ Update Subsidy"):
            with st.form("edit_subsidy_form"):
                s_amt = st.number_input("Subsidy Amount (₹)", min_value=0.0, step=1000.0,
                                        value=float(project.get("subsidy_amount", 0) or 0))
                s_stt = st.selectbox("Subsidy Status", ["pending", "disbursed"],
                                     index=0 if sub_status != "disbursed" else 1)
                if st.form_submit_button("💾 Save"):
                    supabase.table("projects").update({
                        "subsidy_amount": s_amt, "subsidy_status": s_stt,
                    }).eq("id", pid).execute()
                    log_activity(supabase, f"Subsidy updated → {s_stt}", entity_type="project",
                                 project_id=pid, project_name=project.get("customer_name"))
                    st.success("✅ Saved!"); st.rerun()
