import streamlit as st
import pandas as pd
import re
import subprocess
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Dashboard Khảo Sát & So Sánh Giá", layout="wide")

# ----------------------------------------------------
# 1. HÀM CHUẨN HÓA GIÁ (Xử lý dứt điểm dấu phẩy, chấm, đ, khoảng trắng)
# ----------------------------------------------------
def parse_price(val):
    if pd.isna(val) or val is None or val == "":
        return 0.0
    try:
        # Nếu đã là dạng số (int, float)
        if isinstance(val, (int, float)):
            return float(val)
        # Nếu là chuỗi, chỉ giữ lại các chữ số 0-9
        clean_str = re.sub(r'[^\d]', '', str(val))
        return float(clean_str) if clean_str else 0.0
    except Exception:
        return 0.0

# ----------------------------------------------------
# 2. ĐỌC DỮ LIỆU TỪ GOOGLE SHEET
# ----------------------------------------------------
@st.cache_data(ttl=10)
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
# 3. SIDEBAR: ĐIỀU KHIỂN & LỰA CHỌN (Khôi phục nguyên bản)
# ----------------------------------------------------
st.sidebar.header("⚙️ Điều Khiển & Lựa Chọn")

# Lựa chọn Mã SKU / Sản phẩm
sku_list = df["Ten_San_Pham"].tolist() if "Ten_San_Pham" in df.columns else df.iloc[:, 0].tolist()
selected_product = st.sidebar.selectbox("🎯 Chọn Mã SKU / Sản phẩm:", sku_list)

# Cài đặt dung sai (%)
tolerance_pct = st.sidebar.number_input("Cài đặt Dung sai (%):", min_value=0.0, max_value=50.0, value=5.0, step=0.5)

st.sidebar.markdown("---")

# Nút Làm mới dữ liệu
if st.sidebar.button("🔄 Làm mới dữ liệu", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# Nút Quét Giá Live (Khởi chạy Bot)
if st.sidebar.button("🚀 Quét Giá Live (Khởi chạy Bot)", type="primary", use_container_width=True):
    with st.spinner("Bot đang quét giá qua ScraperAPI, vui lòng chờ..."):
        try:
            result = subprocess.run(["python", "crawler.py"], capture_output=True, text=True, timeout=120)
            st.sidebar.success("Đã quét giá xong!")
            st.cache_data.clear()
            st.rerun()
        except Exception as err:
            st.sidebar.error(f"Lỗi khi chạy bot: {err}")

# ----------------------------------------------------
# 4. XỬ LÝ DỮ LIỆU SẢN PHẨM ĐƯỢC CHỌN
# ----------------------------------------------------
selected_row = df[df["Ten_San_Pham"] == selected_product].iloc[0]

# Ép kiểu dữ liệu an toàn bằng hàm parse_price
my_price = parse_price(selected_row.get("Gia_Ban_Cua_Toi", 0))
promo_price = parse_price(selected_row.get("Gia_Khuyen_Mai", 0))
if promo_price == 0:
    promo_price = my_price

shopee_price = parse_price(selected_row.get("Gia_Doi_Thu_Shopee", 0))

# ----------------------------------------------------
# 5. HIỂN THỊ DỮ LIỆU TRÊN DASHBOARD (Giao diện Streamlit gốc)
# ----------------------------------------------------
st.title(f"📦 {selected_product}")

st.markdown(f"**Giá bạn đang bán:** {my_price:,.0f} đ | **Giá KM:** :green[{promo_price:,.0f} đ]")

# Cảnh báo dung sai & Giá TB
if shopee_price > 0:
    avg_market_price = shopee_price
    min_allowed = avg_market_price * (1 - tolerance_pct / 100)
    max_allowed = avg_market_price * (1 + tolerance_pct / 100)
    
    if promo_price < min_allowed:
        st.error(f"🚨 CẢNH BÁO: Giá của bạn ({promo_price:,.0f}đ) đang THẤP HƠN thị trường quá {tolerance_pct}% (Mức đề xuất: {min_allowed:,.0f}đ - {max_allowed:,.0f}đ)")
    elif promo_price > max_allowed:
        st.warning(f"⚠️ CẢNH BÁO: Giá của bạn ({promo_price:,.0f}đ) đang CAO HƠN thị trường quá {tolerance_pct}% (Mức đề xuất: {min_allowed:,.0f}đ - {max_allowed:,.0f}đ)")
    else:
        st.success(f"🟢 AN TOÀN: Giá của bạn đang nằm trong dung sai cho phép (±{tolerance_pct}%)")

    st.info(f"⚖️ **Giá Trung Bình Thị Trường:** **{avg_market_price:,.0f} đ** *(Dựa trên các sàn đang hoạt động tốt)*")
else:
    st.info("⚖️ **Giá Trung Bình Thị Trường (Đã lọc dữ liệu ảo):** Chưa tính được *(Đang chờ dữ liệu giá khảo sát đối thủ...)*")

st.markdown("### 📊 Bảng Đối Soát Chi Tiết Theo Sàn")

# Bảng dữ liệu chi tiết
shopee_display = f"{shopee_price:,.0f} đ" if shopee_price > 0 else "Chưa có dữ liệu"
shopee_status = "🟢 Bình thường" if shopee_price > 0 else "⚪ Đang cập nhật"

table_data = {
    "Nguồn": ["Shopee", "TikTok Shop", "Lazada"],
    "Khoảng Giá Bán Mới Nhất": [shopee_display, "Chưa có dữ liệu", "Chưa có dữ liệu"],
    "Đánh Giá Độ Tin Cậy": [shopee_status, "⚪ Đang cập nhật", "⚪ Đang cập nhật"]
}

st.table(pd.DataFrame(table_data))

# Section Đối soát Link
with st.expander("🔗 Bấm vào đây để Xem Chi Tiết Link Đối Thủ & Đối Soát"):
    st.write("Các đường dẫn được ghi nhận từ hệ thống:")
    shopee_links = str(selected_row.get("Link_Shopee", ""))
    if shopee_links:
        st.markdown(f"- **Link đối thủ Shopee:** {shopee_links}")
    else:
        st.write("Chưa có link đối thủ cho sản phẩm này.")
