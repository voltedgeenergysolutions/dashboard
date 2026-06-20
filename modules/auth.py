"""Authentication Module - Google OAuth + Role-based access"""

import os
import urllib.parse
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI         = os.getenv("REDIRECT_URI", "http://localhost:8501")
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

ADMIN_EMAIL = "voltedgeenergysolutions011@gmail.com"



def init_auth():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated  = False
        st.session_state.user_email     = None
        st.session_state.user_name      = None
        st.session_state.user_picture   = None
        st.session_state.user_role      = "employee"
        st.session_state.user_status    = None
        st.session_state.selected_project_id = None


def get_login_url():
    import secrets
    state = secrets.token_urlsafe(32)
    st.session_state.oauth_state = state
    # Build URL manually — no PKCE, no google_auth_oauthlib, works on any server
    params = urllib.parse.urlencode({
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         "openid email profile",
        "access_type":   "offline",
        "prompt":        "select_account",
        "state":         state,
    })
    return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"


def handle_oauth_callback():
    """Exchange Google code for user info. Returns True if just authenticated."""
    params = st.query_params
    if "code" not in params:
        return False

    try:
        import requests as http
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        code = params.get("code", "")

        # Direct token exchange — no PKCE, no session state needed.
        # google_auth_oauthlib stores code_verifier in the Flow object which
        # is lost on Render restarts, causing "Missing code verifier" error.
        resp = http.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code":          code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  REDIRECT_URI,
                "grant_type":    "authorization_code",
            },
            timeout=10,
        )
        tokens = resp.json()

        if "error" in tokens:
            raise Exception(f"{tokens['error']}: {tokens.get('error_description', '')}")

        id_info = id_token.verify_oauth2_token(
            tokens["id_token"],
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=10,
        )

        st.session_state.authenticated = True
        st.session_state.user_email    = id_info.get("email", "")
        st.session_state.user_name     = id_info.get("name",  id_info.get("email", ""))
        st.session_state.user_picture  = id_info.get("picture", "")
        st.session_state.user_role     = "employee"
        st.session_state.user_status   = "pending"

        st.query_params.clear()
        return True

    except Exception as e:
        st.query_params.clear()
        st.error(f"❌ Google login failed: {e}")
        return False


def load_user_from_db(supabase):
    """
    Check app_users table for the logged-in email.
    - Not found  → insert as pending employee
    - Found      → load role + status into session_state
    Returns the user row dict or None.
    """
    email = st.session_state.get("user_email")
    if not email:
        return None

    try:
        rows = supabase.table("app_users").select("*").eq("email", email).execute().data
        if rows:
            user = rows[0]
        else:
            # New user — insert as pending employee
            row = {
                "email":   email,
                "name":    st.session_state.get("user_name", ""),
                "picture": st.session_state.get("user_picture", ""),
                "role":    "employee",
                "status":  "pending",
            }
            result = supabase.table("app_users").insert(row).execute().data
            user = result[0] if result else row

        # Assign a sequential employee code (VE-001, VE-002, …) if missing
        if not user.get("employee_code"):
            try:
                allc = supabase.table("app_users").select("employee_code").execute().data or []
                nums = []
                for r in allc:
                    c = (r.get("employee_code") or "").strip()
                    if c.upper().startswith("VE-") and c[3:].isdigit():
                        nums.append(int(c[3:]))
                code = f"VE-{(max(nums) + 1) if nums else 1:03d}"
                if user.get("id"):
                    supabase.table("app_users").update({"employee_code": code}).eq("id", user["id"]).execute()
                user["employee_code"] = code
            except Exception:
                # Column may not exist yet — fall back to an id-derived code
                user["employee_code"] = "VE-" + (str(user.get("id"))[:3].upper() if user.get("id") else "001")

        st.session_state.user_role   = user.get("role",   "employee")
        st.session_state.user_status = user.get("status", "pending")
        st.session_state.user_code   = user.get("employee_code", "VE-001")
        return user

    except Exception as e:
        st.error(f"❌ Could not load user profile: {e}")
        return None


def login_form():
    login_url = get_login_url()
    st.link_button("🔐 Sign in with Google", url=login_url, use_container_width=True)


def logout():
    for key in ["authenticated","user_email","user_name","user_picture",
                "user_role","user_status","oauth_state","selected_project_id"]:
        st.session_state.pop(key, None)
    st.rerun()


def check_authentication():
    if not st.session_state.get("authenticated", False):
        st.error("❌ Please log in first")
        st.stop()


def is_admin():
    return st.session_state.get("user_role") == "admin"


def check_role(required_role):
    allowed = {"admin": ["admin"], "employee": ["admin","employee"]}
    if st.session_state.get("user_role","employee") not in allowed.get(required_role, []):
        st.error(f"❌ Access denied.")
        st.stop()
