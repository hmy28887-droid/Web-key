from flask import Flask, render_template_string, request, redirect, session, jsonify
import sqlite3
import os
import random
import string
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "supersecretkey"

ADMIN_USER = "admin"
ADMIN_PASS = "hoangnam0804"

DB = "keys.db"

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE,
        device_id TEXT,
        expire_at TEXT,
        active INTEGER DEFAULT 1
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ================= BASE UI =================
BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }}</title>
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet">
<style>
body{margin:0;font-family:Segoe UI;background:#0f172a;color:#cbd5e1}
.container{max-width:1100px;margin:auto;padding:30px}
.card{background:#111827;padding:20px;border-radius:12px}
h1{color:white}
table{width:100%;border-collapse:collapse}
th,td{padding:12px;border-bottom:1px solid #1f2937}
tr:hover{background:#1e293b}
.badge{padding:5px 10px;border-radius:6px;font-size:12px}
.success{background:#14532d;color:#22c55e}
.danger{background:#7f1d1d;color:#ef4444}
.info{background:#083344;color:#06b6d4}
.btn{padding:6px 10px;border-radius:6px;text-decoration:none;font-size:13px;margin-right:5px}
.blue{background:#3b82f6;color:white}
.red{background:#ef4444;color:white}
input,select{padding:8px;width:100%;margin:8px 0;border-radius:8px;border:none;background:#1f2937;color:white}
button{padding:8px 14px;border:none;border-radius:8px;background:#2563eb;color:white}
.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}
</style>
</head>
<body>
<div class="container">
{{ content|safe }}
</div>
</body>
</html>
"""

# ================= LOGIN =================
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["admin"] = True
            return redirect("/")
    content = """
    <div class="card">
        <h1>Admin Login</h1>
        <form method="post">
            <input name="username" placeholder="Username">
            <input name="password" type="password" placeholder="Password">
            <button>Login</button>
        </form>
    </div>
    """
    return render_template_string(BASE_HTML,title="Login",content=content)

# ================= DASHBOARD =================
@app.route("/")
def home():
    if not session.get("admin"):
        return redirect("/login")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM keys")
    data = c.fetchall()
    conn.close()

    rows = ""
    now = datetime.now()

    for row in data:
        id,key,device,expire,active = row
        expire_dt = datetime.fromisoformat(expire)

        if now > expire_dt:
            status = '<span class="badge danger">Hết hạn</span>'
        elif active:
            status = '<span class="badge success">Hoạt động</span>'
        else:
            status = '<span class="badge danger">Bị khóa</span>'

        device_text = device if device else "Chưa bind"

        rows += f"""
        <tr>
            <td>{key}</td>
            <td>{device_text}</td>
            <td>{expire_dt.strftime('%d/%m/%Y')}</td>
            <td>{status}</td>
            <td>
                <a href="/delete/{id}" class="btn red">Xóa</a>
            </td>
        </tr>
        """

    content = f"""
    <div class="card">
    <div class="top">
        <h1>Quản lý Key</h1>
        <a href="/create" class="btn blue">+ Tạo Key</a>
    </div>
    <table>
        <tr>
            <th>Key</th>
            <th>Thiết bị</th>
            <th>Hạn</th>
            <th>Trạng thái</th>
            <th>Hành động</th>
        </tr>
        {rows}
    </table>
    </div>
    """

    return render_template_string(BASE_HTML,title="Dashboard",content=content)

# ================= CREATE KEY =================
@app.route("/create", methods=["GET","POST"])
def create():
    if not session.get("admin"):
        return redirect("/login")

    if request.method == "POST":
        days = int(request.form["days"])
        new_key = ''.join(random.choices(string.ascii_uppercase+string.digits,k=16))
        expire = datetime.now() + timedelta(days=days)

        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("INSERT INTO keys (key,expire_at) VALUES (?,?)",(new_key,expire.isoformat()))
        conn.commit()
        conn.close()

        return redirect("/")

    content = """
    <div class="card">
        <h1>Tạo Key</h1>
        <form method="post">
            <select name="days">
                <option value="1">1 ngày</option>
                <option value="7">7 ngày</option>
                <option value="30">30 ngày</option>
                <option value="365">365 ngày</option>
            </select>
            <button>Tạo</button>
        </form>
    </div>
    """
    return render_template_string(BASE_HTML,title="Create",content=content)

# ================= DELETE =================
@app.route("/delete/<int:id>")
def delete(id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM keys WHERE id=?",(id,))
    conn.commit()
    conn.close()
    return redirect("/")

# ================= API CHECK KEY =================
@app.route("/api/check", methods=["POST"])
def api_check():
    data = request.json
    key = data.get("key")
    device_id = data.get("device_id")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id,device_id,expire_at,active FROM keys WHERE key=?",(key,))
    row = c.fetchone()

    if not row:
        return jsonify({"status":"invalid"})

    id,stored_device,expire,active = row
    expire_dt = datetime.fromisoformat(expire)

    if not active:
        return jsonify({"status":"banned"})

    if datetime.now() > expire_dt:
        return jsonify({"status":"expired"})

    # ===== BIND DEVICE =====
    if not stored_device:
        c.execute("UPDATE keys SET device_id=? WHERE id=?",(device_id,id))
        conn.commit()
        conn.close()
        return jsonify({"status":"bound"})

    if stored_device != device_id:
        conn.close()
        return jsonify({"status":"device_mismatch"})

    conn.close()
    return jsonify({"status":"valid"})

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)
    
