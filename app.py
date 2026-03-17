import streamlit as st
import pandas as pd
import io
from PIL import Image
from pyzbar.pyzbar import decode

# 設定頁面標題
st.set_page_config(page_title="POS 商品快速建檔比對工具", layout="wide")
st.title("📦 POS 商品快速建檔比對工具")

# --- 1. 自動讀取您專屬的 Google 雲端完整資料表 ---
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
    
    # 建立兩個分頁
    tab1, tab2 = st.tabs(["📂 批次上傳掃描檔", "📷 使用鏡頭拍照掃描"])
    
    # 用來儲存最終要比對的條碼清單
    final_scanned_codes = []
    
    # === 分頁 1：原本的檔案上傳功能 ===
    with tab1:
        st.write("### 適用於：已經用掃碼槍刷出一整份 Excel 清單")
        uploaded_file = st.file_uploader("請上傳現場掃描找不到的條碼檔案 (Excel 或 CSV)", type=["xlsx", "csv"])
        
        if uploaded_file:
            if uploaded_file.name.endswith('.xlsx'):
                scan_df = pd.read_excel(uploaded_file)
            else:
                scan_df = pd.read_csv(uploaded_file)
                
            scan_col = st.selectbox("請選擇包含「掃描條碼」的欄位", scan_df.columns)
            final_scanned_codes = scan_df[scan_col].dropna().astype(str).str.strip().tolist()

    # === 分頁 2：新增的鏡頭掃描功能 ===
    with tab2:
        st.write("### 適用於：現場拿手機或平板，直接對準商品條碼拍照比對")
        
        # 使用 Session State 記憶已掃描的條碼，避免畫面重新整理時消失
        if 'camera_scanned_codes' not in st.session_state:
            st.session_state.camera_scanned_codes = []
            
        # 啟動相機
        camera_image = st.camera_input("📸 點擊拍照以辨識條碼")
        
        if camera_image is not None:
            # 讀取圖片並進行條碼辨識
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
                st.error("❌ 找不到條碼，請確認條碼清晰且佔據畫面主體再拍一次。")
                
        # 顯示目前已掃描的清單
        if st.session_state.camera_scanned_codes:
            st.write("#### 📝 目前已拍照收集的條碼：")
            st.write(st.session_state.camera_scanned_codes)
            
            if st.button("🗑️ 清空重掃"):
                st.session_state.camera_scanned_codes = []
                st.rerun()
                
            # 將相機收集到的條碼交給後續處理
            final_scanned_codes = st.session_state.camera_scanned_codes

    # === 共用邏輯：資料比對與產出 Excel ===
    st.divider()
    
    if final_scanned_codes:
        st.write("### 📊 比對結果")
        
        # 進行比對
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
