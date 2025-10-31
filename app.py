import os
import pandas as pd
from flask import Flask, render_template, jsonify, session
from flask_caching import Cache
from waitress import serve
import threading
import time
import json

app = Flask(__name__)
app.secret_key = "super_secret_key"  # Needed for session storage

# Cache configuration
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

DATA_FOLDER = os.path.join(os.path.dirname(__file__), "data")
DEFAULT_EXCEL_PATH = os.path.join(DATA_FOLDER, "Smart FM Defects through Python.xlsx")

# =============================
# Run defect extraction script
# =============================
def update_defects_excel():
    print("🔁 Running defectsextraction.py ...")
    os.system("python defectsextraction.py")
    print("✅ defectsextraction.py completed")
    return DEFAULT_EXCEL_PATH


# =============================
# Load Excel data
# =============================
def load_excel_data():
    try:
        excel_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".xlsx")]
        dfs = []
        for file in excel_files:
            path = os.path.join(DATA_FOLDER, file)
            df = pd.read_excel(path)
            df["SourceFile"] = file
            dfs.append(df)
        if dfs:
            data = pd.concat(dfs, ignore_index=True)
            print(f"✅ Loaded {len(data)} total defects from {len(excel_files)} Excel files")
            return data
        else:
            print("⚠️ No Excel files found in data folder.")
            return pd.DataFrame()
    except Exception as e:
        print(f"❌ Error loading Excel files: {e}")
        return pd.DataFrame()


# =============================
# Cache Excel data
# =============================
@cache.cached(timeout=300, key_prefix="defects_data")
def get_cached_data():
    return load_excel_data()


# =============================
# Background refresh every 5 mins
# =============================
def refresh_data_background():
    while True:
        try:
            print("🔄 Refreshing Excel data...")
            update_defects_excel()
            cache.delete("defects_data")
            get_cached_data()
            print("✅ Data cache refreshed")
        except Exception as e:
            print(f"⚠️ Refresh error: {e}")
        time.sleep(300)


# =============================
# Flask routes
# =============================
@app.route("/")
def dashboard():
    data = get_cached_data()
    session_filter = session.get("last_filter", None)

    if session_filter:
        filtered_data = data[data["Severity"].str.contains(session_filter, case=False, na=False)]
        table_data = filtered_data.to_dict(orient="records")
        print(f"🔍 Restored filter '{session_filter}' with {len(filtered_data)} records")
    else:
        table_data = data.to_dict(orient="records")

    return render_template("dashboard.html", defects=table_data, filter=session_filter)


@app.route("/filter/<severity>")
def filter_by_severity(severity):
    session["last_filter"] = severity
    data = get_cached_data()
    filtered_data = data[data["Severity"].str.contains(severity, case=False, na=False)]
    return jsonify(filtered_data.to_dict(orient="records"))


@app.route("/reset_filter")
def reset_filter():
    session.pop("last_filter", None)
    return jsonify({"message": "Filter reset"})


# =============================
# Start app
# =============================
if __name__ == "__main__":
    threading.Thread(target=refresh_data_background, daemon=True).start()
    print("🌐 Starting dashboard server on port 10000...")
    serve(app, host="0.0.0.0", port=10000)
