import streamlit as st
import pandas as pd
import re
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Dashboard Theo Dõi Giá Thị Trường", layout="wide")

# Kết nối Google Sheet
@st.cache_data(ttl=30)
def load_data():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("File check gia").worksheet("Data_Gia_Thi_Truong")
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# Hàm chuẩn hóa số tiền (Xóa dấu phẩy, chấm, chữ)
def parse_price(val):
    if pd.isna(val) or val is None or val == "":
        return 0
    clean_str = re.sub(r'[^\d]', '', str(val))
    return float(clean_str) if clean_str else 0

try:
    df = load_data()
    
    # 1. Đọc dữ liệu SKU hiện tại
    if not df.empty:
        row = df.iloc[0]
        sku_code = str(row.get("SKU", "SP001"))
        product_name = str(row.get("Ten_San_Pham", "Sản phẩm khảo sát"))
        my_price = parse_price(row.get("Gia_Ban_Cua_Toi", 0))
        promo_price = parse_price(row.get("Gia_Khuyen_Mai", 0)) or my_price
        shopee_price = parse_price(row.get("Gia_Doi_Thu_Shopee", 0))
        
        shopee_price_fmt = f"{shopee_price:,.0f}đ".replace(",", ".") if shopee_price > 0 else "Chưa có dữ liệu"

    # 2. Mở file HTML Giao diện gốc để hiển thị
    with open("gemini-code-1791189861546_2.html", "r", encoding="utf-8") as f:
        html_code = f.read()

    # Nhúng khung giao diện HTML chuẩn
    st.components.v1.html(html_code, height=950, scrolling=True)

except Exception as e:
    st.error(f"Lỗi khi đọc dữ liệu hoặc file HTML: {e}")
