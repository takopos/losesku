import streamlit as st
import pandas as pd
import io
from PIL import Image
from pyzbar.pyzbar import decode
import requests
import json

st.set_page_config(page_title="POS 商品快速建檔比對工具", layout="wide")
st.title("📦 POS 商品快速建檔比對工具")

# 完整商品資料庫連結
GDRIVE_DIRECT_URL = "https://drive.google.com/uc?id=1Efffq2OuR3y1qI3Xnngw974wkzJXZub1"

# ⚠️ 請將這裡換成您剛剛在 Google Apps Script 拿到的「網頁應用程式網址」
GOOGLE_API_URL = "https://script.google.com/macros/s/您的專屬ID/exec" 

@st.cache_data(ttl=600)
def load_master_data():
    try:
        df = pd.read_excel(GDRIVE_DIRECT_URL)
        if '助記碼' in df.columns:
            df['助記碼'] = df['助記碼'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"讀取雲端資料庫失敗：{e}")
        return None

with st.spinner('🔄 正在從 Google 雲端同步「完整商品資料表」...'):
    master_df = load_master_data()

if master_df is not None:
    tab1, tab2, tab3, tab4 = st.tabs(["📂 批次上傳掃描檔", "📷 手機拍照掃描", "🔫 實體掃碼槍", "🌐 處理第三方累積條碼"])
    final_scanned_codes = []
    
    # ... (前三個分頁的程式碼與上一版完全相同，為了版面簡潔此處省略，請保留上一版的 tab1, tab2, tab3 內容) ...
    # 這裡我補上 tab4 的邏輯：
    
    with tab4:
        st.write("### 🌐 處理第三方系統傳送的累積條碼")
        st.info("條碼目前安全地暫存在您的 Google 試算表中。下載匯入檔後，系統將自動為您清空試算表資料。")
        
        if st.button("🔄 抓取最新累積條碼"):
            st.rerun()

        try:
            # 呼叫 Google API 抓取資料 (GET)
            response = requests.get(GOOGLE_API_URL, timeout=15)
            # Google Apps Script 回傳時可能會帶有轉址，但 requests 會自動處理
            api_data = response.json()
            api_pending_codes = api_data.get("barcodes", [])
            
            st.metric("目前試算表累積的條碼數量", len(api_pending_codes))
            
            if api_pending_codes:
                st.write("📝 **累積清單：**", api_pending_codes)
                if st.button("🚀 開始比對這批累積條碼"):
                    st.session_state.api_processing_codes = api_pending_codes
                    st.success("✅ 已載入比對清單，請看下方比對結果！")
            else:
                st.success("🎉 目前 Google 試算表中沒有累積的條碼需要處理。")
                
        except Exception as e:
            st.error(f"無法連線到 Google 試算表 API，請確認網址是否正確。\n({e})")

        if 'api_processing_codes' in st.session_state and st.session_state.api_processing_codes:
            final_scanned_codes = st.session_state.api_processing_codes


    # === 共用邏輯：比對與下載 ===
    st.divider()
    if final_scanned_codes:
        st.write("### 📊 比對結果")
        matched_df = master_df[master_df['助記碼'].isin(final_scanned_codes)].copy()
        found_codes = matched_df['助記碼'].tolist()
        missing_codes = list(set(final_scanned_codes) - set(found_codes))
        
        col1, col2 = st.columns(2)
        col1.metric("✅ 成功比對並找出的商品數", len(matched_df))
        col2.metric("❌ 找不到的條碼數", len(missing_codes))
        
        if missing_codes:
            st.warning("⚠️ 以下條碼找不到對應商品，請手動新增：")
            st.write(missing_codes)
            
        if not matched_df.empty:
            st.write("### 📥 下載 POS 匯入檔")
            
            output_columns = ['商品名稱✳️', '助記碼', '項目別名', '商品條碼✳️', '分類✳️', '規格', '銷售價格✳️', '成本價', '計價方式✳', '單位✳️', '上架狀態✳️', '描述']
            instruction_row = ["1、帶✳️的欄位為必填\n2、單次最多導入2000條商品，超過按照表格順序，只導入前2000條\n3、多規格商品，表格中的商品名稱/分類/計價方式/單位元/上架狀態必須相同，若不同則認為是不同商品，可能導入失敗"] + [""] * 11
            header_row = output_columns
            desc_row = ["支援漢字/字母/數字及其它國際語言，最多50位", "", "支援漢字/字母/數字及其它國際語言，最多50位", "必須要選擇一種...", "必填，必須是店鋪已經新增的分類名稱", "不填寫時默認單規格商品...", "必填，只能輸入正數...", "選填，只能輸入正數...", "計件/稱重", "稱重商品的單位只能為g/kg...", "選擇上架/下架", "可選..."]
            
            for col in output_columns:
                if col not in matched_df.columns:
                    matched_df[col] = ""
            matched_data_only = matched_df[output_columns]
            
            final_output = pd.DataFrame([instruction_row, header_row, desc_row])
            final_output = pd.concat([final_output, pd.DataFrame(matched_data_only.values)], ignore_index=True)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                final_output.to_excel(writer, index=False, header=False, sheet_name="導入範本")
            
            # --- 核心機制：呼叫 Google API 清空資料表 ---
            def clear_api_and_reset():
                try:
                    # 傳送 POST 請求，並帶上 ?action=clear 的參數
                    requests.post(f"{GOOGLE_API_URL}?action=clear", timeout=15)
                    st.session_state.api_processing_codes = []
                    if 'camera_scanned_codes' in st.session_state: st.session_state.camera_scanned_codes = []
                    if 'gun_scanned_codes' in st.session_state: st.session_state.gun_scanned_codes = []
                except:
                    pass

            st.download_button(
                label="📥 點此下載 Excel 匯入檔 (下載後將自動清空 Google 試算表累積清單！)",
                data=buffer.getvalue(),
                file_name="POS_待匯入商品_已比對.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                on_click=clear_api_and_reset 
            )
