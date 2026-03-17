import streamlit as st
import pandas as pd
import io
from PIL import Image
from pyzbar.pyzbar import decode
import requests

st.set_page_config(page_title="POS 商品快速建檔比對工具", layout="wide")
st.title("📦 POS 商品快速建檔比對工具")

# 完整商品資料庫連結
GDRIVE_DIRECT_URL = "https://docs.google.com/spreadsheets/d/1Efffq2OuR3y1qI3Xnngw974wkzJXZub1/edit?usp=sharing&ouid=101526089892891550768&rtpof=true&sd=true"

# ⚠️ 請確保這裡貼上的是您在 Google Apps Script 拿到的「網頁應用程式網址」
GOOGLE_API_URL = "https://script.google.com/macros/s/AKfycbymbXp2yO4htU6dhp6uT7g6CSQUiO-R4c4QCK6Jmzfk_rEbMC6iptDOAUSDyWPc3eLE/exec" 

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
    tab1, tab2, tab3, tab4 = st.tabs(["📂 批次上傳掃描檔", "📷 手機拍照掃描", "🔫 實體掃碼槍", "🌐 第三方 API 累積處理"])
    
    # 用來集中收集所有分頁累積的條碼
    all_scanned_codes = []

    # === 分頁 1：批次上傳 ===
    with tab1:
        st.write("### 📂 手動上傳 Excel/CSV 檔案")
        uploaded_file = st.file_uploader("請上傳檔案", type=["xlsx", "csv"], key="file_uploader")
        if uploaded_file:
            scan_df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)
            scan_col = st.selectbox("請選擇包含「掃描條碼」的欄位", scan_df.columns)
            tab1_codes = scan_df[scan_col].dropna().astype(str).str.strip().tolist()
            all_scanned_codes.extend(tab1_codes)

    # === 分頁 2：手機拍照 ===
    with tab2:
        st.write("### 📷 透過手機相機辨識商品一維條碼")
        if 'camera_scanned_codes' not in st.session_state:
            st.session_state.camera_scanned_codes = []
        
        camera_image = st.camera_input("📸 點擊這裡開啟相機 / 拍照")
        if camera_image is not None:
            image = Image.open(camera_image)
            decoded_objects = decode(image)
            if decoded_objects:
                for obj in decoded_objects:
                    barcode_data = obj.data.decode('utf-8').strip()
                    if barcode_data not in st.session_state.camera_scanned_codes:
                        st.session_state.camera_scanned_codes.append(barcode_data)
            else:
                st.error("❌ 找不到條碼，請確認畫面清晰再拍一次。")
        
        if st.session_state.camera_scanned_codes:
            st.write("📝 目前拍照累積：", st.session_state.camera_scanned_codes)
            if st.button("🗑️ 清空拍照紀錄", key="clear_cam"):
                st.session_state.camera_scanned_codes = []
                st.rerun()
            all_scanned_codes.extend(st.session_state.camera_scanned_codes)

    # === 分頁 3：掃碼槍 ===
    with tab3:
        st.write("### 🔫 使用實體掃碼槍")
        if 'gun_scanned_codes' not in st.session_state:
            st.session_state.gun_scanned_codes = []
            
        with st.form(key='barcode_form', clear_on_submit=True):
            barcode_input = st.text_input("👇 請將游標點擊下方輸入框，然後按下掃碼槍：")
            submit_button = st.form_submit_button("送出")
            
        if submit_button and barcode_input:
            clean_code = barcode_input.strip()
            if clean_code and clean_code not in st.session_state.gun_scanned_codes:
                st.session_state.gun_scanned_codes.append(clean_code)
                
        if st.session_state.gun_scanned_codes:
            st.write("📝 目前掃碼槍累積：", st.session_state.gun_scanned_codes)
            if st.button("🗑️ 清空掃碼槍紀錄", key="clear_gun"):
                st.session_state.gun_scanned_codes = []
                st.rerun()
            all_scanned_codes.extend(st.session_state.gun_scanned_codes)

    # === 分頁 4：第三方 API ===
    with tab4:
        st.write("### 🌐 處理第三方系統傳送的累積條碼")
        st.info("條碼暫存在 Google 試算表中。下載匯入檔後將自動為您清空累積名單。")
        
        if st.button("🔄 重新整理 / 抓取最新累積條碼"):
            st.rerun()

        try:
            # 防呆機制：判斷使用者是否已經填寫 Google API 網址
            if "script.google.com" in GOOGLE_API_URL:
                response = requests.get(GOOGLE_API_URL, timeout=15)
                api_data = response.json()
                api_pending_codes = api_data.get("barcodes", [])
                
                st.metric("目前試算表累積的條碼數量", len(api_pending_codes))
                
                if api_pending_codes:
                    st.write("📝 **累積清單：**", api_pending_codes)
                    if st.button("🚀 載入這批累積條碼進行比對"):
                        st.session_state.api_processing_codes = api_pending_codes
                        st.success("✅ 已載入比對清單，請看下方比對結果！")
                else:
                    st.success("🎉 目前 Google 試算表中沒有累積的條碼需要處理。")
            else:
                st.warning("⚠️ 請記得在程式碼第 14 行填寫您的 Google Apps Script 網址，功能才會開通喔！")
                
        except Exception as e:
            st.error(f"無法連線到 Google API，請確認網址是否填寫正確。\n({e})")

        if 'api_processing_codes' in st.session_state and st.session_state.api_processing_codes:
            all_scanned_codes.extend(st.session_state.api_processing_codes)

    # === 共用邏輯：綜合比對與下載 ===
    st.divider()
    
    # 去除重複的條碼並過濾空白
    final_scanned_codes = list(set([str(c).strip() for c in all_scanned_codes if str(c).strip()]))
    
    if final_scanned_codes:
        st.write("### 📊 綜合比對結果")
        matched_df = master_df[master_df['助記碼'].isin(final_scanned_codes)].copy()
        found_codes = matched_df['助記碼'].tolist()
        missing_codes = list(set(final_scanned_codes) - set(found_codes))
        
        col1, col2 = st.columns(2)
        col1.metric("✅ 成功比對並找出的商品數", len(matched_df))
        col2.metric("❌ 找不到的條碼數", len(missing_codes))
        
        if missing_codes:
            st.warning("⚠️ 以下條碼在雲端的「完整商品資料表」中找不到，可能需要人工新增：")
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
            
            # --- 下載後自動清空所有紀錄與 API ---
            def clear_all_and_reset():
                try:
                    # 清空 Google 試算表
                    if "script.google.com" in GOOGLE_API_URL:
                        requests.post(f"{GOOGLE_API_URL}?action=clear", timeout=15)
                    # 清空畫面暫存
                    st.session_state.api_processing_codes = []
                    if 'camera_scanned_codes' in st.session_state: st.session_state.camera_scanned_codes = []
                    if 'gun_scanned_codes' in st.session_state: st.session_state.gun_scanned_codes = []
                except:
                    pass

            st.download_button(
                label="📥 點此下載 Excel 匯入檔 (下載後將自動清空上述所有紀錄！)",
                data=buffer.getvalue(),
                file_name="POS_待匯入商品_已比對.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                on_click=clear_all_and_reset 
            )
