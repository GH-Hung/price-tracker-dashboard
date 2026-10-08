import streamlit as st
import pandas as pd
import re
import subprocess
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Dashboard Khảo Sát & So Sánh Giá", layout="wide")

# ----------------------------------------------------
# 1. HÀM CHUẨN HÓA GIÁ (Xử lý dấu phẩy, chấm, chuỗi)
# ----------------------------------------------------
def parse_price(val):
    if pd.isna(val) or val is None or val == "":
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
@st.cache_data(ttl=5)
def load_data():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("File check gia").worksheet("Data_Gia_Thi_Truong")
    data = sheet.get_all_records()
    return pd.DataFrame(data)

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

sku_column = "Ten_San_Pham" if "Ten_San_Pham" in df.columns else df.columns[0]
sku_list = df[sku_column].astype(str).tolist()

selected_product = st.sidebar.selectbox("🎯 Chọn Mã SKU / Sản phẩm:", sku_list)
tolerance_pct = st.sidebar.number_input("Cài đặt Dung sai (%):", min_value=0.0, max_value=50.0, value=5.0, step=0.5)

st.sidebar.markdown("---")

if st.sidebar.button("🔄 Làm mới dữ liệu", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

if st.sidebar.button("🚀 Quét Giá Live (Khởi chạy Bot)", type="primary", use_container_width=True):
    with st.spinner("Bot đang quét giá qua ScraperAPI, vui lòng chờ..."):
        try:
            result = subprocess.run(["python", "crawler.py"], capture_output=True, text=True, timeout=120)
            st.sidebar.success("Đã hoàn tất tiến trình quét giá!")
            st.cache_data.clear()
            st.rerun()
        except Exception as err:
            st.sidebar.error(f"Lỗi khi chạy bot: {err}")

# ----------------------------------------------------
# 4. BÓC TÁCH DỮ LIỆU SẢN PHẨM ĐƯỢC CHỌN
# ----------------------------------------------------
selected_row = df[df[sku_column].astype(str) == selected_product].iloc[0]

my_price = parse_price(selected_row.get("Gia_Ban_Cua_Toi", 0))
promo_price = parse_price(selected_row.get("Gia_Khuyen_Mai", 0))
if promo_price == 0:
    promo_price = my_price

shopee_price = parse_price(selected_row.get("Gia_Doi_Thu_Shopee", 0))

# ----------------------------------------------------
# 5. HIỂN THỊ CÁC THÔNG SỐ SO SÁNH
# ----------------------------------------------------
st.title(f"📦 {selected_product}")
st.markdown(f"**Giá bạn đang bán:** {my_price:,.0f} đ | **Giá KM:** :green[{promo_price:,.0f} đ]")

if shopee_price > 0:
    avg_market_price = shopee_price
    min_allowed = avg_market_price * (1 - tolerance_pct / 100)
    max_allowed = avg_market_price * (1 + tolerance_pct / 100)
    
    st.info(f"⚖️ **Giá Trung Bình Thị Trường:** **{avg_market_price:,.0f} đ** *(Dựa trên dữ liệu thu thập)*")
    
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
    shopee_links = str(selected_row.get("Link_Shopee", ""))
    if shopee_links:
        st.markdown(f"- **Link đối thủ Shopee:** {shopee_links}")
    else:
        st.write("Chưa có thông tin link đối thủ.")
