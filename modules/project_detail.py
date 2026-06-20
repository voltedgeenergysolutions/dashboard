"""Project Detail View — full per-project dashboard (card layout)"""

import streamlit as st
from datetime import datetime
from .utils import format_currency
from .supabase_client import log_activity

DEFAULT_STEPS = [
    (1,  "Survey & Engineering"),
    (2,  "Document Collection"),
    (3,  "National Portal Application"),
    (4,  "Loan Approval"),
    (5,  "MSEDCL Application"),
    (6,  "Structure Fabrication"),
    (7,  "Electrical Installation"),
    (8,  "Release Order Application"),
    (9,  "Meter Testing"),
    (10, "National Portal Installation Details"),
    (11, "Net Meter Installation"),
    (12, "Project Commissioning"),
    (13, "Subsidy Process"),
    (14, "Project Handover"),
]

STEP_ICONS = ["📐", "📋", "🖥️", "🏦", "🏛️", "🔧", "⚡", "📑", "🧪", "🌐", "🔌", "⚙️", "🎁", "📦"]

DEFAULT_DOCS = [
    "WCR", "ANNEXURE I", "DCR CERTIFICATE",
    "NET METER AGREEMENT", "DATA SHEET", "SITE PHOTOS",
]


# ── data helpers ──────────────────────────────────────────────────────────────

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
        name_by_no = {n: name for n, name in DEFAULT_STEPS}
        changed = False
        # 1) normalize names of existing steps to the current set
        for r in rows:
            want = name_by_no.get(r.get("step_no"))
            if want and r.get("step_name") != want:
                supabase.table("project_steps").update({"step_name": want}).eq("id", r["id"]).execute()
                r["step_name"] = want
                changed = True
        # 2) add any steps that don't exist yet (e.g. new steps 11–14)
        existing_nos = {r.get("step_no") for r in rows}
        missing = [(n, name) for n, name in DEFAULT_STEPS if n not in existing_nos]
        if missing:
            supabase.table("project_steps").insert([
                {"project_id": project_id, "step_no": n, "step_name": name,
                 "status": "pending", "progress_percent": 0}
                for n, name in missing
            ]).execute()
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
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%b %d, %Y")
    except Exception:
        return s[:10]


def _fmt_datetime(val):
    if not val:
        return "-"
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00")).strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return str(val)[:16]


# ── style helpers ─────────────────────────────────────────────────────────────

CARD     = "background:#0d1a2e;border:1px solid #16304d;border-radius:12px;padding:16px 18px;margin-bottom:6px"
NOTECARD = ("background:#1c1708;border:1px solid #a16207;border-left:4px solid #f59e0b;"
            "border-radius:12px;padding:16px 18px;margin-bottom:6px")


def _card(inner_html, style=CARD):
    """Render one whole section as a single bordered card (no empty bars)."""
    st.markdown(f"<div style='{style}'>{inner_html}</div>", unsafe_allow_html=True)


def _title(icon, text):
    return (f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:12px'>"
            f"<span style='font-size:1rem'>{icon}</span>"
            f"<span style='font-weight:700;font-size:0.92rem;color:#e2e8f0;letter-spacing:0.5px'>{text}</span></div>")


def _kv(label, value, vcolor="#f1f5f9"):
    return (f"<div style='margin-bottom:10px'>"
            f"<div style='color:#64748b;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.5px'>{label}</div>"
            f"<div style='color:{vcolor};font-size:0.9rem;font-weight:600;margin-top:2px'>{value}</div></div>")


def _grid(items, cols):
    return (f"<div style='display:grid;grid-template-columns:repeat({cols},1fr);gap:4px 16px'>"
            + "".join(items) + "</div>")


def _status_pill(status):
    s = (status or "").lower()
    if s == "completed":
        return '<span style="background:#16a34a22;color:#22c55e;border:1px solid #16a34a;padding:3px 12px;border-radius:6px;font-size:0.72rem;font-weight:700">Completed</span>'
    if s in ("cancelled", "rejected"):
        return '<span style="background:#dc262622;color:#ef4444;border:1px solid #dc2626;padding:3px 12px;border-radius:6px;font-size:0.72rem;font-weight:700">Cancelled</span>'
    return '<span style="background:#2563eb22;color:#3b82f6;border:1px solid #2563eb;padding:3px 12px;border-radius:6px;font-size:0.72rem;font-weight:700">In Progress</span>'


