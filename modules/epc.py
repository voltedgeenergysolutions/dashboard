"""EPC Partners — admin page for fund & GST tracking between Voltedge and EPCs.

Not linked to customer money. System amount is pulled live from project details
(amount received on projects whose execution partner is this EPC); everything else
is entered here.
"""

import streamlit as st
import pandas as pd
from .utils import format_currency
from .supabase_client import log_activity

CARD = "background:#0d1a2e;border:1px solid #16304d;border-radius:12px;padding:16px 18px;margin-bottom:10px"
GST_OPTS = [0, 5, 12, 18, 28]


def _epcs(supabase):
    try:
        return supabase.table("epcs").select("*").order("name").execute().data or []
    except Exception as e:
        st.error(f"Could not load EPCs — run the EPC migration (003_epc_tables.sql). {e}")
        return []


def _txns(supabase, epc_id):
    try:
        return supabase.table("epc_transactions").select("*").eq("epc_id", epc_id).order("created_at").execute().data or []
    except Exception:
        return []


def _kv(label, value, vcolor="#f1f5f9"):
    return (f"<div style='margin-bottom:10px'>"
            f"<div style='color:#64748b;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.5px'>{label}</div>"
            f"<div style='color:{vcolor};font-size:1.05rem;font-weight:700;margin-top:2px'>{value}</div></div>")


