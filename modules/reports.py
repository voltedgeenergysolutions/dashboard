"""Admin Reports & Analytics — financials, pipeline, subsidy, partner & GST."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from collections import defaultdict
from .utils import format_currency

CARD = "background:#0d1a2e;border:1px solid #16304d;border-radius:12px;padding:16px 18px;margin-bottom:10px"


def _kpi(label, value, sub="", color="#f1f5f9"):
    return (f"<div style='{CARD}'>"
            f"<div style='color:#64748b;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.5px'>{label}</div>"
            f"<div style='font-size:1.45rem;font-weight:800;color:{color};margin-top:4px'>{value}</div>"
            f"<div style='color:#64748b;font-size:0.7rem'>{sub}</div></div>")


def _style(fig, h=300, legend=True):
    fig.update_layout(height=h, margin=dict(t=10, b=40, l=10, r=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font_color="#cbd5e1", showlegend=legend,
                      xaxis=dict(gridcolor="#16304d"), yaxis=dict(gridcolor="#16304d"),
                      legend=dict(bgcolor="rgba(0,0,0,0)", font_size=11))
    return fig


def render_reports(supabase, projects, df):
    st.markdown("#### 📊 Admin Reports & Analytics")
    st.caption("Company-wide financials, pipeline, subsidies and execution-partner performance.")

    if not projects:
        st.info("No project data yet.")
        return

    # ── aggregates ────────────────────────────────────────────────
    total       = len(projects)
    total_cost  = sum(float(p.get("total_cost", 0) or 0) for p in projects)
    total_paid  = sum(float(p.get("amount_paid", 0) or 0) for p in projects)
    balance     = sum(float(p.get("balance", 0) or 0) for p in projects)
    coll_rate   = round(total_paid / total_cost * 100, 1) if total_cost else 0
    active      = sum(1 for p in projects if p.get("project_status") in ("in_progress", "planning", "approved", "on_hold"))
    completed   = sum(1 for p in projects if p.get("project_status") == "completed")

    sub_expected = sum(float(p.get("subsidy_amount", 0) or 0) for p in projects)
    sub_disb_amt = sum(float(p.get("subsidy_amount", 0) or 0) for p in projects if (p.get("subsidy_status") or "").lower() == "disbursed")
    sub_pend_amt = sub_expected - sub_disb_amt
    sub_disb_cnt = sum(1 for p in projects if (p.get("subsidy_status") or "").lower() == "disbursed")
    sub_pend_cnt = sum(1 for p in projects if float(p.get("subsidy_amount", 0) or 0) > 0 and (p.get("subsidy_status") or "").lower() != "disbursed")

    # ── KPI cards ─────────────────────────────────────────────────
    k = st.columns(4)
    k[0].markdown(_kpi("Total Project Value", format_currency(total_cost), f"{total} projects", "#3b82f6"), unsafe_allow_html=True)
    k[1].markdown(_kpi("Amount Received", format_currency(total_paid), f"Collection {coll_rate}%", "#22c55e"), unsafe_allow_html=True)
    k[2].markdown(_kpi("Outstanding Due", format_currency(balance), "to be collected", "#ef4444"), unsafe_allow_html=True)
    k[3].markdown(_kpi("Avg Project Value", format_currency(total_cost / total if total else 0), "per project", "#a78bfa"), unsafe_allow_html=True)

    k2 = st.columns(4)
    k2[0].markdown(_kpi("Active Projects", active, "in pipeline", "#3b82f6"), unsafe_allow_html=True)
    k2[1].markdown(_kpi("Completed", completed, f"{round(completed/total*100,1) if total else 0}% of all", "#22c55e"), unsafe_allow_html=True)
    k2[2].markdown(_kpi("Subsidy Disbursed", format_currency(sub_disb_amt), f"{sub_disb_cnt} projects", "#22c55e"), unsafe_allow_html=True)
    k2[3].markdown(_kpi("Subsidy Pending", format_currency(sub_pend_amt), f"{sub_pend_cnt} projects", "#f59e0b"), unsafe_allow_html=True)

    # ── Execution partner performance ─────────────────────────────
    with st.container(border=True, key="rpt_partner"):
        st.markdown("**Execution Partner Performance**")
        pa = defaultdict(lambda: {"count": 0, "value": 0.0, "recv": 0.0})
        for p in projects:
            ep = p.get("execution_partner") or "—"
            pa[ep]["count"] += 1
            pa[ep]["value"] += float(p.get("total_cost", 0) or 0)
            pa[ep]["recv"]  += float(p.get("amount_paid", 0) or 0)
        eps = list(pa.keys())
        pc1, pc2 = st.columns(2)
        with pc1:
            fig = go.Figure(go.Bar(x=eps, y=[pa[e]["count"] for e in eps], marker_color="#8b5cf6",
                                   text=[pa[e]["count"] for e in eps], textposition="outside"))
            fig.update_layout(title=dict(text="Projects per Partner", font=dict(size=12, color="#94a3b8")))
            st.plotly_chart(_style(fig, 260, legend=False), use_container_width=True, key="rpt_partner_cnt")
        with pc2:
            fig = go.Figure()
            fig.add_trace(go.Bar(name="Value",    x=eps, y=[pa[e]["value"] for e in eps], marker_color="#3b82f6"))
            fig.add_trace(go.Bar(name="Received", x=eps, y=[pa[e]["recv"] for e in eps],  marker_color="#22c55e"))
            fig.update_layout(barmode="group", title=dict(text="Value per Partner", font=dict(size=12, color="#94a3b8")))
            st.plotly_chart(_style(fig, 260), use_container_width=True, key="rpt_partner_val")

    # ── Monthly trend ─────────────────────────────────────────────
    with st.container(border=True, key="rpt_month"):
        st.markdown("**Monthly — New Projects & Collections**")
        new_by_month = defaultdict(int)
        for p in projects:
            m = str(p.get("created_at") or "")[:7]
            if m:
                new_by_month[m] += 1
        try:
            insts = supabase.table("installments").select("amount,due_date,status").execute().data or []
        except Exception:
            insts = []
        coll_by_month = defaultdict(float)
        for i in insts:
            if (i.get("status") == "paid") and i.get("due_date"):
                coll_by_month[str(i["due_date"])[:7]] += float(i.get("amount", 0) or 0)
        months = sorted(set(list(new_by_month) + list(coll_by_month)))[-12:]
        if months:
            mc1, mc2 = st.columns(2)
            with mc1:
                fig = go.Figure(go.Bar(x=months, y=[new_by_month.get(m, 0) for m in months],
                                       marker_color="#3b82f6", text=[new_by_month.get(m, 0) for m in months], textposition="outside"))
                fig.update_layout(title=dict(text="New Projects / month", font=dict(size=12, color="#94a3b8")))
                st.plotly_chart(_style(fig, 250, legend=False), use_container_width=True, key="rpt_new_month")
            with mc2:
                fig = go.Figure(go.Bar(x=months, y=[coll_by_month.get(m, 0) for m in months], marker_color="#22c55e"))
                fig.update_layout(title=dict(text="Collections / month (₹)", font=dict(size=12, color="#94a3b8")))
                st.plotly_chart(_style(fig, 250, legend=False), use_container_width=True, key="rpt_coll_month")
        else:
            st.caption("Not enough dated data for monthly trends yet.")

    # ── Pipeline by current stage ─────────────────────────────────
    with st.container(border=True, key="rpt_pipeline"):
        st.markdown("**Pipeline — Projects by Current Stage**")
        try:
            steps = supabase.table("project_steps").select("project_id,step_no,step_name,status").execute().data or []
        except Exception:
            steps = []
        by_proj = defaultdict(list)
        for s in steps:
            by_proj[s.get("project_id")].append(s)
        proj_ids = {p["id"] for p in projects}
        stage_count = defaultdict(int)
        for pid_, slist in by_proj.items():
            if pid_ not in proj_ids:
                continue
            slist.sort(key=lambda x: x.get("step_no", 0))
            cur = next((s for s in slist if s.get("status") == "in_progress"), None) \
                or next((s for s in slist if s.get("status") == "pending"), None)
            stage_count[cur.get("step_name", "—") if cur else "✅ Completed"] += 1
        if stage_count:
            labels = list(stage_count.keys())
            fig = go.Figure(go.Bar(y=labels, x=[stage_count[l] for l in labels], orientation="h",
                                   marker_color="#f59e0b", text=[stage_count[l] for l in labels], textposition="outside"))
            st.plotly_chart(_style(fig, max(220, 36 * len(labels)), legend=False), use_container_width=True, key="rpt_pipeline_fig")
        else:
            st.caption("No workflow data yet.")

    # ── EPC GST summary ───────────────────────────────────────────
    with st.container(border=True, key="rpt_epc"):
        st.markdown("**EPC GST Summary**")
        try:
            epcs = supabase.table("epcs").select("*").execute().data or []
            etx  = supabase.table("epc_transactions").select("*").execute().data or []
        except Exception:
            epcs, etx = [], []
        rows = []
        for e in epcs:
            eid = e["id"]
            pg = sum(float(t.get("purchase_base", 0) or 0) * float(t.get("purchase_gst_pct", 0) or 0) / 100 for t in etx if t.get("epc_id") == eid)
            sg = sum(float(t.get("sale_base", 0) or 0) * float(t.get("sale_gst_pct", 0) or 0) / 100 for t in etx if t.get("epc_id") == eid)
            pend = sg - pg
            recv = float(e.get("gst_received", 0) or 0)
            rows.append({"EPC": e.get("name", "-"),
                         "Purchase GST": pg, "Sales GST": sg,
                         "GST Pending": pend, "Received": recv, "Balance": pend - recv})
        if rows:
            edf = pd.DataFrame(rows)
            show = edf.copy()
            for col in ("Purchase GST", "Sales GST", "GST Pending", "Received", "Balance"):
                show[col] = show[col].apply(lambda x: format_currency(float(x)))
            st.dataframe(show, use_container_width=True, hide_index=True)
        else:
            st.caption("No EPC data yet — add EPCs in the EPC Partners page.")

    # ── Financial summary by status + export ──────────────────────
    with st.container(border=True, key="rpt_table"):
        st.markdown("**Financial Summary by Status**")
        if "project_status" in df.columns:
            grp = df.groupby("project_status").agg(
                Count=("project_status", "count"),
                **{"Total Cost":  ("total_cost",  lambda x: x.fillna(0).sum())},
                **{"Amount Paid": ("amount_paid", lambda x: x.fillna(0).sum())},
                **{"Balance":     ("balance",     lambda x: x.fillna(0).sum())},
            ).reset_index()
            grp.rename(columns={"project_status": "Status"}, inplace=True)
            grp_show = grp.copy()
            for col in ("Total Cost", "Amount Paid", "Balance"):
                grp_show[col] = grp_show[col].apply(lambda x: format_currency(float(x)))
            st.dataframe(grp_show, use_container_width=True, hide_index=True)

        fin_cols = [c for c in ["customer_name", "project_code", "execution_partner", "system_size_kwp",
                                "project_status", "total_cost", "amount_paid", "balance",
                                "subsidy_amount", "subsidy_status"] if c in df.columns]
        if fin_cols:
            raw = df[fin_cols].copy()
            st.download_button("⬇️ Export Full Project Report (CSV)",
                               raw.to_csv(index=False).encode("utf-8"),
                               "voltedge_admin_report.csv", "text/csv", use_container_width=True)
