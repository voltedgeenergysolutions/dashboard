"""Utility Functions Module"""

import pandas as pd
import datetime
import pytz

def format_currency(value):
    """Format value as Indian currency"""
    return f"₹{value:,.2f}"

def format_percentage(value):
    """Format value as percentage"""
    return f"{value:.1f}%"

def get_status_color(status):
    """Get color for project status"""
    colors = {
        "completed": "✅ Completed",
        "in_progress": "🔄 In Progress",
        "planning": "📋 Planning",
        "approved": "✔️ Approved",
        "on_hold": "⏸️ On Hold",
    }
    return colors.get(status, status)

def get_status_badge_color(status):
    """Get badge color for Streamlit"""
    color_map = {
        "completed": "green",
        "in_progress": "blue",
        "planning": "gray",
        "approved": "orange",
        "on_hold": "red",
    }
    return color_map.get(status, "gray")

def calculate_completion_percentage(completed, total):
    """Calculate completion percentage"""
    if total == 0:
        return 0
    return (completed / total) * 100

def convert_to_dataframe(data):
    """Convert list of dicts to DataFrame"""
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)

def get_date_string(date_obj):
    """Format date to string"""
    if isinstance(date_obj, str):
        return date_obj
    return date_obj.strftime("%Y-%m-%d") if date_obj else "N/A"

def get_year_month():
    """Get current year and month"""
    now = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    return now.year, now.month

def get_month_name(month):
    """Get month name from number"""
    months = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]
    return months[month - 1] if 1 <= month <= 12 else "Unknown"