def render_epc_page(supabase, projects):
    st.markdown("#### 🏭 EPC Partners — Funds & GST")
    st.caption("Internal accounting between Voltedge and execution partners (EPCs). Not linked to customer payments.")

    epcs = _epcs(supabase)
    # Ensure our own "Voltedge" is always available as a selectable partner
    if epcs is not None and not any((e.get("name") or "").lower() == "voltedge" for e in epcs):
        try:
            supabase.table("epcs").insert({"name": "Voltedge", "personal_amount": 0, "gst_received": 0}).execute()
            epcs = _epcs(supabase)
        except Exception:
            pass
    names = [e["name"] for e in epcs]

    # ── Top: select EPC  |  Add New EPC ───────────────────────────
    c1, c2 = st.columns([2, 1])
    with c1:
        sel_name = st.selectbox("🔍 Search / Select EPC", ["— Select EPC —"] + names, key="epc_sel")
    with c2:
        with st.expander("➕ Add New EPC"):
            with st.form("add_epc_form", clear_on_submit=True):
                n  = st.text_input("Name *")
                m  = st.text_input("Mobile")
                em = st.text_input("Email")
                ad = st.text_input("Address")
                aa = st.text_input("Aadhar Card")
                st.caption("Initial amount starts at 0.")
                if st.form_submit_button("➕ Add EPC", use_container_width=True):
                    if n.strip():
                        supabase.table("epcs").insert({
                            "name": n.strip(), "mobile": m, "email": em, "address": ad, "aadhar": aa,
                            "personal_amount": 0, "gst_received": 0,
                        }).execute()
                        log_activity(supabase, f"Added EPC: {n.strip()}", entity_type="user")
                        st.toast("✅ EPC added!", icon="✅"); st.rerun()
                    else:
                        st.error("Name is required.")

    epc = next((x for x in epcs if x["name"] == sel_name), None)
    if not epc:
        st.info("Select an EPC above to view its funds, GST and transactions — or add a new one.")
        return

    epc_id = epc["id"]
    txns   = _txns(supabase, epc_id)
    # group materials by customer (same customer's rows sit together)
    txns   = sorted(txns, key=lambda t: ((t.get("customer_name") or "").lower(), str(t.get("created_at") or "")))

    # customers belonging to THIS EPC: from its projects + anything already in its ledger
    epc_customers = sorted(set(
        [p.get("customer_name") for p in projects
         if (p.get("execution_partner") or "") == epc["name"] and p.get("customer_name")]
        + [t.get("customer_name") for t in txns if t.get("customer_name")]
    ))

    # ── computations ──────────────────────────────────────────────
    system_credited = sum(float(p.get("amount_paid", 0) or 0) for p in projects
                          if (p.get("execution_partner") or "") == epc["name"])
    personal    = float(epc.get("personal_amount", 0) or 0)
    total_funds = system_credited + personal

    purchase_gst_total = sum(float(t.get("purchase_base", 0) or 0) * float(t.get("purchase_gst_pct", 0) or 0) / 100 for t in txns)
    sale_gst_total     = sum(float(t.get("sale_base", 0) or 0) * float(t.get("sale_gst_pct", 0) or 0) / 100 for t in txns)
    gst_pending  = sale_gst_total - purchase_gst_total
    gst_received = float(epc.get("gst_received", 0) or 0)
    epc_balance  = gst_pending - gst_received

    # ── Fund details | GST details ────────────────────────────────
    fc, gc = st.columns(2)
    with fc:
        st.markdown(
            f"<div style='{CARD}'>"
            f"<div style='font-weight:700;color:#e2e8f0;margin-bottom:12px'>💰 FUND DETAILS</div>"
            + _kv("Total System Amount Credited (live)", format_currency(system_credited), "#3b82f6")
            + _kv("Total Personal Amount (from EPC)", format_currency(personal), "#a78bfa")
            + "<div style='border-top:1px solid #16304d;margin:6px 0 8px'></div>"
            + _kv("Total Funds Available", format_currency(total_funds), "#22c55e")
            + "</div>", unsafe_allow_html=True)
    with gc:
        _bal_clr = "#ef4444" if epc_balance > 0 else "#22c55e"
        st.markdown(
            f"<div style='{CARD}'>"
            f"<div style='font-weight:700;color:#e2e8f0;margin-bottom:12px'>🧾 GST DETAILS</div>"
            + _kv("GST Pending (Sales GST − Purchase GST)", format_currency(gst_pending), "#f59e0b")
            + _kv("Total GST Received", format_currency(gst_received), "#22c55e")
            + "<div style='border-top:1px solid #16304d;margin:6px 0 8px'></div>"
            + _kv("EPC Balance (Pending − Received)", format_currency(epc_balance), _bal_clr)
            + "</div>", unsafe_allow_html=True)

    # ── Edit / Delete EPC ─────────────────────────────────────────
    with st.expander("✏️ Edit EPC details / funds"):
        with st.form("edit_epc_form"):
            ec1, ec2 = st.columns(2)
            with ec1:
                e_personal = st.number_input("Total Personal Amount (₹)", min_value=0.0, step=1000.0,
                                             value=float(epc.get("personal_amount", 0) or 0))
                e_gstrecv  = st.number_input("Total GST Received (₹)", min_value=0.0, step=1000.0,
                                             value=float(epc.get("gst_received", 0) or 0))
                e_mob = st.text_input("Mobile", value=epc.get("mobile", "") or "")
            with ec2:
                e_mail = st.text_input("Email", value=epc.get("email", "") or "")
                e_addr = st.text_input("Address", value=epc.get("address", "") or "")
                e_aad  = st.text_input("Aadhar Card", value=epc.get("aadhar", "") or "")
            if st.form_submit_button("💾 Save EPC"):
                supabase.table("epcs").update({
                    "personal_amount": e_personal, "gst_received": e_gstrecv,
                    "mobile": e_mob, "email": e_mail, "address": e_addr, "aadhar": e_aad,
                }).eq("id", epc_id).execute()
                log_activity(supabase, f"Updated EPC: {epc['name']}", entity_type="user")
                st.toast("✅ Saved!", icon="✅"); st.rerun()
        st.markdown("<div style='color:#64748b;font-size:0.72rem;margin-top:6px'>Danger zone</div>", unsafe_allow_html=True)
        if st.button("🗑️ Delete this EPC", key="del_epc"):
            supabase.table("epcs").delete().eq("id", epc_id).execute()
            log_activity(supabase, f"Deleted EPC: {epc['name']}", entity_type="user")
            st.session_state.epc_sel = "— Select EPC —"
            st.toast("🗑️ EPC deleted.", icon="🗑️"); st.rerun()

    # ── Transactions table ────────────────────────────────────────
    st.markdown(f"<div style='font-weight:700;color:#e2e8f0;margin:6px 0 6px'>📒 PURCHASE / SALE LEDGER — {epc['name']}</div>", unsafe_allow_html=True)

    rows = []
    for t in txns:
        pb = float(t.get("purchase_base", 0) or 0); pp = float(t.get("purchase_gst_pct", 0) or 0)
        sb = float(t.get("sale_base", 0) or 0);     sp = float(t.get("sale_gst_pct", 0) or 0)
        p_gst = pb * pp / 100; tot_p = pb + p_gst
        s_gst = sb * sp / 100; tot_s = sb + s_gst
        rows.append({
            "Customer": t.get("customer_name", ""),
            "Purchase Material": t.get("purchase_material", ""),
            "Purchase Base": pb, "P.GST %": pp, "Purchase GST": p_gst, "Total Purchase": tot_p,
            "Sale Material": t.get("sale_material", ""),
            "Sale Base": sb, "S.GST %": sp, "Sale GST": s_gst, "Total Sale": tot_s,
        })

    if rows:
        tdf = pd.DataFrame(rows)
        show = tdf.copy()
        for col in ("Purchase Base", "Purchase GST", "Total Purchase", "Sale Base", "Sale GST", "Total Sale"):
            show[col] = show[col].apply(lambda x: format_currency(float(x)))
        st.dataframe(show, use_container_width=True, hide_index=True)
        # totals row
        st.markdown(
            f"<div style='color:#94a3b8;font-size:0.8rem;margin:4px 2px'>"
            f"Totals — Purchase GST: <b style='color:#cbd5e1'>{format_currency(purchase_gst_total)}</b> · "
            f"Sales GST: <b style='color:#cbd5e1'>{format_currency(sale_gst_total)}</b> · "
            f"GST Pending: <b style='color:#f59e0b'>{format_currency(gst_pending)}</b></div>",
            unsafe_allow_html=True)
        _summary = (
            "\n\nGST DETAILS\n"
            f"Purchase GST Total,{purchase_gst_total:.2f}\n"
            f"Sales GST Total,{sale_gst_total:.2f}\n"
            f"GST Pending (Sales GST - Purchase GST),{gst_pending:.2f}\n"
            f"Total GST Received,{gst_received:.2f}\n"
            f"EPC Balance (Pending - Received),{epc_balance:.2f}\n"
            "\nFUND DETAILS\n"
            f"Total System Amount Credited (live),{system_credited:.2f}\n"
            f"Total Personal Amount (from EPC),{personal:.2f}\n"
            f"Total Funds Available,{total_funds:.2f}\n"
        )
        _csv = tdf.to_csv(index=False) + _summary
        st.download_button("⬇️ Export Ledger + Summary (CSV)", _csv.encode("utf-8"),
                           f"epc_{epc['name']}_ledger.csv", "text/csv")
    else:
        st.info("No transactions yet. Add the first purchase/sale entry below.")

    # ── Add transaction ───────────────────────────────────────────
    with st.expander("➕ Add Purchase / Sale Entry"):
        st.caption("Pick an existing customer of this EPC (suggested) or type a new one. "
                   "Add multiple materials by submitting one entry per material under the same customer.")
        with st.form("add_txn_form", clear_on_submit=True):
            try:
                t_cust = st.selectbox("Customer Name", epc_customers, index=None,
                                      placeholder="Select or type a customer…",
                                      accept_new_options=True, key="t_cust")
            except TypeError:
                # older Streamlit without accept_new_options — fall back to text input
                t_cust = st.text_input("Customer Name", key="t_cust_txt")
            t_cust = t_cust or ""
            st.markdown("**Purchase (Voltedge buys)**")
            p1, p2, p3 = st.columns(3)
            with p1: t_pmat = st.text_input("Purchase Material", key="t_pmat")
            with p2: t_pbase = st.number_input("Purchase Base (₹)", min_value=0.0, step=1000.0, value=None, placeholder="0", key="t_pbase") or 0.0
            with p3: t_ppct = st.selectbox("Purchase GST %", GST_OPTS, index=1, key="t_ppct")
            st.markdown("**Sale (Voltedge sells to EPC)**")
            s1, s2, s3 = st.columns(3)
            with s1: t_smat = st.text_input("Sale Material", key="t_smat")
            with s2: t_sbase = st.number_input("Sale Base (₹)", min_value=0.0, step=1000.0, value=None, placeholder="0", key="t_sbase") or 0.0
            with s3: t_spct = st.selectbox("Sale GST %", GST_OPTS, index=1, key="t_spct")
            # live preview
            _pg = t_pbase * t_ppct / 100; _sg = t_sbase * t_spct / 100
            st.caption(f"Total Purchase {format_currency(t_pbase + _pg)}  ·  Total Sale {format_currency(t_sbase + _sg)}  ·  GST diff {format_currency(_sg - _pg)}")
            if st.form_submit_button("➕ Add Entry", use_container_width=True):
                supabase.table("epc_transactions").insert({
                    "epc_id": epc_id, "customer_name": t_cust,
                    "purchase_material": t_pmat, "purchase_base": t_pbase, "purchase_gst_pct": t_ppct,
                    "sale_material": t_smat, "sale_base": t_sbase, "sale_gst_pct": t_spct,
                }).execute()
                log_activity(supabase, f"EPC entry added ({epc['name']})", entity_type="installment",
                             details=f"Purchase {format_currency(t_pbase)} / Sale {format_currency(t_sbase)}")
                st.toast("✅ Entry added!", icon="✅"); st.rerun()

    # ── Delete a transaction ──────────────────────────────────────
    if txns:
        with st.expander("🗑️ Delete a Material / Entry"):
            opt = {f"{i+1}. {t.get('customer_name','-')} · {t.get('purchase_material') or t.get('sale_material') or 'material'} "
                   f"· buy {format_currency(float(t.get('purchase_base',0) or 0))} / sell {format_currency(float(t.get('sale_base',0) or 0))}": t["id"]
                   for i, t in enumerate(txns)}
            pick = st.selectbox("Entry", list(opt.keys()), key="epc_del_txn")
            if st.button("🗑️ Delete Entry", key="epc_del_txn_btn"):
                supabase.table("epc_transactions").delete().eq("id", opt[pick]).execute()
                st.toast("🗑️ Entry deleted.", icon="🗑️"); st.rerun()
