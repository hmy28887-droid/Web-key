from flask import Flask, request, jsonify, render_template_string, redirect, session
from datetime import datetime, timedelta
import sqlite3
import os
import uuid

app = Flask(__name__)
app.secret_key = "super_secret_admin_key"

DATABASE = "keys.db"

# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE,
            device_id TEXT,
            max_devices INTEGER,
            expiry_date TEXT,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ================= LOGIN =================

ADMIN_USER = "admin"
ADMIN_PASS = "hoangnam0804"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["admin"] = True
            return redirect("/")
        else:
            return "Sai tài khoản hoặc mật khẩu"
    return """
    <h2>Admin Login</h2>
    <form method="post">
        <input name="username" placeholder="Username"><br><br>
        <input name="password" type="password" placeholder="Password"><br><br>
        <button type="submit">Login</button>
    </form>
    """

def require_login():
    if "admin" not in session:
        return False
    return True

# ================= ADMIN PANEL =================

@app.route("/")
def home():
    if not require_login():
        return redirect("/login")

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM keys")
    keys = c.fetchall()
    conn.close()

    html = """
    <h2>Quản lý Key</h2>
    <a href='/create'>Tạo Key</a><br><br>
    <table border=1 cellpadding=5>
    <tr>
        <th>Key</th>
        <th>Thiết bị</th>
        <th>Hạn sử dụng</th>
        <th>Trạng thái</th>
        <th>Hành động</th>
    </tr>
    """

    for k in keys:
        expiry = "Không hết hạn" if k[4] == "never" else k[4]
        device_display = "0/1" if not k[2] else "1/1"

        html += f"""
        <tr>
            <td>{k[1]}</td>
            <td>{device_display}</td>
            <td>{expiry}</td>
            <td>{k[5]}</td>
            <td>
                <a href='/reset/{k[0]}'>🟡 Reset</a>
                <a href='/delete/{k[0]}'>🔴 Xóa</a>
            </td>
        </tr>
        """

    html += "</table>"
    return render_template_string(html)

# ================= CREATE KEY =================

@app.route("/create")
def create_key():
    if not require_login():
        return redirect("/login")

    new_key = str(uuid.uuid4()).replace("-", "")[:16].upper()
    expiry = "never"

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO keys (license_key, device_id, max_devices, expiry_date, status)
        VALUES (?, ?, ?, ?, ?)
    """, (new_key, "", 1, expiry, "active"))
    conn.commit()
    conn.close()

    return redirect("/")

# ================= DELETE KEY =================

@app.route("/delete/<int:key_id>")
def delete_key(key_id):
    if not require_login():
        return redirect("/login")

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("DELETE FROM keys WHERE id=?", (key_id,))
    conn.commit()
    conn.close()

    return redirect("/")

# ================= RESET DEVICE =================

@app.route("/reset/<int:key_id>")
def reset_device(key_id):
    if not require_login():
        return redirect("/login")

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("UPDATE keys SET device_id='' WHERE id=?", (key_id,))
    conn.commit()
    conn.close()

    return redirect("/")

# ================= VERIFY API =================

@app.route("/verify", methods=["POST"])
def verify():
    data = request.json
    key = data.get("key")
    device_id = data.get("device_id")

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM keys WHERE license_key=?", (key,))
    result = c.fetchone()

    if not result:
        return jsonify({"status": "invalid"})

    if result[5] != "active":
        return jsonify({"status": "disabled"})

    # Check expiry
    if result[4] != "never":
        expiry_date = datetime.strptime(result[4], "%Y-%m-%d")
        if datetime.now() > expiry_date:
            return jsonify({"status": "expired"})

    # Device binding
    if not result[2]:
        c.execute("UPDATE keys SET device_id=? WHERE id=?", (device_id, result[0]))
        conn.commit()
    elif result[2] != device_id:
        return jsonify({"status": "device_limit"})

    conn.close()
    return jsonify({"status": "valid"})

# ================= RENDER PORT FIX =================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
        