def _donut(progress):
    return (f"<div style='display:flex;flex-direction:column;align-items:center'>"
            f"<div style='width:104px;height:104px;border-radius:50%;background:conic-gradient(#22c55e {progress}%,#1e293b 0);"
            f"display:flex;align-items:center;justify-content:center'>"
            f"<div style='width:78px;height:78px;border-radius:50%;background:#0d1a2e;display:flex;flex-direction:column;"
            f"align-items:center;justify-content:center'>"
            f"<div style='font-size:1.15rem;font-weight:800;color:#f1f5f9'>{progress}%</div>"
            f"<div style='font-size:0.55rem;color:#64748b'>Complete</div></div></div>"
            f"<div style='color:#64748b;font-size:0.6rem;margin-top:6px'>Overall Progress</div></div>")


# ── main renderer ─────────────────────────────────────────────────────────────

def render_project_detail(supabase, project, role="admin"):
    pid          = project["id"]
    steps        = _get_or_create_steps(supabase, pid)
    installments = _get_installments(supabase, pid)
    docs         = _get_or_create_docs(supabase, pid)
    notes        = _get_notes(supabase, pid)
    logs         = _get_project_logs(supabase, pid)

    done_steps   = sum(1 for s in steps if s.get("status") == "completed")
    progress     = int(done_steps / len(steps) * 100) if steps else 0
    project_code = project.get("project_code") or f"EPC-{str(pid)[:8].upper()}"

    cur_stage = next((s for s in steps if s.get("status") == "in_progress"), None) \
        or next((s for s in steps if s.get("status") == "pending"), None) \
        or (steps[-1] if steps else None)
    cur_name = cur_stage.get("step_name", "-") if cur_stage else "-"
    cur_no   = cur_stage.get("step_no", "-") if cur_stage else "-"

    # ── top bar ──────────────────────────────────────────────────
    tb1, tb2 = st.columns([3, 1])
    with tb1:
        st.markdown(
            "<div style='display:flex;align-items:center;gap:10px'>"
            "<span style='color:#64748b;font-size:0.85rem'>Edit Customers</span>"
            "<span style='color:#475569'>›</span>"
            "<span style='font-weight:800;font-size:1.15rem;color:#3b82f6'>📂 PROJECT DETAILS</span></div>",
            unsafe_allow_html=True)
    with tb2:
        if st.button("← Back", key="back_to_dash", use_container_width=True):
            st.session_state.selected_project_id = None
            st.rerun()
    st.markdown(
        f"<div style='color:#64748b;font-size:0.72rem;margin:2px 0 12px'>Last updated: "
        f"{_fmt_datetime(project.get('updated_at') or project.get('created_at'))}</div>",
        unsafe_allow_html=True)

    # ── PROJECT SUMMARY | SUBSIDY ────────────────────────────────
    sum_col, sub_col = st.columns([1.75, 1])
    with sum_col:
        left = _grid([
            _kv("Project ID", project_code, "#f97316"),
            _kv("Customer Name", project.get("customer_name", "-") or "-"),
            _kv("Last Updated On", _fmt_datetime(project.get("updated_at") or project.get("created_at"))),
            _kv("Current Stage", f"#{cur_no} · {cur_name}"),
        ], 2)
        inner = (_title("📑", "PROJECT SUMMARY")
                 + f"<div style='display:flex;gap:18px;align-items:center'>"
                   f"<div style='flex:1'>{left}</div><div>{_donut(progress)}</div></div>")
        _card(inner)
        with st.expander("✏️ Edit Project ID"):
            with st.form("edit_pid_form"):
                new_code = st.text_input("Project ID", value=project.get("project_code") or "",
                                         placeholder="e.g. EPC-2026-001")
                if st.form_submit_button("💾 Save"):
                    supabase.table("projects").update({"project_code": new_code.strip()}).eq("id", pid).execute()
                    log_activity(supabase, f"Set Project ID → {new_code.strip()}", entity_type="project",
                                 project_id=pid, project_name=project.get("customer_name"))
                    st.toast("✅ Saved!", icon="✅"); st.rerun()
    with sub_col:
        _render_subsidy(supabase, project, installments)

    # ── CUSTOMER INFO | PROJECT INFO ─────────────────────────────
    ci, pi = st.columns(2)
    with ci:
        inner = _title("👤", "CUSTOMER INFORMATION") + _grid([
            _kv("Customer Name 🔒", project.get("customer_name", "-") or "-"),
            _kv("Mobile Number", project.get("mobile", "-") or "-"),
            _kv("Email", project.get("email", "-") or "-"),
            _kv("Alternate Mobile", project.get("alt_mobile", "-") or "-"),
            _kv("Aadhar Number", project.get("aadhar_number", "-") or "-"),
            _kv("PAN Number", project.get("pan_number", "-") or "-"),
        ], 3)
        _card(inner)
        with st.expander("✏️ Edit Customer Information"):
            with st.form("edit_cust_form"):
                e_name = st.text_input("Customer Name", value=project.get("customer_name", "") or "")
                e_mob  = st.text_input("Mobile Number", value=project.get("mobile", "") or "")
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
                    st.toast("✅ Saved!", icon="✅"); st.rerun()

    with pi:
        inner = _title("📋", "PROJECT INFORMATION") + _grid([
            _kv("System Size (kWp)", f"{project.get('system_size_kwp', 0) or 0} kWp"),
            _kv("Connection Type", project.get("connection_type", "-") or "-"),
            _kv("Execution Partner", project.get("execution_partner", "-") or "-"),
            _kv("Discom", project.get("discom", "MSEDCL") or "MSEDCL"),
            _kv("Project Created On 🔒", _fmt_date(project.get("created_at"))),
            _kv("Project Status", _status_pill(project.get("project_status"))),
        ], 3)
        _card(inner)
        with st.expander("✏️ Edit Project Information"):
            with st.form("edit_proj_form"):
                pe1, pe2 = st.columns(2)
                with pe1:
                    e_size = st.number_input("System Size (kWp)", min_value=0.0, step=0.5,
                                             value=float(project.get("system_size_kwp", 0) or 0))
                    e_conn = st.selectbox("Connection Type", ["On-Grid", "Off-Grid", "Hybrid"],
                                          index=["On-Grid", "Off-Grid", "Hybrid"].index(project.get("connection_type"))
                                          if (project.get("connection_type") in ["On-Grid", "Off-Grid", "Hybrid"]) else 0)
                with pe2:
                    e_exec = st.text_input("Execution Partner", value=project.get("execution_partner", "") or "")
                    e_disc = st.text_input("Discom", value=project.get("discom", "MSEDCL") or "MSEDCL")
                eb1, eb2 = st.columns(2)
                with eb1:
                    e_bank = st.text_input("Bank Name", value=project.get("bank_name", "") or "")
                with eb2:
                    _ls = ["—", "Applied", "Approved", "Disbursed", "Rejected"]
                    e_lstat = st.selectbox("Loan Status", _ls,
                                           index=_ls.index(project.get("loan_status")) if project.get("loan_status") in _ls else 0)
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
                    st.toast("✅ Saved!", icon="✅"); st.rerun()

    # ── PROJECT WORKFLOW & MILESTONES (horizontal scroll) ────────
    steps_html = "<div style='display:flex;gap:8px;overflow-x:auto;padding-bottom:8px'>"
    for i, step in enumerate(steps):
        sstatus = step.get("status", "pending")
        if sstatus == "completed":
            ring, badge, lbl = "#22c55e", "#16a34a", "<span style='color:#22c55e;font-size:0.6rem;font-weight:700'>✓ Completed</span>"
        elif sstatus == "in_progress":
            ring, badge, lbl = "#3b82f6", "#2563eb", "<span style='color:#3b82f6;font-size:0.6rem;font-weight:700'>● In Progress</span>"
        else:
            ring, badge, lbl = "#475569", "#1e293b", "<span style='color:#ef4444;font-size:0.6rem;font-weight:700'>Pending</span>"
        date_txt = _fmt_date(step.get("end_date") or step.get("start_date"))
        bdr = ring if sstatus != "pending" else "#1e293b"
        icon = STEP_ICONS[i] if i < len(STEP_ICONS) else "•"
        steps_html += (
            f"<div style='flex:0 0 100px;text-align:center;border:1px solid {bdr};border-radius:10px;"
            f"padding:10px 4px 8px;background:#0b1626'>"
            f"<div style='background:{badge};border:2px solid {ring};border-radius:50%;width:24px;height:24px;"
            f"line-height:20px;font-size:0.66rem;font-weight:700;color:#fff;margin:0 auto 6px'>{step.get('step_no', i+1)}</div>"
            f"<div style='font-size:0.95rem;margin-bottom:2px'>{icon}</div>"
            f"<div style='font-size:0.58rem;font-weight:700;color:#cbd5e1;line-height:1.15;min-height:26px'>{step.get('step_name','')}</div>"
            f"<div style='font-size:0.54rem;color:#64748b;margin:2px 0'>{date_txt}</div>{lbl}</div>")
    steps_html += "</div>"
    _card(_title("🛠️", "PROJECT WORKFLOW & MILESTONES") + steps_html)

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
            st.toast("✅ Step updated!", icon="✅"); st.rerun()

    # ── BOTTOM GRID: Financials | Documents + Notes | Timeline ───
    fin_col, doc_col, time_col = st.columns([2.1, 1.2, 1.2])
    with fin_col:
        _render_financials(supabase, project, installments)
    with doc_col:
        _render_documents(supabase, project, docs)
        _render_internal_notes(supabase, project, notes)
    with time_col:
        _render_timeline(supabase, project, logs)

    # ── SAVE CHANGES ─────────────────────────────────────────────
    sv1, sv2 = st.columns([4, 1])
    with sv2:
        if st.button("💾 SAVE CHANGES", type="primary", use_container_width=True, key="detail_save"):
            st.toast("✅ All edits are saved per section as you make them.")


