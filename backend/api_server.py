from flask import Flask, request, jsonify, render_template, send_file, g, current_app
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from db.db_helper import get_db, init_db
from datetime import datetime, date
import sqlite3, csv, os
from io import StringIO, BytesIO
import threading
import time
import pyttsx3
import queue
from openpyxl import Workbook

app = Flask(__name__, template_folder="../web/templates", static_folder="../web/static")
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

with app.app_context():
    init_db()

MENU = {
    "🍖 山豬肉": {"price": 100, "type": "food", "img": "meat.png"},
    "🌭 香腸": {"price": 50, "type": "food", "img": "sausage.png"},
    "🍹 水果茶": {"price": 45, "type": "drink", "img": "tea.png"},
    "🍹 水果茶（自備杯）": {"price": 40, "type": "drink", "img": "tea.png"},
}

tts_queue = queue.Queue()

def tts_worker():
    engine = pyttsx3.init()
    engine.setProperty("rate", 150)
    engine.setProperty("volume", 1)
    while True:
        text = tts_queue.get()
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print("語音播放錯誤:", e)
        tts_queue.task_done()

def speak(text):
    tts_queue.put(text)

tts_thread = threading.Thread(target=tts_worker, daemon=True)
tts_thread.start()

def auto_clear_order(order_id, app):
    time.sleep(50)
    with app.app_context():
        db = get_db()
        db.execute("UPDATE orders SET status = ? WHERE id = ?", ("cleared", order_id))
        db.commit()

@app.route("/menu", methods=["GET", "POST"])
def menu():
    if request.method == "POST":
        data = request.form
        customer_name = data.get("customer_name", "").strip()
        if not customer_name:
            return render_template("menu.html", menu=MENU, error="請輸入姓名")
        
        items = []
        total = 0
        for item in MENU:
            qty = int(data.get(item, 0) or 0)
            if qty > 0:
                items.append(f"{item} x {qty}")
                total += MENU[item]["price"] * qty

        if not items:
            return render_template("menu.html", menu=MENU, error="請至少選擇一項")

        db = get_db()
        db.execute("""
            INSERT INTO orders (customer_name, items, total_price, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
        """, (customer_name, ", ".join(items), total, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        db.commit()
        order_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        socketio.emit("new_order", {"order_id": order_id, "name": customer_name})
        return render_template("success.html", order_id=order_id, items=items, total=total)

    return render_template("menu.html", menu=MENU)

@app.route("/admin207")
def admin_ui():
    db = get_db()
    orders = db.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    row = db.execute("""
        SELECT COUNT(*) AS count, SUM(total_price) AS total
        FROM orders WHERE status != 'cancelled'
    """).fetchone()
    return render_template("admin.html", orders=orders, report={"orders": row["count"], "total": row["total"]})

@app.route("/admin/update_status", methods=["POST"])
def admin_update_status():
    order_id = request.json.get("order_id")
    db = get_db()
    row = db.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not row:
        return jsonify({"error": "無此訂單"}), 404

    status = row["status"]
    next_status = "preparing" if status == "pending" else "ready" if status == "preparing" else None
    if next_status:
        db.execute("UPDATE orders SET status = ? WHERE id = ?", (next_status, order_id))
        db.commit()
        socketio.emit("order_updated", {"order_id": order_id, "status": next_status})

        if next_status == "ready":
            speak(f"編號 {order_id} 號的訂單已完成，請取餐")
            threading.Thread(target=auto_clear_order, args=(order_id, current_app._get_current_object())).start()

        return jsonify({"message": "狀態已更新"})

    return jsonify({"message": "無可更新狀態"})

@app.route("/api/order/<int:order_id>/cancel", methods=["POST"])
def cancel_order(order_id):
    db = get_db()
    db.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))
    db.commit()
    socketio.emit("order_updated", {"order_id": order_id, "status": "cancelled"})
    return jsonify({"message": "訂單已取消"})

@app.route("/display")
def display_ui():
    db = get_db()
    preparing_orders = db.execute(
        "SELECT * FROM orders WHERE status = 'preparing' ORDER BY created_at DESC"
    ).fetchall()
    ready_orders = db.execute(
        "SELECT * FROM orders WHERE status IN ('ready', 'cleared') ORDER BY created_at DESC;"
    ).fetchall()
    return render_template("display.html", preparing_orders=preparing_orders, ready_orders=ready_orders)

@app.route("/api/report/download")
def download_report():
    db = get_db()
    orders = db.execute("""
        SELECT * FROM orders 
        WHERE status != 'cancelled'
        ORDER BY created_at DESC
    """).fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "所有訂單報表"
    ws.append(["訂單編號", "顧客", "品項", "金額", "狀態", "時間"])
    for o in orders:
        ws.append([
            o["id"],
            o["customer_name"],
            o["items"],
            o["total_price"],
            o["status"],
            o["created_at"]
        ])

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    return send_file(
        stream,
        as_attachment=True,
        download_name="report_all_orders.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/order/search", methods=["GET", "POST"])
def search_order():
    if request.method == "POST":
        order_id = request.form.get("order_id")
        db = get_db()
        row = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if row:
            return render_template("search_order.html", result=row)
        else:
            return render_template("search_order.html", error="查無此訂單編號")
    return render_template("search_order.html")



@app.route("/")
def index():
    return render_template("qrcode.html")

@socketio.on("connect")
def handle_connect():
    print("✅ SocketIO client connected")

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
