"""Supabase Client Module"""

import streamlit as st
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()


@st.cache_resource
def get_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        st.error("❌ Supabase credentials not configured!")
        st.stop()
    return create_client(url, key)


# ── Activity Logging ──────────────────────────────────────────────────────────

def log_activity(supabase, action, entity_type=None, project_id=None, project_name=None, details=None):
    """Record an activity log entry. Never raises — logging must not break the app."""
    try:
        supabase.table("activity_logs").insert({
            "user_email":   st.session_state.get("user_email", ""),
            "user_name":    st.session_state.get("user_name",  ""),
            "user_picture": st.session_state.get("user_picture", ""),
            "action":       action,
            "entity_type":  entity_type,
            "project_id":   str(project_id) if project_id else None,
            "project_name": project_name,
            "details":      details,
        }).execute()
    except Exception:
        pass


def get_activity_logs(supabase, limit=50, user_email=None):
    try:
        q = supabase.table("activity_logs").select("*").order("created_at", desc=True).limit(limit)
        if user_email:
            q = q.eq("user_email", user_email)
        return q.execute().data or []
    except Exception as e:
        return []


# ── Projects ─────────────────────────────────────────────────────────────────

def get_projects(supabase):
    try:
        return supabase.table("projects").select("*").order("created_at", desc=True).execute().data or []
    except Exception as e:
        st.error(f"Error fetching projects: {e}")
        return []


def get_project_by_id(supabase, project_id):
    try:
        rows = supabase.table("projects").select("*").eq("id", project_id).execute().data
        return rows[0] if rows else None
    except Exception as e:
        st.error(f"Error fetching project: {e}")
        return None


def create_project(supabase, data):
    try:
        rows = supabase.table("projects").insert(data).execute().data
        result = rows[0] if rows else None
        if result:
            log_activity(supabase, "Created project",
                         entity_type="project",
                         project_id=result.get("id"),
                         project_name=result.get("customer_name"),
                         details=f"Status: {result.get('project_status')} | Size: {result.get('system_size_kwp')} kWp")
        return result
    except Exception as e:
        st.error(f"Error creating project: {e}")
        return None


def update_project(supabase, project_id, data):
    try:
        rows = supabase.table("projects").update(data).eq("id", project_id).execute().data
        result = rows[0] if rows else None
        if result:
            changed = ", ".join(f"{k}={v}" for k, v in data.items()
                                if k not in ("updated_at",))
            log_activity(supabase, "Updated project",
                         entity_type="project",
                         project_id=project_id,
                         project_name=result.get("customer_name"),
                         details=changed[:200])
        return result
    except Exception as e:
        st.error(f"Error updating project: {e}")
        return None


def get_dashboard_stats(supabase):
    try:
        projects = get_projects(supabase)
        return {
            "total_projects":  len(projects),
            "completed":       sum(1 for p in projects if p.get("project_status") == "completed"),
            "in_progress":     sum(1 for p in projects if p.get("project_status") == "in_progress"),
            "total_cost":      sum(float(p.get("total_cost",  0) or 0) for p in projects),
            "total_paid":      sum(float(p.get("amount_paid", 0) or 0) for p in projects),
            "pending_balance": sum(float(p.get("balance",     0) or 0) for p in projects),
        }
    except Exception as e:
        st.error(f"Error calculating stats: {e}")
        return None