def _render_subsidy(supabase, project, installments):
    pid        = project["id"]
    total      = float(project.get("total_cost", 0) or 0)
    sub_amt    = float(project.get("subsidy_amount", 0) or 0)
    sub_status = (project.get("subsidy_status") or "pending").lower()
    appl_date  = project.get("subsidy_applied_date")
    disb_date  = project.get("subsidy_disbursed_date")
    is_disb    = sub_status == "disbursed"

    applied_html = (f"<span style='color:#22c55e'>✅ Yes</span> "
                    f"<span style='color:#64748b;font-size:0.72rem'>({_fmt_date(appl_date)})</span>"
                    if appl_date else "<span style='color:#ef4444'>❌ No</span>")
    disb_html    = (f"<span style='color:#22c55e'>✅ Yes</span> "
                    f"<span style='color:#64748b;font-size:0.72rem'>({_fmt_date(disb_date)})</span>"
                    if is_disb else "<span style='color:#ef4444'>❌ Not yet</span>")

    inner = (_title("🏛️", "SUBSIDY INFORMATION")
             + _kv("Amount Expected", format_currency(sub_amt), "#f59e0b")
             + _kv("Applied", applied_html)
             + _kv("Disbursed", disb_html))
    _card(inner)

    with st.expander("✏️ Update Subsidy"):
        with st.form("edit_subsidy_form"):
            s_amt = st.number_input("Subsidy Amount Expected (₹)", min_value=0.0, step=1000.0,
                                    value=float(project.get("subsidy_amount", 0) or 0))
            s_applied = st.checkbox("Applied for subsidy", value=bool(appl_date))
            s_appl_dt = st.date_input("Applied date", value=None, key="sub_appl_dt")
            s_disb    = st.checkbox("Disbursed", value=is_disb)
            s_disb_dt = st.date_input("Disbursement date", value=None, key="sub_disb_dt")
            if st.form_submit_button("💾 Save Subsidy"):
                import datetime as _dt
                payload = {"subsidy_amount": s_amt}
                if s_applied:
                    payload["subsidy_applied_date"] = str(s_appl_dt or appl_date or _dt.date.today())
                if s_disb:
                    _dd = str(s_disb_dt or disb_date or _dt.date.today())
                    payload["subsidy_status"] = "disbursed"
                    payload["subsidy_disbursed_date"] = _dd
                    # complete the Subsidy Process workflow step
                    try:
                        steps = supabase.table("project_steps").select("id,step_name")\
                            .eq("project_id", pid).execute().data or []
                        for s in steps:
                            if "subsidy" in (s.get("step_name", "").lower()):
                                supabase.table("project_steps").update({
                                    "status": "completed", "progress_percent": 100, "end_date": _dd,
                                }).eq("id", s["id"]).execute()
                    except Exception:
                        pass
                    # post subsidy as a payment so it counts to Received (no double-count)
                    try:
                        subs = [i for i in installments if (i.get("payment_type") or "").lower() == "subsidy"]
                        if subs:
                            supabase.table("installments").update(
                                {"amount": s_amt, "due_date": _dd, "status": "paid"}
                            ).eq("id", subs[0]["id"]).execute()
                        elif s_amt > 0:
                            existing = supabase.table("installments").select("installment_no").eq("project_id", pid).execute().data or []
                            nxt = max([e.get("installment_no", 0) for e in existing], default=0) + 1
                            supabase.table("installments").insert({
                                "project_id": pid, "installment_no": nxt, "amount": s_amt,
                                "due_date": _dd, "status": "paid", "payment_type": "Subsidy",
                            }).execute()
                        allp = supabase.table("installments").select("amount").eq("project_id", pid).execute().data or []
                        recv = sum(float(a.get("amount", 0) or 0) for a in allp)
                        supabase.table("projects").update({"amount_paid": recv, "balance": total - recv}).eq("id", pid).execute()
                    except Exception:
                        pass
                else:
                    payload["subsidy_status"] = "applied" if s_applied else "pending"
                try:
                    supabase.table("projects").update(payload).eq("id", pid).execute()
                except Exception as e:
                    st.error(f"Save failed (run subsidy date migration?): {e}")
                    st.stop()
                log_activity(supabase, "Subsidy updated"
                             + (" → disbursed (Subsidy Process completed)" if s_disb else ""),
                             entity_type="project", project_id=pid,
                             project_name=project.get("customer_name"))
                st.toast("✅ Saved!", icon="✅"); st.rerun()


