from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import sqlite3
import os

app = FastAPI(title="POS 條碼收集 API", description="接收第三方條碼並暫存，供網頁端後續批次處理")

DB_FILE = "barcodes.db"

# 初始化輕量級資料庫 (SQLite)
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 建立一個資料表，設定 code 為唯一值，避免同一個條碼被重複加入
    c.execute("CREATE TABLE IF NOT EXISTS pending_barcodes (code TEXT UNIQUE)")
    conn.commit()
    conn.close()

init_db()

class BarcodeRequest(BaseModel):
    barcodes: List[str]

# 1. 接收第三方條碼的端點
@app.post("/api/add_barcodes")
def add_barcodes(request: BarcodeRequest):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    added_count = 0
    for code in request.barcodes:
        clean_code = str(code).strip()
        if clean_code:
            try:
                # INSERT OR IGNORE 可以自動忽略已經存在資料庫裡的重複條碼
                c.execute("INSERT OR IGNORE INTO pending_barcodes (code) VALUES (?)", (clean_code,))
                if c.rowcount > 0:
                    added_count += 1
            except Exception:
                pass
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"成功接收並新增 {added_count} 筆新條碼"}

# 2. 提供給 Streamlit 網頁讀取「目前累積了多少條碼」的端點
@app.get("/api/get_barcodes")
def get_barcodes():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT code FROM pending_barcodes")
    rows = c.fetchall()
    conn.close()
    # 將結果轉為純文字清單回傳
    return {"barcodes": [row[0] for row in rows]}

# 3. 提供給 Streamlit 網頁「一鍵清空」的端點
@app.post("/api/clear_barcodes")
def clear_barcodes():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM pending_barcodes")
    conn.commit()
    conn.close()
    return {"status": "success", "message": "資料庫已清空"}
