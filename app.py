from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import sqlite3
import random
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

DB_NAME = "luckywheel.db"

# Initialize DB with 1–22 members
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            number INTEGER NOT NULL,
            selected INTEGER DEFAULT 0,
            selected_at TEXT
        )
    ''')
    c.execute("SELECT COUNT(*) FROM members")
    if c.fetchone()[0] == 0:
        names = ["Alice","Bob","Charlie","David","Eva","Farhan","Grace","Hari","Isha","Jack",
                 "Kavya","Leo","Mira","Nithin","Olivia","Pooja","Quinn","Ravi","Sita","Thomas",
                 "Uma","Vikram"]
        for i, name in enumerate(names, start=1):
            c.execute("INSERT INTO members (name, number) VALUES (?, ?)", (name, i))
    conn.commit()
    conn.close()

init_db()

# Get available members
def get_available():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, name, number FROM members WHERE selected=0")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "number": r[2]} for r in rows]

@app.route("/")
def index():
    return render_template("index.html")

# API: available members (optional)
@app.route("/api/available")
def available_api():
    return jsonify({"available": get_available()})

# SocketIO: spin wheel
@socketio.on("spin_wheel")
def spin_wheel():
    available = get_available()
    if not available:
        emit("spin_result", {"error": "No members left"})
        return
    winner = random.choice(available)
    # Mark as selected
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE members SET selected=1, selected_at=? WHERE id=?",
              (datetime.utcnow().isoformat(), winner["id"]))
    conn.commit()
    conn.close()
    # Notify all clients: start spinning
    emit("spin_started", {}, broadcast=True)
    socketio.sleep(4)  # simulate 4-second spin
    emit("spin_result", {"winner": winner}, broadcast=True)

# SocketIO: reset wheel
@socketio.on("reset_wheel")
def reset_wheel():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE members SET selected=0, selected_at=NULL")
    conn.commit()
    conn.close()
    emit("wheel_reset", {}, broadcast=True)

# Optional: Admin page
ADMIN_USER = "admin"
ADMIN_PASS = "password"

from flask import request, Response

def check_auth(username, password):
    return username == ADMIN_USER and password == ADMIN_PASS

def authenticate():
    return Response(
        'Login required.', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    decorated.__name__ = f.__name__
    return decorated

@app.route("/admin")
@requires_auth
def admin():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, name, number, selected, selected_at FROM members")
    rows = c.fetchall()
    conn.close()
    html = "<h1>Admin - Member Database</h1>"
    html += "<table border='1' style='border-collapse: collapse;'><tr><th>ID</th><th>Name</th><th>Number</th><th>Selected</th><th>Selected At</th></tr>"
    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{'Yes' if r[3] else 'No'}</td><td>{r[4] if r[4] else ''}</td></tr>"
    html += "</table>"
    return html

if __name__ == "__main__":
    socketio.run(app, debug=True)