def _render_financials(supabase, project, installments):
    pid      = project["id"]
    total    = float(project.get("total_cost", 0) or 0)
    received = sum(float(i.get("amount", 0) or 0) for i in installments)
    due      = total - received
    rec_pct  = round(received / total * 100, 1) if total else 0
    due_pct  = round(due / total * 100, 1) if total else 0
    pay_mode = "Loan" if (project.get("payment_mode") or "").upper() == "LOAN" else "Cash"

    if pay_mode == "Loan":
        _lstat = project.get("loan_status") or "—"
        pm_val = (f"<span style='color:#a78bfa'>Loan</span><br>"
                  f"<span style='color:#22c55e;font-size:0.68rem'>{_lstat}</span><br>"
                  f"<span style='color:#64748b;font-size:0.68rem'>Bank: {project.get('bank_name','-') or '-'}</span>")
    else:
        pm_val = "<span style='color:#22c55e'>Cash</span>"

    metrics = _grid([
        _kv("Total Project Cost", format_currency(total), "#3b82f6"),
        _kv("Received Amount", f"{format_currency(received)} <span style='color:#22c55e;font-size:0.7rem'>({rec_pct}%)</span>", "#22c55e"),
        _kv("Due Amount", f"{format_currency(due)} <span style='color:#ef4444;font-size:0.7rem'>({due_pct}%)</span>", "#ef4444"),
        _kv("Payment Mode", pm_val),
    ], 4)

    breakdown = ""
    if installments:
        breakdown = ("<div style='margin-top:8px;border-top:1px solid #16304d;padding-top:8px'>"
                     "<div style='color:#64748b;font-size:0.66rem;text-transform:uppercase;margin-bottom:4px'>Received breakdown</div>")
        for i in installments:
            typ = i.get("payment_type") or "Installment"
            breakdown += (f"<div style='font-size:0.72rem;color:#94a3b8;padding:2px 0'>"
                          f"<span style='color:#cbd5e1'>{typ}</span> · "
                          f"<span style='color:#22c55e;font-weight:600'>{format_currency(float(i.get('amount',0) or 0))}</span> · "
                          f"<span style='color:#64748b'>{_fmt_date(i.get('due_date'))}</span></div>")
        breakdown += "</div>"

    _card(_title("💰", "FINANCIAL PROGRESS") + metrics + breakdown)

    with st.expander("➕ Add Payment / Installment"):
        with st.form("add_payment_form"):
            pc1, pc2, pc3 = st.columns(3)
            with pc1:
                ptype = st.selectbox("Type", ["Advance Payment", "Installment", "Subsidy"], key="pay_type_sel")
            with pc2:
                iamt = st.number_input("Amount (₹)", min_value=0.0, step=5000.0, value=None, placeholder="0", key="pay_amt") or 0.0
            with pc3:
                ipdate = st.date_input("Payment Date", key="pay_date")
            if st.form_submit_button("💾 Add Payment"):
                if iamt <= 0:
                    st.error("Enter an amount.")
                else:
                    existing = supabase.table("installments").select("installment_no").eq("project_id", pid).execute().data or []
                    nxt = max([e.get("installment_no", 0) for e in existing], default=0) + 1
                    row = {"project_id": pid, "installment_no": nxt, "amount": iamt,
                           "due_date": str(ipdate), "status": "paid"}
                    try:
                        supabase.table("installments").insert({**row, "payment_type": ptype}).execute()
                    except Exception:
                        supabase.table("installments").insert(row).execute()
                    new_recv = received + iamt
                    supabase.table("projects").update({
                        "amount_paid": new_recv, "balance": total - new_recv,
                    }).eq("id", pid).execute()
                    log_activity(supabase, f"Payment: {ptype}", entity_type="installment",
                                 project_id=pid, project_name=project.get("customer_name"),
                                 details=f"₹{iamt:,.0f} · {ipdate}")
                    st.toast("✅ Payment added!", icon="✅"); st.rerun()


