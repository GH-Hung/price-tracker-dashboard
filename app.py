import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Hệ Thống Báo Động & So Sánh Giá", layout="wide")

st.title("🖥️ Hệ Thống Báo Động & So Sánh Giá Thị Trường")
st.markdown("Cập nhật và đối soát giá bán với đối thủ trên Shopee, Lazada, TikTok Shop...")

# --- HÀM LÀM SẠCH GIÁ TIỀN ---
def clean_price(val):
    if pd.isna(val) or val is None or val == "":
        return None
    s = str(val).replace("đ", "").replace("Đ", "").replace(",", "").replace(".", "").strip()
    try:
        return float(s)
    except ValueError:
        return None

# --- HÀM KẾT NỐI GOOGLE SHEET ---
@st.cache_data(ttl=5)
def load_data_from_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    
    sheet = client.open("File check gia").sheet1
    data = sheet.get_all_records()
    return pd.DataFrame(data)

try:
    df = load_data_from_sheet()

    # 1. Làm sạch dữ liệu giá của tôi và các sàn đối thủ
    df["Gia_Ban_Clean"] = df["Gia_Ban_Cua_Toi"].apply(clean_price)
    
    # Làm sạch cột giá từng sàn (nếu cột tồn tại)
    for col in ["Gia_Doi_Thu_Shopee", "Gia_Doi_Thu_TikTok", "Gia_Doi_Thu_Lazada", "Gia_Doi_Thu_Ngoai_San"]:
        if col in df.columns:
            df[f"{col}_Clean"] = df[col].apply(clean_price)
        else:
            df[f"{col}_Clean"] = None

    # 2. Bộ lọc chọn Sàn để so sánh
    st.sidebar.header("⚙️ Cấu hình xem dữ liệu")
    platform = st.sidebar.selectbox(
        "Chọn sàn đối thủ để so sánh:",
        ["Tất cả sàn (Lấy giá thấp nhất)", "Shopee", "TikTok Shop", "Lazada", "Ngoài sàn"]
    )

    # Lựa chọn cột giá tương ứng dựa trên sàn được chọn
    def get_target_market_price(row):
        if platform == "Shopee":
            return row["Gia_Doi_Thu_Shopee_Clean"]
        elif platform == "TikTok Shop":
            return row["Gia_Doi_Thu_TikTok_Clean"]
        elif platform == "Lazada":
            return row["Gia_Doi_Thu_Lazada_Clean"]
        elif platform == "Ngoài sàn":
            return row["Gia_Doi_Thu_Ngoai_San_Clean"]
        else:
            # Chọn 'Tất cả': Lấy giá nhỏ nhất khác None giữa các sàn
            prices = [
                row["Gia_Doi_Thu_Shopee_Clean"],
                row["Gia_Doi_Thu_TikTok_Clean"],
                row["Gia_Doi_Thu_Lazada_Clean"],
                row["Gia_Doi_Thu_Ngoai_San_Clean"]
            ]
            valid_prices = [p for p in prices if pd.notna(p) and p is not None]
            return min(valid_prices) if valid_prices else None

    df["Gia_TT_Clean"] = df.apply(get_target_market_price, axis=1)

    # 3. Tính toán Trạng thái Cảnh báo
    def calculate_status(row):
        my_price = row["Gia_Ban_Clean"]
        market_price = row["Gia_TT_Clean"]
        
        tolerance_str = str(row.get("Dung_Sai_Percent", "0")).replace("%", "").strip()
        try:
            tolerance = float(tolerance_str) / 100.0
        except:
            tolerance = 0.0

        if pd.isna(my_price) or pd.isna(market_price) or market_price is None:
            return "⚪ Chưa có dữ liệu"
        
        lower_bound = market_price * (1 - tolerance)
        upper_bound = market_price * (1 + tolerance)
        
        if my_price < lower_bound:
            return "🟡 SKU Giá Thấp"
        elif my_price > upper_bound:
            return "🔴 SKU Giá Cao"
        else:
            return "🟢 SKU Giá Chuẩn"

    df["Trang_Thai"] = df.apply(calculate_status, axis=1)

    # 4. Hiển thị Metrics
    total_sku = len(df)
    normal_count = (df["Trang_Thai"] == "🟢 SKU Giá Chuẩn").sum()
    high_count = (df["Trang_Thai"] == "🔴 SKU Giá Cao").sum()
    low_count = (df["Trang_Thai"] == "🟡 SKU Giá Thấp").sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tổng SKU Theo Dõi", total_sku)
    col2.metric("🟢 SKU Giá Chuẩn", normal_count)
    col3.metric("🔴 SKU Giá Cao", high_count)
    col4.metric("🟡 SKU Giá Thấp", low_count)

    st.markdown("---")
    st.subheader(f"📋 Danh Sách Chi Tiết SKU & Cảnh Báo Giá ({platform})")

    # 5. Bộ lọc Trạng thái
    status_options = ["🟢 SKU Giá Chuẩn", "🔴 SKU Giá Cao", "🟡 SKU Giá Thấp", "⚪ Chưa có dữ liệu"]
    selected_status = st.multiselect("Lọc theo trạng thái:", status_options, default=status_options)

    filtered_df = df[df["Trang_Thai"].isin(selected_status)]

    # 6. Format dữ liệu bảng hiển thị
    display_df = filtered_df.copy()
    display_df["Giá Bán Của Tôi"] = display_df["Gia_Ban_Clean"].apply(lambda x: f"{x:,.0f} đ" if pd.notna(x) else "N/A")
    display_df["Giá Đối Thủ (Đã chọn)"] = display_df["Gia_TT_Clean"].apply(lambda x: f"{x:,.0f} đ" if pd.notna(x) else "Chưa có")

    cols_to_show = ["SKU", "Ten_San_Pham", "Giá Bán Của Tôi", "Giá Đối Thủ (Đã chọn)", "Dung_Sai_Percent", "Trang_Thai", "Tinh_Trang", "Khu_Vuc_Uu_Tien"]
    existing_cols = [c for c in cols_to_show if c in display_df.columns]
    
    st.dataframe(display_df[existing_cols], use_container_width=True)

except Exception as e:
    st.error(f"⚠️ Đã xảy ra lỗi khi kết nối hoặc xử lý dữ liệu: {e}")
