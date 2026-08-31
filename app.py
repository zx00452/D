```python
from flask import Flask, request, jsonify
import sqlite3
import os
import json
from datetime import datetime

app = Flask(__name__)

# -------- 初始化数据库（自动建表）--------
def init_db():
    # 使用 /app/data/ 作为持久化目录（Zeabur挂载点）
    db_path = os.path.join(os.environ.get('DATA_DIR', '/app/data'), 'activity.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    # 只保留最近100条（清理）
    c.execute('''
        DELETE FROM activities 
        WHERE id NOT IN (
            SELECT id FROM activities ORDER BY created_at DESC LIMIT 100
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db_conn():
    db_path = os.path.join(os.environ.get('DATA_DIR', '/app/data'), 'activity.db')
    return sqlite3.connect(db_path)

# -------- 1. 健康检查 --------
@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok"}), 200

# -------- 2. 上报接口（iOS快捷指令调用）--------
@app.route('/report', methods=['POST'])
def report():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    expected_token = os.environ.get('REPORT_TOKEN')
    if not expected_token or token != expected_token:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    if not data or 'app_name' not in data:
        return jsonify({"error": "Missing app_name"}), 400
    app_name = data['app_name']
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('INSERT INTO activities (app_name) VALUES (?)', (app_name,))
    # 保留最近100条
    c.execute('''
        DELETE FROM activities 
        WHERE id NOT IN (
            SELECT id FROM activities ORDER BY created_at DESC LIMIT 100
        )
    ''')
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "app": app_name}), 200

# -------- 3. 查最近100条完整记录 --------
@app.route('/activity', methods=['GET'])
def get_activity():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    expected_token = os.environ.get('REPORT_TOKEN')
    if not expected_token or token != expected_token:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT app_name, created_at FROM activities ORDER BY created_at DESC LIMIT 100')
    rows = c.fetchall()
    conn.close()
    result = [{"app": row[0], "time": row[1]} for row in rows]
    return jsonify(result), 200

# -------- 4. 聚合查询（最近活跃时间+最近10个App）--------
@app.route('/activity/summary', methods=['GET'])
def get_summary():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    expected_token = os.environ.get('REPORT_TOKEN')
    if not expected_token or token != expected_token:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db_conn()
    c = conn.cursor()
    # 最近一条
    c.execute('SELECT app_name, created_at FROM activities ORDER BY created_at DESC LIMIT 1')
    last = c.fetchone()
    # 最近10个不重复App
    c.execute('''
        SELECT DISTINCT app_name FROM activities 
        ORDER BY created_at DESC LIMIT 10
    ''')
    apps = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify({
        "last_active": {"app": last[0], "time": last[1]} if last else None,
        "recent_apps": apps
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
```