def _render_documents(supabase, project, docs):
    pid = project["id"]
    rows = ""
    for i, doc in enumerate(docs, start=1):
        uploaded = doc.get("status") == "uploaded"
        clr = "#22c55e" if uploaded else "#ef4444"
        bg  = "#16a34a22" if uploaded else "#dc262622"
        lbl = "Uploaded" if uploaded else "Pending"
        rows += (f"<div style='display:flex;justify-content:space-between;align-items:center;"
                 f"padding:7px 0;border-bottom:1px solid #16304d'>"
                 f"<span style='color:#cbd5e1;font-size:0.78rem'>{i}. {doc.get('doc_name','')}</span>"
                 f"<span style='background:{bg};color:{clr};padding:2px 9px;border-radius:5px;"
                 f"font-size:0.66rem;font-weight:700'>{lbl}</span></div>")
    _card(_title("📄", "DOCUMENTS CHECKLIST") + rows)
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
                st.toast("✅ Document updated!", icon="✅"); st.rerun()


def _render_internal_notes(supabase, project, notes):
    pid = project["id"]
    if notes:
        latest = notes[0]
        body = f"<div style='font-size:0.86rem;color:#fef3c7;line-height:1.6;font-weight:500'>{latest.get('note','')}</div>"
        if latest.get("next_action"):
            body += f"<div style='margin-top:8px;border-left:3px solid #f59e0b;padding-left:10px;font-size:0.8rem;color:#fbbf24'>Next: {latest.get('next_action')}</div>"
        body += f"<div style='color:#a16207;font-size:0.68rem;margin-top:8px'>Last note added: {_fmt_datetime(latest.get('created_at'))}</div>"
    else:
        body = "<div style='color:#a16207;font-size:0.82rem'>No notes yet — add one below.</div>"
    _card(_title("📝", "INTERNAL NOTES") + body, style=NOTECARD)
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
                    st.toast("✅ Note saved!", icon="✅"); st.rerun()

        # existing notes with delete (outside the form so buttons work)
        if notes:
            st.markdown("<div style='color:#64748b;font-size:0.72rem;text-transform:uppercase;margin-top:6px'>Existing notes</div>", unsafe_allow_html=True)
            for n in notes:
                nc1, nc2 = st.columns([5, 1])
                with nc1:
                    _nt = (n.get("note", "") or "")[:80]
                    st.markdown(f"<div style='font-size:0.8rem;color:#cbd5e1'>{_nt}</div>"
                                f"<div style='font-size:0.66rem;color:#64748b'>{_fmt_datetime(n.get('created_at'))}</div>",
                                unsafe_allow_html=True)
                with nc2:
                    if st.button("🗑️", key=f"del_note_{n['id']}", help="Delete note"):
                        supabase.table("project_notes").delete().eq("id", n["id"]).execute()
                        log_activity(supabase, "Deleted note", entity_type="note",
                                     project_id=pid, project_name=project.get("customer_name"))
                        st.toast("🗑️ Note deleted", icon="🗑️"); st.rerun()


def _render_timeline(supabase, project, logs):
    items = ""
    if logs:
        for lg in logs:
            items += (f"<div style='border-left:2px solid #2563eb;padding:0 0 12px 14px;position:relative'>"
                      f"<div style='position:absolute;left:-5px;top:2px;width:8px;height:8px;border-radius:50%;background:#3b82f6'></div>"
                      f"<div style='font-size:0.68rem;color:#94a3b8'>{_fmt_datetime(lg.get('created_at'))}</div>"
                      f"<div style='font-size:0.78rem;color:#e2e8f0'>{lg.get('action','')}</div>"
                      f"<div style='font-size:0.66rem;color:#64748b'>{lg.get('user_name','') or ''}</div></div>")
    else:
        items = "<div style='color:#475569;font-size:0.82rem'>No activity recorded yet.</div>"
    _card(_title("🕐", "PROJECT TIMELINE") + items)
