import streamlit as st
import pandas as pd
import io
from PIL import Image
from pyzbar.pyzbar import decode
import requests

st.set_page_config(page_title="POS 商品快速建檔比對工具", layout="wide")
st.title("📦 POS 商品快速建檔比對工具")

# 完整商品資料庫連結 (已使用最穩定的 export 格式)
GDRIVE_DIRECT_URL = "https://docs.google.com/spreadsheets/d/1Efffq2OuR3y1qI3Xnngw974wkzJXZub1/export?format=xlsx"

# ⚠️ 請確保這裡貼上的是您在 Google Apps Script 拿到的「網頁應用程式網址」
GOOGLE_API_URL = "https://script.google.com/macros/s/您的專屬ID/exec" 

# --- API 溝通輔助函數 ---
def add_barcodes_to_api(codes):
    if "script.google.com" not in GOOGLE_API_URL:
        return False
    try:
        requests.post(f"{GOOGLE_API_URL}?action=add", json={"barcodes": codes}, timeout=15)
        return True
    except:
        return False

def get_barcodes_from_api():
    if "script.google.com" not in GOOGLE_API_URL:
        return []
    try:
        res = requests.get(GOOGLE_API_URL, timeout=15)
        return res.json().get("barcodes", [])
    except:
        return []

def clear_barcodes_from_api():
    if "script.google.com" not in GOOGLE_API_URL:
        return
    try:
        requests.post(f"{GOOGLE_API_URL}?action=clear", timeout=15)
        # 清空暫存畫面狀態
        if 'processing_codes' in st.session_state:
            st.session_state.processing_codes = []
    except:
        pass

# --- 讀取完整商品庫 ---
@st.cache_data(ttl=600)
def load_master_data():
    try:
        # 指定 engine='openpyxl' 避免無法辨識 Excel 格式的錯誤
        df = pd.read_excel(GDRIVE_DIRECT_URL, engine='openpyxl')
        if '助記碼' in df.columns:
            df['助記碼'] = df['助記碼'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"讀取雲端資料庫失敗：{e}")
        return None

with st.spinner('🔄 正在從 Google 雲端同步「完整商品資料表」...'):
    master_df = load_master_data()

