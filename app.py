import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIG TRANG WEB ---
st.set_page_config(
    page_title="Dashboard So Sánh Giá Linh Kiện",
    page_icon="🖥️",
    layout="wide"
)

st.title("🖥️ Hệ Thống Báo Động & So Sánh Giá Thị Trường")
st.markdown("Cập nhật và đối soát giá bán với đối thủ trên Shopee, Lazada, TikTok Shop...")

# --- HÀM KẾT NỐI GOOGLE SHEET ---
@st.cache_data(ttl=600)  # Cache 10 phút để tối ưu tốc độ
def load_data_from_sheet():
    # Lấy thông tin xác thực từ Streamlit Secrets
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    
    # Mở Google Sheet (Thay tên file của bạn vào đây)
    sheet = client.open("File check gia").sheet1
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# --- XỬ LÝ DỮ LIỆU & TÍNH TOÁN ---
try:
    df = load_data_from_sheet()
    
    # Làm sạch dữ liệu số
    df['Gia_Ban_Cua_Toi'] = pd.to_numeric(df['Gia_Ban_Cua_Toi'], errors='coerce')
    df['Dung_Sai_Percent'] = pd.to_numeric(df['Dung_Sai_Percent'].astype(str).str.rstrip('%'), errors='coerce') / 100

    # Giả lập giá trung bình thị trường cào được (sẽ nối với Scraper ở Bước 2.1)
    # Thực tế cột này sẽ do Bot cào về và ghi vào Sheet
    if 'Gia_Thi_Truong_TB' not in df.columns:
        df['Gia_Thi_Truong_TB'] = df['Gia_Ban_Cua_Toi'] * 0.98 # Ví dụ mẫu

    # --- TÍNH TOÁN CẢNH BÁO MÀU SẮC ---
    def check_status(row):
        price_me = row['Gia_Ban_Cua_Toi']
        price_market = row['Gia_Thi_Truong_TB']
        tolerance = row['Dung_Sai_Percent']
        
        if pd.isna(price_market) or price_market == 0:
            return "⚪ Chưa có dữ liệu"
        
        diff_percent = (price_me - price_market) / price_market
        
        if diff_percent > tolerance:
            return "🔴 Giá Cao (Khó Bán)"
        elif diff_percent < -tolerance:
            return "🟡 Giá Thấp (Hao Lợi Nhuận)"
        else:
            return "🟢 Giá Chuẩn"

    df['Trang_Thai'] = df.apply(check_status, axis=1)

    # --- KHU VỰC THỐNG KÊ NHANH (METRICS) ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tổng SKU Theo Dõi", len(df))
    col2.metric("🟢 SKU Giá Chuẩn", len(df[df['Trang_Thai'].str.contains("🟢")]))
    col3.metric("🔴 SKU Giá Cao", len(df[df['Trang_Thai'].str.contains("🔴")]))
    col4.metric("🟡 SKU Giá Thấp", len(df[df['Trang_Thai'].str.contains("🟡")]))

    st.divider()

    # --- BẢNG DỮ LIỆU HIỂN THỊ MAIN DASHBOARD ---
    st.subheader("📋 Danh Sách Chi Tiết SKU & Cảnh Báo Giá")
    
    # Bộ lọc nhanh
    status_filter = st.multiselect("Lọc theo trạng thái:", options=df['Trang_Thai'].unique(), default=df['Trang_Thai'].unique())
    filtered_df = df[df['Trang_Thai'].isin(status_filter)]

    # Định dạng hiển thị bảng
    st.dataframe(
        filtered_df[[
            'SKU', 'Ten_San_Pham', 'Gia_Ban_Cua_Toi', 
            'Gia_Thi_Truong_TB', 'Dung_Sai_Percent', 'Trang_Thai', 
            'Tinh_Trang', 'Khu_Vuc_Uu_Tien', 'Link_Shopee'
        ]],
        column_config={
            "Gia_Ban_Cua_Toi": st.column_config.NumberColumn("Giá Bán Của Tôi", format="%d đ"),
            "Gia_Thi_Truong_TB": st.column_config.NumberColumn("Giá TT Trung Bình", format="%d đ"),
            "Dung_Sai_Percent": st.column_config.NumberColumn("Dung Sai", format="%.0f%%"),
            "Link_Shopee": st.column_config.LinkColumn("Link Shopee Đối Thủ"),
        },
        use_container_width=True,
        hide_index=True
    )

except Exception as e:
    st.error(f"⚠️ Chưa kết nối được dữ liệu Google Sheet. Vui lòng kiểm tra lại thiết lập JSON Secret! Lỗi: {e}")
