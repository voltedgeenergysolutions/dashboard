"""Project Detail View — full per-project dashboard"""

import streamlit as st
import plotly.graph_objects as go
from .utils import format_currency
from .supabase_client import log_activity

DEFAULT_STEPS = [
    (1,  "Get Documents"),
    (2,  "Survey"),
    (3,  "MSEDCL Approval"),
    (4,  "Loan Approval"),
    (5,  "Subsidy Application"),
    (6,  "Subsidy Received"),
    (7,  "Meter Installed"),
    (8,  "Structure Done"),
    (9,  "Installation Completed"),
    (10, "Commissioning & Handover"),
]

DEFAULT_DOCS = [
    "Identity Proof", "Address Proof", "Electricity Bill",
    "Property Documents", "Cancelled Cheque", "Photo (Site)",
]


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_or_create_steps(supabase, project_id):
    rows = supabase.table("project_steps").select("*").eq("project_id", project_id).order("step_no").execute().data
    if not rows:
        supabase.table("project_steps").insert([
            {"project_id": project_id, "step_no": n, "step_name": name,
             "status": "pending", "progress_percent": 0}
            for n, name in DEFAULT_STEPS
        ]).execute()
        rows = supabase.table("project_steps").select("*").eq("project_id", project_id).order("step_no").execute().data
    return rows or []


def _get_or_create_docs(supabase, project_id):
    rows = supabase.table("project_documents").select("*").eq("project_id", project_id).execute().data
    if not rows:
        supabase.table("project_documents").insert([
            {"project_id": project_id, "doc_name": d, "status": "pending"}
            for d in DEFAULT_DOCS
        ]).execute()
        rows = supabase.table("project_documents").select("*").eq("project_id", project_id).execute().data
    return rows or []


def _get_installments(supabase, project_id):
    return supabase.table("installments").select("*").eq("project_id", project_id).order("installment_no").execute().data or []


def _get_notes(supabase, project_id):
    return supabase.table("project_notes").select("*").eq("project_id", project_id).order("created_at", desc=True).execute().data or []


# ── main renderer ─────────────────────────────────────────────────────────────