if master_df is not None:
    # 重新排列頁籤順序
    tab1, tab2, tab3, tab4 = st.tabs([
        "📷 手機拍照掃描", 
        "🔫 實體掃碼槍", 
        "🌐 檢視累積條碼", 
        "📂 批次上傳與總匯出"
    ])
    
    # 紀錄本次操作已傳送過的條碼，避免畫面重新整理重複傳送
    if 'session_sent_codes' not in st.session_state:
        st.session_state.session_sent_codes = set()

    # === 分頁 1：手機拍照 (只負責上傳到 API) ===
    with tab1:
        st.write("### 📷 透過手機相機辨識商品條碼")
        st.info("掃描成功的條碼會直接存入雲端「POS暫存條碼庫」，不會在此頁進行比對。")
        
        camera_image = st.camera_input("📸 點擊這裡開啟相機 / 拍照")
        if camera_image is not None:
            image = Image.open(camera_image)
            decoded_objects = decode(image)
            if decoded_objects:
                new_codes = []
                for obj in decoded_objects:
                    barcode_data = obj.data.decode('utf-8').strip()
                    if barcode_data not in st.session_state.session_sent_codes:
                        new_codes.append(barcode_data)
                        st.session_state.session_sent_codes.add(barcode_data)
                
                if new_codes:
                    success = add_barcodes_to_api(new_codes)
                    if success:
                        st.success(f"✅ 成功將條碼傳送至雲端暫存庫：{', '.join(new_codes)}")
                    else:
                        st.error("❌ 傳送失敗，請檢查 Google API 網址設定。")
            else:
                st.error("❌ 找不到條碼，請確認畫面清晰再拍一次。")

    # === 分頁 2：掃碼槍 (只負責上傳到 API) ===
    with tab2:
        st.write("### 🔫 使用實體掃碼槍")
        st.info("刷入的條碼會直接存入雲端「POS暫存條碼庫」，不會在此頁進行比對。")
        
        with st.form(key='barcode_form', clear_on_submit=True):
            barcode_input = st.text_input("👇 請將游標點擊下方輸入框，然後按下掃碼槍：")
            submit_button = st.form_submit_button("送出至暫存庫")
            
        if submit_button and barcode_input:
            clean_code = barcode_input.strip()
            if clean_code:
                success = add_barcodes_to_api([clean_code])
                if success:
                    st.success(f"✅ 成功將條碼傳送至雲端暫存庫：{clean_code}")
                else:
                    st.error("❌ 傳送失敗，請檢查 Google API 網址設定。")

    # === 分頁 3：純檢視 API 累積狀態 ===
    with tab3:
        st.write("### 🌐 目前雲端暫存庫累積狀態")
        if st.button("🔄 重新整理檢視"):
            pass # 按鈕會觸發重新整理
            
        current_codes = get_barcodes_from_api()
        st.metric("目前試算表累積的條碼總數", len(current_codes))
        if current_codes:
            st.write("📝 **清單預覽：**", current_codes)

    # === 分頁 4：批次上傳 ＆ 結算匯出 ===
    with tab4:
        st.write("### 📂 第一步：手動批次上傳條碼 (非必要)")
        st.info("如果您有整批的 Excel 條碼清單，可以在此上傳並加入暫存庫。")
        
        uploaded_file = st.file_uploader("請上傳檔案", type=["xlsx", "csv"], key="file_uploader")
        if uploaded_file:
            scan_df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)
            scan_col = st.selectbox("請選擇包含「掃描條碼」的欄位", scan_df.columns)
            
            if st.button("⬆️ 將這批條碼加入暫存庫"):
                batch_codes = scan_df[scan_col].dropna().astype(str).str.strip().tolist()
                success = add_barcodes_to_api(batch_codes)
                if success:
                    st.success(f"✅ 成功將 {len(batch_codes)} 筆條碼加入雲端暫存庫！請至下方結算。")
                else:
                    st.error("❌ 傳送失敗。")

        st.divider()
        
        st.write("### 📥 第二步：比對結算與下載 POS 匯入檔")
        st.write("點擊下方按鈕，系統會將「手機、掃碼槍、批次上傳、第三方系統」累積在暫存庫的所有條碼，一次抓下來進行比對！")
        
        if st.button("🚀 載入所有累積條碼並比對"):
            st.session_state.processing_codes = get_barcodes_from_api()
            if not st.session_state.processing_codes:
                st.warning("目前暫存庫沒有任何條碼喔！")
                
        # 處理比對邏輯與畫面呈現
        if 'processing_codes' in st.session_state and st.session_state.processing_codes:
            # 去除重複條碼
            final_codes = list(set([str(c).strip() for c in st.session_state.processing_codes if str(c).strip()]))
            
            matched_df = master_df[master_df['助記碼'].isin(final_codes)].copy()
            found_codes = matched_df['助記碼'].tolist()
            missing_codes = list(set(final_codes) - set(found_codes))
            
            col1, col2 = st.columns(2)
            col1.metric("✅ 成功比對並找出的商品數", len(matched_df))
            col2.metric("❌ 找不到的條碼數", len(missing_codes))
            
            # --- 找不到的條碼，用文字框顯示方便複製 ---
            if missing_codes:
                st.warning("⚠️ 以下條碼在雲端的「完整商品資料表」中找不到：")
                # 使用 text_area 讓使用者可以一鍵全選複製
                st.text_area("請直接複製下方條碼至其他系統處理：", value="\n".join(missing_codes), height=150)
                
            # --- 找得到的條碼，產生匯入檔 ---
            if not matched_df.empty:
                st.write("#### 準備匯出 POS 檔案")
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
                
                # 下載檔案並自動呼叫清空 API
                st.download_button(
                    label="📥 下載 Excel 匯入檔 (下載後將自動清空 Google 暫存庫！)",
                    data=buffer.getvalue(),
                    file_name="POS_待匯入商品_已比對.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    on_click=clear_barcodes_from_api 
                )
