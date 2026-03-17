import streamlit as st
import pandas as pd
import io

# 設定頁面標題
st.set_page_config(page_title="POS 商品快速建檔比對工具", layout="wide")
st.title("📦 POS 商品快速建檔比對工具")

# --- 1. 自動讀取您專屬的 Google 雲端完整資料表 ---
# 這是您提供的雲端硬碟檔案轉換後的直接下載連結
GDRIVE_DIRECT_URL = "https://drive.google.com/uc?id=1Efffq2OuR3y1qI3Xnngw974wkzJXZub1"

@st.cache_data(ttl=600) # 快取資料 10 分鐘，加快重複操作的速度
def load_master_data():
    try:
        # 直接從 Google 雲端讀取 Excel 檔案
        df = pd.read_excel(GDRIVE_DIRECT_URL)
        # 確保助記碼皆為字串格式且去除空白，方便後續比對
        if '助記碼' in df.columns:
            df['助記碼'] = df['助記碼'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"讀取雲端資料庫失敗，請確認檔案共用權限是否設定為「知道連結的任何人均可查看」\n錯誤訊息：{e}")
        return None

# 載入雲端資料
with st.spinner('🔄 正在從 Google 雲端同步「完整商品資料表」...'):
    master_df = load_master_data()

if master_df is not None:
    st.success(f"✅ 成功載入雲端完整資料庫！目前共有 {len(master_df)} 筆商品。")
    
    # --- 2. 使用者上傳現場掃描的條碼清單 ---
    st.write("### 步驟 1：上傳現場掃描條碼")
    uploaded_file = st.file_uploader("請上傳現場掃描找不到的條碼檔案 (Excel 或 CSV)", type=["xlsx", "csv"])
    
    if uploaded_file:
        # 讀取上傳的檔案
        if uploaded_file.name.endswith('.xlsx'):
            scan_df = pd.read_excel(uploaded_file)
        else:
            scan_df = pd.read_csv(uploaded_file)
            
        # 讓使用者選擇哪一個欄位是「條碼」
        scan_col = st.selectbox("請選擇包含「掃描條碼」的欄位", scan_df.columns)
        scanned_codes = scan_df[scan_col].dropna().astype(str).str.strip().tolist()
        
        # --- 3. 進行資料比對 ---
        st.write("### 步驟 2：比對結果")
        
        # 以「助記碼」進行比對挑出商品
        matched_df = master_df[master_df['助記碼'].isin(scanned_codes)].copy()
        found_codes = matched_df['助記碼'].tolist()
        
        # 找出沒有在完整資料庫中的條碼
        missing_codes = list(set(scanned_codes) - set(found_codes))
        
        col1, col2 = st.columns(2)
        col1.metric("✅ 成功比對並找出的商品數", len(matched_df))
        col2.metric("❌ 雲端資料庫也找不到的條碼數", len(missing_codes))
        
        if missing_codes:
            st.warning("⚠️ 以下條碼在雲端的「完整商品資料表」中也找不到，可能需要人工新增：")
            st.write(missing_codes)
            
        # --- 4. 產生 POS 匯入格式的 Excel ---
        if not matched_df.empty:
            st.write("### 步驟 3：下載 POS 匯入檔")
            
            # 準備 POS 範本需要的欄位順序
            output_columns = ['商品名稱✳️', '助記碼', '項目別名', '商品條碼✳️', '分類✳️', '規格', '銷售價格✳️', '成本價', '計價方式✳', '單位✳️', '上架狀態✳️', '描述']
            
            # POS 系統規定的前三行說明與標題
            instruction_row = ["1、帶✳️的欄位為必填\n2、單次最多導入2000條商品，超過按照表格順序，只導入前2000條\n3、多規格商品，表格中的商品名稱/分類/計價方式/單位元/上架狀態必須相同，若不同則認為是不同商品，可能導入失敗"] + [""] * 11
            header_row = output_columns
            desc_row = ["支援漢字/字母/數字及其它國際語言，最多50位", "", "支援漢字/字母/數字及其它國際語言，最多50位", "必須要選擇一種，可以系統生成，也可以為無碼商品，若需要導入條碼時，條碼必須為 5-14 位的數字", "必填，必須是店鋪已經新增的分類名稱", "不填寫時默認單規格商品，如果同一個商品有多個規格，請填寫相同的商品名稱/分類/計價方式/單位元/上架狀態", "必填，只能輸入正數，最多兩位小數，範圍0-99999999.99", "選填，只能輸入正數，最多兩位小數，範圍0-99999999.99 ，不填默認為0", "計件/稱重", "稱重商品的單位只能為g/kg，計件不限制，最多10個字", "選擇上架/下架", "可選，若留白則預設為空，最多 300 字元。"]
            
            # 確保比對出的資料只留下需要的欄位 (若雲端資料表缺少某些欄位，補上空值以符合格式)
            for col in output_columns:
                if col not in matched_df.columns:
                    matched_df[col] = ""
            matched_data_only = matched_df[output_columns]
            
            # 將說明行與資料合併
            final_output = pd.DataFrame([instruction_row, header_row, desc_row])
            final_output = pd.concat([final_output, pd.DataFrame(matched_data_only.values)], ignore_index=True)
            
            # 寫入 Excel 的記憶體緩衝區
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                # header=False, index=False 確保不會寫入多餘的 Pandas 預設索引跟欄位名
                final_output.to_excel(writer, index=False, header=False, sheet_name="導入範本")
            
            st.download_button(
                label="📥 點此下載「POS 匯入專用」Excel 檔",
                data=buffer.getvalue(),
                file_name="POS_待匯入商品_已比對.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )