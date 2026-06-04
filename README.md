# VOLTEDGE Streamlit Dashboard - Setup Guide

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip (Python package manager)

### Installation

1. **Navigate to Streamlit app directory**
```bash
cd streamlit_app
```

2. **Create Python virtual environment** (optional but recommended)
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# or source venv/bin/activate  # Mac/Linux
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure .env file**
```bash
# Copy .env file (already configured with your Supabase credentials)
# The SUPABASE_URL and SUPABASE_ANON_KEY are already set
```

5. **Run Streamlit app**
```bash
streamlit run Home.py
```

The app will open at: **http://localhost:8501**

---

## 📁 Project Structure

```
streamlit_app/
├── Home.py                  # Main homepage & login
├── pages/
│   ├── 1_💼_Dashboard.py   # Projects list & create
│   ├── 2_📊_Analytics.py   # Financial analytics & charts
│   ├── 3_👥_Users.py       # User management
│   └── 4_📄_Reports.py     # Reports & export
├── modules/
│   ├── supabase_client.py  # Database operations
│   ├── auth.py             # Authentication
│   └── utils.py            # Utility functions
├── requirements.txt         # Python dependencies
└── .streamlit/
    └── config.toml         # Streamlit theme config
```

---

## ✨ Features

✅ **Dashboard** - View all solar projects
✅ **Analytics** - Financial analysis with charts
✅ **Reports** - Generate and export reports
✅ **User Management** - User role control (coming soon)
✅ **Real-time** - Live data from Supabase
✅ **Modular** - Easy to extend and maintain

---

## 🔐 Login

Default login (for demo):
- **Email:** any email
- **Password:** any password

Note: Full Supabase Auth integration coming soon!

---

## 📊 Using the Dashboard

### 1. Dashboard Tab
- View all projects
- Filter by status
- Create new projects
- Edit project details

### 2. Analytics Tab
- View financial summary
- See payment progress
- Charts by status
- Top customers analysis

### 3. Reports Tab
- Generate summary reports
- Export as CSV
- Financial analysis
- Payment status reports

---

## 🚀 Deployment to Streamlit Cloud

1. **Push code to GitHub**
```bash
git init
git add .
git commit -m "Initial commit"
git push origin main
```

2. **Deploy on Streamlit Cloud**
- Go to https://streamlit.io/cloud
- Connect your GitHub repository
- Select branch and app file (Home.py)
- Click "Deploy"

3. **Add Secrets** in Streamlit Cloud
- Go to app settings
- Add secrets:
  ```
  SUPABASE_URL = "..."
  SUPABASE_ANON_KEY = "..."
  ```

---

## 🔧 Troubleshooting

### Issue: "Module not found"
**Solution:** Ensure you're in the correct directory and have installed requirements:
```bash
pip install -r requirements.txt
```

### Issue: "Supabase credentials not set"
**Solution:** Check .env file has correct values:
```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=xxxxx
```

### Issue: "Page not loading"
**Solution:** Check database schema is initialized in Supabase

---

## 📚 Key Dependencies

- **streamlit** - Web framework
- **supabase** - Database client
- **pandas** - Data manipulation
- **plotly** - Interactive charts
- **python-dotenv** - Environment variables

---

## 🎯 Next Steps

1. Test the dashboard locally
2. Create sample projects
3. Verify all features work
4. Deploy to Streamlit Cloud
5. Share link with your team

---

## ✉️ Support

For issues or questions:
1. Check logs in terminal
2. Review Streamlit documentation
3. Check Supabase dashboard

Enjoy your VOLTEDGE Dashboard! 🌟
