import streamlit as st
import pandas as pd
import re
import gspread
from google.oauth2.service_account import Credentials
import crawler

st.set_page_config(page_title="Dashboard Khảo Sát & So Sánh Giá", layout="wide")

# ----------------------------------------------------
# 1. HÀM CHUẨN HÓA GIÁ
# ----------------------------------------------------
def parse_price(val):
    if pd.isna(val) or val is None or str(val).strip() == "":
        return 0.0
    try:
        if isinstance(val, (int, float)):
            return float(val)
        clean_str = re.sub(r'[^\d]', '', str(val))
        return float(clean_str) if clean_str else 0.0
    except Exception:
        return 0.0

# ----------------------------------------------------
# 2. ĐỌC DỮ LIỆU TỪ GOOGLE SHEET
# ----------------------------------------------------
@st.cache_data(ttl=3)
def load_data():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("File check gia").worksheet("Data_Gia_Thi_Truong")
    
    rows = sheet.get_all_values()
    if not rows or len(rows) < 2:
        return pd.DataFrame()
    
    headers = [str(h).strip() for h in rows[0]]
    df = pd.DataFrame(rows[1:], columns=headers)
    return df

try:
    df = load_data()
except Exception as e:
    st.error(f"Lỗi kết nối Google Sheet: {e}")
    st.stop()

if df.empty:
    st.warning("Chưa có dữ liệu trong Google Sheet!")
    st.stop()

# ----------------------------------------------------
# 3. SIDEBAR: ĐIỀU KHIỂN & LỰA CHỌN
# ----------------------------------------------------
st.sidebar.header("⚙️ Điều Khiển & Lựa Chọn")

product_col = None
for col in df.columns:
    if "Ten_San_Pham" in col or "San_Pham" in col:
        product_col = col
        break
if not product_col:
    product_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

sku_list = df[product_col].astype(str).tolist()
selected_product = st.sidebar.selectbox("🎯 Chọn Mã SKU / Sản phẩm:", sku_list)
tolerance_pct = st.sidebar.number_input("Cài đặt Dung sai (%):", min_value=0.0, max_value=50.0, value=5.0, step=0.5)

st.sidebar.markdown("---")

# Nút Làm mới dữ liệu
if st.sidebar.button("🔄 Làm mới dữ liệu", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# Nút Quét Giá Live (Đã khôi phục)
if st.sidebar.button("🚀 Quét Giá Live (Khởi chạy Bot)", type="primary", use_container_width=True):
    with st.spinner("🤖 Bot đang bóc tách link & quét giá Shopee qua ScraperAPI... Vui lòng chờ..."):
        try:
            crawler.run_crawler_with_creds(dict(st.secrets["gcp_service_account"]))
            st.sidebar.success("✅ Đã quét giá thành công và cập nhật vào Google Sheet!")
            st.cache_data.clear()
            st.rerun()
        except Exception as err:
            st.sidebar.error(f"❌ Lỗi khi quét giá: {err}")

# ----------------------------------------------------
# 4. XỬ LÝ DỮ LIỆU DÒNG ĐƯỢC CHỌN
# ----------------------------------------------------
selected_df = df[df[product_col].astype(str) == selected_product]
if selected_df.empty:
    st.error("Không tìm thấy dữ liệu cho sản phẩm đã chọn.")
    st.stop()

selected_row = selected_df.iloc[0]

my_price_raw = selected_row.iloc[2] if len(selected_row) > 2 else 0
shopee_price_raw = selected_row.iloc[9] if len(selected_row) > 9 else 0

my_price = parse_price(my_price_raw)
promo_price = parse_price(selected_row.iloc[3]) if len(selected_row) > 3 and parse_price(selected_row.iloc[3]) > 0 else my_price
shopee_price = parse_price(shopee_price_raw)

# ----------------------------------------------------
# 5. HIỂN THỊ DỮ LIỆU DUNG SAI & BẢNG SO SÁNH
# ----------------------------------------------------
st.title(f"📦 {selected_product}")
st.markdown(f"**Giá bạn đang bán:** {my_price:,.0f} đ | **Giá KM:** :green[{promo_price:,.0f} đ]")

if shopee_price > 0:
    avg_market_price = shopee_price
    min_allowed = avg_market_price * (1 - tolerance_pct / 100)
    max_allowed = avg_market_price * (1 + tolerance_pct / 100)
    
    st.info(f"⚖️ **Giá Trung Bình Thị Trường:** **{avg_market_price:,.0f} đ** *(Dựa trên dữ liệu khảo sát đối thủ)*")
    
    if promo_price < min_allowed:
        st.error(f"🚨 **CẢNH BÁO:** Giá của bạn ({promo_price:,.0f}đ) đang **THẤP HƠN** thị trường quá {tolerance_pct}% (Khung giá an toàn: {min_allowed:,.0f}đ - {max_allowed:,.0f}đ)")
    elif promo_price > max_allowed:
        st.warning(f"⚠️ **CẢNH BÁO:** Giá của bạn ({promo_price:,.0f}đ) đang **CAO HƠN** thị trường quá {tolerance_pct}% (Khung giá an toàn: {min_allowed:,.0f}đ - {max_allowed:,.0f}đ)")
    else:
        st.success(f"🟢 **AN TOÀN:** Giá của bạn nằm trong dung sai cho phép (±{tolerance_pct}%)")
else:
    st.info("⚖️ **Giá Trung Bình Thị Trường:** Chưa tính được *(Chưa có dữ liệu giá đối thủ cho sản phẩm này)*")

st.markdown("### 📊 Bảng Đối Soát Chi Tiết Theo Sàn")

shopee_display = f"{shopee_price:,.0f} đ" if shopee_price > 0 else "Chưa có dữ liệu"
shopee_status = "🟢 Bình thường" if shopee_price > 0 else "⚪ Đang cập nhật"

table_df = pd.DataFrame({
    "Nguồn": ["Shopee", "TikTok Shop", "Lazada"],
    "Khoảng Giá Bán Mới Nhất": [shopee_display, "Chưa có dữ liệu", "Chưa có dữ liệu"],
    "Đánh Giá Độ Tin Cậy": [shopee_status, "⚪ Đang cập nhật", "⚪ Đang cập nhật"]
})

st.table(table_df)

with st.expander("🔗 Bấm vào đây để Xem Chi Tiết Link Đối Thủ & Đối Soát"):
    shopee_link_val = selected_row.iloc[8] if len(selected_row) > 8 else "Chưa có dữ liệu"
    st.markdown(f"- **Link đối thủ Shopee:** {shopee_link_val}")