def render_project_detail(supabase, project, role="admin"):
    """Render the full project detail dashboard for one project."""

    # ── back button ──────────────────────────────────────────────
    if st.button("← Back to Dashboard", key="back_to_dash"):
        st.session_state.selected_project_id = None
        st.rerun()

    st.markdown("<hr style='margin:8px 0 14px'>", unsafe_allow_html=True)

    # ── fetch related data ────────────────────────────────────────
    steps        = _get_or_create_steps(supabase, project["id"])
    installments = _get_installments(supabase, project["id"])
    docs         = _get_or_create_docs(supabase, project["id"])
    notes        = _get_notes(supabase, project["id"])

    # progress calculation
    done_steps = sum(1 for s in steps if s.get("status") == "completed")
    progress   = int(done_steps / len(steps) * 100) if steps else 0
    project_code = project.get("project_code") or f"EPC-{str(project['id'])[:8].upper()}"

    # ── header row ───────────────────────────────────────────────
    hc1, hc2 = st.columns([3, 1])

    with hc1:
        st.markdown(f"""
        <div style="color:#64748b;font-size:0.72rem;letter-spacing:1px">CUSTOMER</div>
        <div style="font-size:1.75rem;font-weight:800;margin:2px 0">{project.get('customer_name','')}</div>
        <div style="color:#64748b;font-size:0.82rem">Premium Solar EPC Project</div>
        """, unsafe_allow_html=True)
        st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        m1.metric("Project ID",   project_code)
        m2.metric("System Size",  f"{project.get('system_size_kwp', 0)} kWp")
        m3.metric("Location",     project.get("location", "-") or "-")

    with hc2:
        fig_p = go.Figure(go.Pie(
            values=[max(progress, 1), 100 - max(progress, 1)],
            hole=0.72,
            marker_colors=["#dc2626", "#1e293b"],
            showlegend=False, textinfo="none",
            direction="clockwise", sort=False,
        ))
        fig_p.add_annotation(
            text=f"<b>{progress}%</b><br><span style='font-size:11px'>COMPLETED</span>",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=18, color="#f1f5f9"),
        )
        fig_p.update_layout(
            height=170, margin=dict(t=4, b=4, l=4, r=4),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_p, use_container_width=True)
        st.markdown(
            "<div style='text-align:center;color:#dc2626;font-size:0.68rem;font-weight:700;letter-spacing:1px'>"
            "STAY FOCUSED. EXECUTE. DELIVER.</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='margin:14px 0'>", unsafe_allow_html=True)

    # ── execution steps ──────────────────────────────────────────
    st.markdown("**PROJECT EXECUTION STEPS**")
    status_color = {"completed": "#22c55e", "in_progress": "#f59e0b", "pending": "#475569"}
    cols = st.columns(10)

    for i, step in enumerate(steps[:10]):
        sstatus = step.get("status", "pending")
        sprog   = step.get("progress_percent", 0)
        color   = status_color.get(sstatus, "#475569")
        bg      = "#dc2626" if sstatus == "completed" else ("#f59e0b" if sstatus == "in_progress" else "#1e293b")

        with cols[i]:
            st.markdown(f"""
            <div style="text-align:center">
              <div style="background:{bg};border:2px solid {color};border-radius:50%;
                          width:26px;height:26px;line-height:26px;font-size:0.7rem;
                          font-weight:700;color:#fff;margin:0 auto 5px">{step.get('step_no',i+1)}</div>
              <div style="font-size:0.6rem;font-weight:700;color:#cbd5e1;line-height:1.2;min-height:28px">{step.get('step_name','')}</div>
              <div style="font-size:0.58rem;color:{color};margin:3px 0">{sstatus.replace('_',' ').title()}</div>
              <div style="font-size:0.55rem;color:#64748b">Start:<br>{step.get('start_date','-') or '-'}</div>
              <div style="font-size:0.55rem;color:#64748b">End:<br>{step.get('end_date','-') or '-'}</div>
            </div>""", unsafe_allow_html=True)
            if sstatus == "in_progress" and sprog:
                st.progress(sprog / 100)

    st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
    st.progress(progress / 100, text=f"Overall Progress  {progress}%")

    # ── edit steps expander ───────────────────────────────────────
    with st.expander("✏️ Update Step Status"):
        opts = [f"{s['step_no']}. {s['step_name']}" for s in steps]
        chosen = st.selectbox("Step", opts, key="upd_step_sel")
        idx    = int(chosen.split(".")[0]) - 1
        sel    = steps[idx]
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            new_st = st.selectbox("Status", ["pending","in_progress","completed"],
                index=["pending","in_progress","completed"].index(sel.get("status","pending")),
                key="upd_status")
        with sc2:
            new_pr = st.slider("Progress %", 0, 100, sel.get("progress_percent", 0), key="upd_prog")
        with sc3:
            new_sd = st.date_input("Start Date", value=None, key="upd_sd")
        with sc4:
            new_ed = st.date_input("End Date",   value=None, key="upd_ed")
        if st.button("💾 Update Step", key="upd_step_btn"):
            payload = {"status": new_st, "progress_percent": new_pr}
            if new_sd: payload["start_date"] = str(new_sd)
            if new_ed: payload["end_date"]   = str(new_ed)
            supabase.table("project_steps").update(payload).eq("id", sel["id"]).execute()
            log_activity(supabase, f"Updated step '{sel['step_name']}' → {new_st}",
                         entity_type="step",
                         project_id=project["id"],
                         project_name=project.get("customer_name"),
                         details=f"Progress: {new_pr}%")
            st.success("✅ Step updated!")
            st.rerun()

    st.markdown("<hr style='margin:16px 0'>", unsafe_allow_html=True)

    # ── payment summary + financial overview (ADMIN ONLY) ─────────
    if role != "admin":
        st.info("💼 Financial details are visible to admins only.")
        st.markdown("<hr style='margin:16px 0'>", unsafe_allow_html=True)

    pc1, pc2 = st.columns(2) if role == "admin" else (None, None)
    if role != "admin":
        # skip financial sections — jump to status/docs/notes
        _render_bottom_sections(supabase, project, docs, notes)
        return

    with pc1:
        st.markdown("**PAYMENT SUMMARY**")
        pay_mode  = (project.get("payment_mode") or "Cash").title()
        total_amt = float(project.get("total_cost", 0) or 0)
        pm_color  = "#3b82f6" if pay_mode.lower() == "loan" else "#22c55e"
        st.markdown(f"""
        <div style="background:#1e293b;border-radius:10px;padding:16px">
          <div style="color:#64748b;font-size:0.72rem;text-transform:uppercase">Payment Mode</div>
          <div style="margin:8px 0">
            <span style="background:{pm_color};color:#fff;padding:4px 16px;
                         border-radius:20px;font-size:0.85rem;font-weight:600">{pay_mode}</span>
          </div>
          <div style="color:#64748b;font-size:0.72rem;margin-top:10px">TOTAL AMOUNT</div>
          <div style="font-size:1.5rem;font-weight:800;color:#dc2626">{format_currency(total_amt)}</div>
          <div style="color:#64748b;font-size:0.7rem">(Including GST)</div>
        </div>
        """, unsafe_allow_html=True)

        if installments:
            st.markdown("<div style='margin-top:8px;color:#94a3b8;font-size:0.78rem'>INSTALLMENT PLAN</div>", unsafe_allow_html=True)
            inst_html = '<div style="background:#1e293b;border-radius:8px;padding:10px 14px">'
            for inst in installments:
                icon = "✅" if inst.get("status") == "paid" else "⏳"
                inst_html += f"""
                <div style="display:flex;justify-content:space-between;align-items:center;
                             padding:6px 0;border-bottom:1px solid #334155;font-size:0.8rem">
                  <span>{icon} Installment {inst.get('installment_no','')}</span>
                  <span style="color:#64748b">Due: {inst.get('due_date','-') or '-'}</span>
                  <span style="font-weight:700;color:#f1f5f9">{format_currency(float(inst.get('amount',0) or 0))}</span>
                </div>"""
            inst_html += "</div>"
            st.markdown(inst_html, unsafe_allow_html=True)

        with st.expander("➕ Add Installment"):
            with st.form("add_inst_form"):
                ai1, ai2 = st.columns(2)
                with ai1:
                    ino  = st.number_input("Installment #", min_value=1, value=len(installments)+1, key="ino")
                    iamt = st.number_input("Amount (₹)", min_value=0.0, step=5000.0, key="iamt")
                with ai2:
                    idue = st.date_input("Due Date", key="idue")
                    ist  = st.selectbox("Status", ["pending","paid"], key="ist")
                if st.form_submit_button("Add Installment"):
                    supabase.table("installments").insert({
                        "project_id": project["id"],
                        "installment_no": int(ino),
                        "amount": iamt,
                        "due_date": str(idue),
                        "status": ist,
                    }).execute()
                    log_activity(supabase, f"Added installment #{int(ino)}",
                                 entity_type="installment",
                                 project_id=project["id"],
                                 project_name=project.get("customer_name"),
                                 details=f"Amount: ₹{iamt:,.0f} | Due: {idue} | Status: {ist}")
                    st.success("✅ Installment added!")
                    st.rerun()

    with pc2:
        st.markdown("**FINANCIAL OVERVIEW**")
        rows = [
            ("System Size",           f"{project.get('system_size_kwp',0)} kWp",                            "#f1f5f9"),
            ("Total Project Cost",    format_currency(float(project.get('total_cost',    0) or 0)),         "#f1f5f9"),
            ("Subsidy Amount (Est.)", format_currency(float(project.get('subsidy_amount',0) or 0)),         "#f1f5f9"),
            ("Net Payable",           format_currency(float(project.get('net_payable',   0) or 0)),         "#f1f5f9"),
            ("Amount Paid",           format_currency(float(project.get('amount_paid',   0) or 0)),         "#22c55e"),
            ("Balance",               format_currency(float(project.get('balance',       0) or 0)),         "#ef4444"),
        ]
        html = '<div style="background:#1e293b;border-radius:10px;padding:16px">'
        for lbl, val, clr in rows:
            html += f"""
            <div style="display:flex;justify-content:space-between;padding:8px 0;
                        border-bottom:1px solid #334155">
              <span style="color:#94a3b8;font-size:0.84rem">{lbl}</span>
              <span style="font-weight:700;font-size:0.84rem;color:{clr}">{val}</span>
            </div>"""
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

    st.markdown("<hr style='margin:16px 0'>", unsafe_allow_html=True)
    _render_bottom_sections(supabase, project, docs, notes)


