import streamlit as st
import pandas as pd
import io
from PIL import Image
from pyzbar.pyzbar import decode
import requests

# 設定頁面標題
st.set_page_config(page_title="POS 商品快速建檔比對工具", layout="wide")
st.title("📦 POS 商品快速建檔比對工具")

GDRIVE_DIRECT_URL = "https://drive.google.com/uc?id=1Efffq2OuR3y1qI3Xnngw974wkzJXZub1"

# ⚠️ 請將這裡換成您在 Render 拿到的網址 (不要在結尾加斜線 /)
API_BASE_URL = "https://您在Render的網址.onrender.com" 

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
    # 建立四個分頁 (新增了 API 累積處理分頁)
    tab1, tab2, tab3, tab4 = st.tabs(["📂 批次上傳掃描檔", "📷 手機拍照掃描", "🔫 實體掃碼槍", "🌐 第三方 API 累積處理"])
    final_scanned_codes = []
    
    # === 分頁 1、2、3：保留您原本手動操作的功能 (這裡濃縮顯示，功能皆相同) ===
    with tab1:
        st.write("### 📂 手動上傳 Excel/CSV 檔案")
        uploaded_file = st.file_uploader("請上傳檔案", type=["xlsx", "csv"], key="file_uploader")
        if uploaded_file:
            scan_df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)
            scan_col = st.selectbox("請選擇包含「掃描條碼」的欄位", scan_df.columns)
            final_scanned_codes = scan_df[scan_col].dropna().astype(str).str.strip().tolist()

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
                st.error("❌ 找不到條碼。")
        if st.session_state.camera_scanned_codes:
            st.write(st.session_state.camera_scanned_codes)
            final_scanned_codes = st.session_state.camera_scanned_codes

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
            st.write(st.session_state.gun_scanned_codes)
            final_scanned_codes = st.session_state.gun_scanned_codes

    # === 分頁 4：新功能！處理第三方 API 累積的條碼 ===
    with tab4:
        st.write("### 🌐 處理第三方系統傳送的累積條碼")
        st.info("系統會自動抓取第三方 API 傳過來並暫存的條碼。下載匯入檔後，累積清單將會「自動清空」以等待下一批。")
        
        # 建立一個按鈕來手動刷新 API 資料
        if st.button("🔄 重新整理 / 抓取最新累積條碼"):
            st.rerun()

        try:
            # 呼叫我們在 Render 部署的 API
            response = requests.get(f"{API_BASE_URL}/api/get_barcodes", timeout=10)
            if response.status_code == 200:
                api_pending_codes = response.json().get("barcodes", [])
                
                st.metric("目前等待處理的累積條碼數量", len(api_pending_codes))
                
                if api_pending_codes:
                    st.write("📝 **累積清單：**", api_pending_codes)
                    
                    # 決定將這批 API 條碼送進共用的比對邏輯中
                    if st.button("🚀 開始比對這批累積條碼"):
                        st.session_state.api_processing_codes = api_pending_codes
                        st.success("✅ 已載入比對清單，請看下方比對結果！")
                        
                else:
                    st.success("🎉 目前沒有任何累積的條碼需要處理。")
                    
            else:
                st.error(f"API 回傳錯誤：{response.status_code}")
        except Exception as e:
            st.error(f"無法連線到 API 伺服器，請確認 Render 是否正常運作或網址是否填寫正確。\n({e})")

        # 檢查是否有點擊處理 API 條碼
        if 'api_processing_codes' in st.session_state and st.session_state.api_processing_codes:
            final_scanned_codes = st.session_state.api_processing_codes


    # === 共用邏輯：資料比對與產出 Excel ===
    st.divider()
    if final_scanned_codes:
        st.write("### 📊 比對結果")
        matched_df = master_df[master_df['助記碼'].isin(final_scanned_codes)].copy()
        found_codes = matched_df['助記碼'].tolist()
        missing_codes = list(set(final_scanned_codes) - set(found_codes))
        
        col1, col2 = st.columns(2)
        col1.metric("✅ 成功比對並找出的商品數", len(matched_df))
        col2.metric("❌ 雲端資料庫也找不到的條碼數", len(missing_codes))
        
        if missing_codes:
            st.warning("⚠️ 以下條碼在雲端的「完整商品資料表」中也找不到，請手動新增：")
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
            
            # --- 核心機制：下載後自動呼叫 API 清空資料 ---
            def clear_api_and_reset():
                try:
                    # 呼叫 API 清空伺服器資料庫
                    requests.post(f"{API_BASE_URL}/api/clear_barcodes")
                    # 清空 Streamlit 畫面暫存
                    st.session_state.api_processing_codes = []
                    # 為了手動掃描的分頁也一併清空
                    if 'camera_scanned_codes' in st.session_state: st.session_state.camera_scanned_codes = []
                    if 'gun_scanned_codes' in st.session_state: st.session_state.gun_scanned_codes = []
                except:
                    pass

            st.download_button(
                label="📥 點此下載 Excel 匯入檔 (下載後將自動清空累積清單！)",
                data=buffer.getvalue(),
                file_name="POS_待匯入商品_已比對.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                on_click=clear_api_and_reset  # 點擊下載時觸發清空動作
            )
