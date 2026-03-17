import streamlit as st
import pandas as pd
import io
from PIL import Image
from pyzbar.pyzbar import decode

# 設定頁面標題
st.set_page_config(page_title="POS 商品快速建檔比對工具", layout="wide")
st.title("📦 POS 商品快速建檔比對工具")

GDRIVE_DIRECT_URL = "https://drive.google.com/uc?id=1Efffq2OuR3y1qI3Xnngw974wkzJXZub1"

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
    st.success(f"✅ 成功載入雲端完整資料庫！目前共有 {len(master_df)} 筆商品。")
    
    # 建立三個分頁
    tab1, tab2, tab3 = st.tabs(["📂 批次上傳掃描檔", "📷 手機拍照掃描 (一維條碼)", "🔫 實體掃碼槍 (最推薦)"])
    final_scanned_codes = []
    
    # === 分頁 1：原本的檔案上傳功能 ===
    with tab1:
        st.write("### 適用於：已經有一整份 Excel 條碼清單")
        uploaded_file = st.file_uploader("請上傳檔案 (Excel 或 CSV)", type=["xlsx", "csv"])
        if uploaded_file:
            scan_df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)
            scan_col = st.selectbox("請選擇包含「掃描條碼」的欄位", scan_df.columns)
            final_scanned_codes = scan_df[scan_col].dropna().astype(str).str.strip().tolist()

    # === 分頁 2：一維條碼專用拍照辨識 ===
    with tab2:
        st.write("### 透過手機相機辨識商品一維條碼")
        st.info("💡 操作提示：請將一維條碼放在畫面正中央，對焦清晰後點擊拍照。")
        
        if 'camera_scanned_codes' not in st.session_state:
            st.session_state.camera_scanned_codes = []
            
        # 呼叫官方穩定的相機元件
        camera_image = st.camera_input("📸 點擊這裡開啟相機 / 拍照")
        
        if camera_image is not None:
            # 讀取圖片並進行一維條碼辨識
            image = Image.open(camera_image)
            decoded_objects = decode(image)
            
            if decoded_objects:
                for obj in decoded_objects:
                    barcode_data = obj.data.decode('utf-8').strip()
                    if barcode_data not in st.session_state.camera_scanned_codes:
                        st.session_state.camera_scanned_codes.append(barcode_data)
                        st.success(f"✅ 成功掃描並記錄條碼：{barcode_data}")
                    else:
                        st.warning(f"⚠️ 條碼 {barcode_data} 剛剛已經掃過了喔！")
            else:
                st.error("❌ 找不到條碼，請確認條碼清晰、沒有反光，且佔據畫面主體再拍一次。")
                
        if st.session_state.camera_scanned_codes:
            st.write("#### 📝 目前已收集的條碼：")
            st.write(st.session_state.camera_scanned_codes)
            if st.button("🗑️ 清空重掃", key="clear_cam"):
                st.session_state.camera_scanned_codes = []
                st.rerun()
            final_scanned_codes = st.session_state.camera_scanned_codes

    # === 分頁 3：實體掃碼槍功能 (營運首選) ===
    with tab3:
        st.write("### 適用於：外接 USB 或藍牙實體掃碼槍")
        st.success("✨ 如果店裡商品很多，強烈建議買一把幾百塊的掃碼槍接電腦，游標點在下方框框直接刷，免對焦且 100% 準確！")
        
        if 'gun_scanned_codes' not in st.session_state:
            st.session_state.gun_scanned_codes = []
            
        with st.form(key='barcode_form', clear_on_submit=True):
            barcode_input = st.text_input("👇 請將游標點擊下方輸入框，然後按下掃碼槍：")
            submit_button = st.form_submit_button("送出 (大部分掃碼槍刷完會自動送出)")
            
        if submit_button and barcode_input:
            clean_code = barcode_input.strip()
            if clean_code and clean_code not in st.session_state.gun_scanned_codes:
                st.session_state.gun_scanned_codes.append(clean_code)
                st.success(f"✅ 成功記錄：{clean_code}")
            elif clean_code in st.session_state.gun_scanned_codes:
                 st.warning(f"⚠️ 條碼 {clean_code} 已經掃過了！")
                 
        if st.session_state.gun_scanned_codes:
            st.write("#### 📝 目前已收集的條碼：")
            st.write(st.session_state.gun_scanned_codes)
            if st.button("🗑️ 清空重掃", key="clear_gun"):
                st.session_state.gun_scanned_codes = []
                st.rerun()
            final_scanned_codes = st.session_state.gun_scanned_codes

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
            st.warning("⚠️ 以下條碼在雲端的「完整商品資料表」中也找不到，可能需要人工新增：")
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
            
            st.download_button(
                label="📥 點此下載「POS 匯入專用」Excel 檔",
                data=buffer.getvalue(),
                file_name="POS_待匯入商品_已比對.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
