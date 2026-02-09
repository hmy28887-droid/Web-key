from flask import Flask, request, jsonify, render_template_string, redirect, session
import sqlite3
import datetime
import hashlib
import os

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_SECRET_KEY"

DB = "keys.db"

ADMIN_USER = "hoangnam0303"
ADMIN_PASS = "hoangnam0804"

# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            key TEXT PRIMARY KEY,
            expiry TEXT,
            device_id TEXT,
            max_devices INTEGER
        )
    """)
    conn.commit()
    conn.close()

def generate_key(days):
    key_raw = hashlib.sha256(os.urandom(64)).hexdigest()[:20]

    if days == 0:
        expiry = "never"
    else:
        expiry = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO licenses VALUES (?, ?, ?, ?)", (key_raw, expiry, None, 1))
    conn.commit()
    conn.close()

    return key_raw

# ================= LOGIN =================

def login_required():
    return "admin" in session

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["admin"] = True
            return redirect("/")
    return """
    <body style='background:#111;color:white;font-family:sans-serif;text-align:center;padding-top:120px'>
    <h2>🔐 Admin Login</h2>
    <form method='POST'>
    <input name='username' placeholder='Username'><br><br>
    <input name='password' type='password' placeholder='Password'><br><br>
    <button>Login</button>
    </form>
    </body>
    """

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= DASHBOARD =================

@app.route("/")
def admin():
    if not login_required():
        return redirect("/login")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM licenses")
    data = c.fetchall()
    conn.close()

    html = """
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" rel="stylesheet">

    <body class="bg-dark text-light">
    <div class="container mt-5">

    <div class="card bg-black border-secondary p-3">
    <h5><i class="fa-solid fa-key"></i> Khóa cấp phép</h5>

    <form method="POST" action="/create" class="row g-2 mb-3">
        <div class="col-auto">
            <input class="form-control bg-dark text-light border-secondary" name="days" placeholder="Số ngày (0 = không hết hạn)">
        </div>
        <div class="col-auto">
            <button class="btn btn-warning">Tạo key</button>
        </div>
        <div class="col-auto">
            <a href="/logout" class="btn btn-danger">Logout</a>
        </div>
    </form>

    <table class="table table-dark align-middle">
    <thead>
        <tr>
            <th>Chìa khóa</th>
            <th>Thiết bị</th>
            <th>Hạn sử dụng</th>
            <th>Trạng thái</th>
            <th>Hành động</th>
        </tr>
    </thead>
    <tbody>
    {% for row in data %}
        <tr>
            <td>{{row[0]}}</td>

            <td>
                {% if row[2] %}
                    <span class="badge bg-danger">1/1</span>
                {% else %}
                    <span class="badge bg-secondary">0/1</span>
                {% endif %}
            </td>

            <td>
                {% if row[1] == "never" %}
                    <span class="badge bg-info"><i class="fa-solid fa-infinity"></i> Không hết hạn</span>
                {% else %}
                    <span class="badge bg-info">{{row[1]}}</span>
                {% endif %}
            </td>

            <td>
                <span class="badge bg-success">Tích cực</span>
            </td>

            <td>
                <a href="/reset/{{row[0]}}" class="btn btn-warning btn-sm">
                    <i class="fa-solid fa-rotate"></i>
                </a>

                <a href="/delete/{{row[0]}}" class="btn btn-danger btn-sm"
                onclick="return confirm('Xóa key này?')">
                    <i class="fa-solid fa-trash"></i>
                </a>
            </td>

        </tr>
    {% endfor %}
    </tbody>
    </table>
    </div>
    </div>
    </body>
    """
    return render_template_string(html, data=data)

# ================= ACTIONS =================

@app.route("/create", methods=["POST"])
def create():
    if not login_required():
        return redirect("/login")

    days = int(request.form["days"])
    generate_key(days)
    return redirect("/")

@app.route("/delete/<key>")
def delete_key(key):
    if not login_required():
        return redirect("/login")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM licenses WHERE key=?", (key,))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/reset/<key>")
def reset_device(key):
    if not login_required():
        return redirect("/login")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE licenses SET device_id=NULL WHERE key=?", (key,))
    conn.commit()
    conn.close()
    return redirect("/")

# ================= VERIFY API =================

@app.route("/verify", methods=["POST"])
def verify():
    data = request.json
    user_key = data.get("key")
    device_id = data.get("device_id")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT expiry, device_id FROM licenses WHERE key=?", (user_key,))
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "invalid"})

    expiry, saved_device = row

    if expiry != "never":
        expiry_time = datetime.datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
        if datetime.datetime.now() > expiry_time:
            return jsonify({"status": "expired"})

    if saved_device is None:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("UPDATE licenses SET device_id=? WHERE key=?", (device_id, user_key))
        conn.commit()
        conn.close()
        return jsonify({"status": "valid"})

    if saved_device != device_id:
        return jsonify({"status": "wrong_device"})

    return jsonify({"status": "valid"})

if __name__ == "__main__":
    init_db()
    app.run()
  