def _render_bottom_sections(supabase, project, docs, notes):
    """Important status, documents checklist, and notes — shown to all roles."""
    bc1, bc2, bc3 = st.columns(3)

    with bc1:
        st.markdown("**IMPORTANT STATUS**")
        fields = [
            ("MSEDCL Application No.",  project.get("msedcl_application_no",  "-") or "-"),
            ("Net Metering Status",     project.get("net_metering_status",     "Pending")),
            ("Subsidy Type",            project.get("subsidy_type",            "MNRE (Residential)")),
            ("Subsidy Application No.", project.get("subsidy_application_no",  "-") or "-"),
            ("Subsidy Status",          project.get("subsidy_status",          "Not Applied")),
            ("Meter Type",              project.get("meter_type",              "Net Meter")),
            ("Estimated Generation",    project.get("estimated_generation",    "-") or "-"),
        ]
        html = '<div style="background:#1e293b;border-radius:10px;padding:14px">'
        for lbl, val in fields:
            html += f"""
            <div style="display:flex;justify-content:space-between;padding:5px 0;
                        border-bottom:1px solid #334155">
              <span style="color:#94a3b8;font-size:0.76rem">{lbl}</span>
              <span style="font-size:0.76rem;font-weight:600;color:#f1f5f9">{val}</span>
            </div>"""
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

        with st.expander("✏️ Edit Status"):
            with st.form("edit_status_form"):
                new_msedcl  = st.text_input("MSEDCL Application No.", value=project.get("msedcl_application_no","") or "")
                new_nm      = st.selectbox("Net Metering Status", ["Pending","Applied","Approved","Rejected"],
                                index=["Pending","Applied","Approved","Rejected"].index(project.get("net_metering_status","Pending") or "Pending"))
                new_sub_st  = st.selectbox("Subsidy Status", ["Not Applied","Applied","Approved","Received"],
                                index=["Not Applied","Applied","Approved","Received"].index(project.get("subsidy_status","Not Applied") or "Not Applied"))
                new_sub_app = st.text_input("Subsidy Application No.", value=project.get("subsidy_application_no","") or "")
                new_gen     = st.text_input("Estimated Generation",    value=project.get("estimated_generation","") or "")
                if st.form_submit_button("Save"):
                    supabase.table("projects").update({
                        "msedcl_application_no":  new_msedcl,
                        "net_metering_status":     new_nm,
                        "subsidy_status":          new_sub_st,
                        "subsidy_application_no":  new_sub_app,
                        "estimated_generation":    new_gen,
                    }).eq("id", project["id"]).execute()
                    st.success("✅ Saved!")
                    st.rerun()

    with bc2:
        st.markdown("**DOCUMENTS CHECKLIST**")
        html = '<div style="background:#1e293b;border-radius:10px;padding:14px">'
        for doc in docs:
            uploaded = doc.get("status") == "uploaded"
            icon  = "✅" if uploaded else "⏳"
            color = "#22c55e" if uploaded else "#f59e0b"
            html += f"""
            <div style="display:flex;justify-content:space-between;padding:5px 0;
                        border-bottom:1px solid #334155">
              <span style="color:#cbd5e1;font-size:0.8rem">{icon} {doc.get('doc_name','')}</span>
              <span style="color:{color};font-size:0.76rem;font-weight:600">
                {'Uploaded' if uploaded else 'Pending'}</span>
            </div>"""
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

        with st.expander("✏️ Update Documents"):
            for doc in docs:
                dc1, dc2 = st.columns([2, 1])
                with dc1:
                    st.markdown(f"<span style='font-size:0.82rem'>{doc.get('doc_name','')}</span>", unsafe_allow_html=True)
                with dc2:
                    cur = doc.get("status", "pending")
                    new_s = st.selectbox("", ["pending","uploaded"],
                                index=0 if cur == "pending" else 1,
                                key=f"doc_{doc['id']}", label_visibility="collapsed")
                if new_s != cur:
                    supabase.table("project_documents").update({"status": new_s}).eq("id", doc["id"]).execute()
                    log_activity(supabase, f"Updated document '{doc.get('doc_name','')}' → {new_s}",
                                 entity_type="document",
                                 project_id=project["id"],
                                 project_name=project.get("customer_name"))
                    st.rerun()

    with bc3:
        st.markdown("**QUICK NOTES**")
        if notes:
            latest = notes[0]
            st.markdown(f"""
            <div style="background:#1e293b;border-radius:10px;padding:14px;min-height:80px">
              <div style="font-size:0.82rem;color:#cbd5e1;line-height:1.6">{latest.get('note','')}</div>
            </div>""", unsafe_allow_html=True)
            if latest.get("next_action"):
                st.markdown(f"""
                <div style="background:#1e293b;border-radius:10px;padding:12px;margin-top:8px;
                            border-left:3px solid #f59e0b">
                  <div style="color:#64748b;font-size:0.7rem;text-transform:uppercase;margin-bottom:4px">Next Action</div>
                  <div style="font-size:0.82rem;color:#f59e0b">{latest.get('next_action','')}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div style="background:#1e293b;border-radius:10px;padding:14px;color:#475569;font-size:0.82rem">No notes yet.</div>', unsafe_allow_html=True)

        with st.expander("➕ Add Note"):
            with st.form("add_note_form"):
                note_txt   = st.text_area("Note", key="note_txt")
                action_txt = st.text_input("Next Action", key="action_txt")
                if st.form_submit_button("Save Note"):
                    if note_txt.strip():
                        supabase.table("project_notes").insert({
                            "project_id": project["id"],
                            "note":        note_txt.strip(),
                            "next_action": action_txt.strip(),
                        }).execute()
                        log_activity(supabase, "Added note",
                                     entity_type="note",
                                     project_id=project["id"],
                                     project_name=project.get("customer_name"),
                                     details=note_txt.strip()[:150])
                        st.success("✅ Note saved!")
                        st.rerun()
