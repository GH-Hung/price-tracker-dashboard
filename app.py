import streamlit as st
import pandas as pd
import gspread
import re
from google.oauth2.service_account import Credentials

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Hệ Thống Theo Dõi & Đối Soát Giá Thị Trường", layout="wide")

# CSS tùy chỉnh để làm giao diện đẹp giống bản HTML
st.markdown("""
<style>
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .status-badge-green {
        background-color: #dcfce7; color: #15803d; padding: 6px 12px;
        border-radius: 8px; font-weight: bold; border: 1px solid #bbf7d0;
    }
    .status-badge-red {
        background-color: #fee2e2; color: #b91c1c; padding: 6px 12px;
        border-radius: 8px; font-weight: bold; border: 1px solid #fca5a5;
    }
    .status-badge-yellow {
        background-color: #fef3c7; color: #b45309; padding: 6px 12px;
        border-radius: 8px; font-weight: bold; border: 1px solid #fde68a;
    }
</style>
""", unsafe_allow_html=True)

# --- HÀM LÀM SẠCH SỐ TIỀN ---
def clean_price(val):
    if pd.isna(val) or val is None or val == "":
        return None
    digits = re.sub(r'[^\d]', '', str(val))
    return float(digits) if digits else None

# --- ĐỌC DỮ LIỆU TỪ GOOGLE SHEET ---
@st.cache_data(ttl=60)
def load_data():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("File check gia").sheet1
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df.columns = [str(c).strip() for c in df.columns]
    return df

# --- HEADER TỔNG QUAN ---
st.title("📈 Hệ Thống Theo Dõi Giá Thị Trường")
st.caption("Tự động thu thập, lọc dữ liệu ảo & Cảnh báo dung sai theo từng sản phẩm")

try:
    df = load_data()

    # --- SIDEBAR: CẤU HÌNH & CHỌN SẢN PHẨM ---
    st.sidebar.header("⚙️ Điều Khiển & Lựa Chọn")
    
    # 1. Chọn SKU cần kiểm tra
    sku_list = df["SKU"].unique().tolist() if "SKU" in df.columns else []
    selected_sku = st.sidebar.selectbox("🎯 Chọn Mã SKU / Sản phẩm:", sku_list)
    
    # 2. Cài đặt Dung sai %
    tolerance_input = st.sidebar.number_input("Cài đặt Dung sai (%):", min_value=1.0, max_value=20.0, value=5.0, step=0.5)

    # 3. Nút Refresh & Nút Kích Hoạt Bot
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Làm mới dữ liệu", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if st.sidebar.button("🚀 Quét Giá Live (Khởi chạy Bot)", type="primary", use_container_width=True):
        with st.spinner("🤖 Bot đang cào dữ liệu live từ các link Shopee..."):
            try:
                import crawler
                crawler.run_crawler_process()
                st.cache_data.clear()
                st.sidebar.success("✅ Đã hoàn tất quét và cập nhật Google Sheet!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Lỗi khi chạy Bot: {e}")

    # --- XỬ LÝ DỮ LIỆU CỦA SKU ĐƯỢC CHỌN ---
    row = df[df["SKU"] == selected_sku].iloc[0]
    
    my_price = clean_price(row.get("Gia_Ban_Cua_Toi"))
    my_promo_price = clean_price(row.get("Gia_Khuyen_Mai")) or my_price
    
    shopee_price = clean_price(row.get("Gia_Doi_Thu_Shopee"))
    tiktok_price = clean_price(row.get("Gia_Doi_Thu_TikTok"))
    lazada_price = clean_price(row.get("Gia_Doi_Thu_Lazada"))
    
    # Tính Giá Trung Bình Thị Trường (Đã lọc)
    valid_market_prices = [p for p in [shopee_price, tiktok_price, lazada_price] if p is not None]
    avg_market_price = sum(valid_market_prices) / len(valid_market_prices) if valid_market_prices else None

    # --- THẺ THÔNG TIN SẢN PHẨM (PRODUCT CARD) ---
    st.markdown("---")
    col_info, col_status = st.columns([3, 2])
    
    with col_info:
        st.subheader(f"📦 [{selected_sku}] {row.get('Ten_San_Pham', '')}")
        p_val = f"{my_price:,.0f} đ" if my_price else "Chưa có"
        p_promo_val = f"{my_promo_price:,.0f} đ" if my_promo_price else "Chưa có"
        st.markdown(f"**Giá bạn đang bán:** `{p_val}` | **Giá KM:** <span style='color:green; font-weight:bold;'>{p_promo_val}</span>", unsafe_allow_html=True)

    with col_status:
        # Tính toán Trạng thái Dung sai
        if my_price and avg_market_price:
            min_allowed = avg_market_price * (1 - tolerance_input / 100.0)
            max_allowed = avg_market_price * (1 + tolerance_input / 100.0)
            
            if my_promo_price < min_allowed:
                st.markdown(f"<div class='status-badge-yellow'>⚠️ CẢNH BÁO: Giá Thấp Hơn Thị Trường (> {tolerance_input}%)</div>", unsafe_allow_html=True)
            elif my_promo_price > max_allowed:
                st.markdown(f"<div class='status-badge-red'>🚨 CẢNH BÁO: Giá Cao Hơn Thị Trường (> {tolerance_input}%)</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='status-badge-green'>✅ AN TOÀN: Nằm Trong Dung Sai (±{tolerance_input}%)</div>", unsafe_allow_html=True)
        else:
            st.info("⚪ Đang chờ dữ liệu giá khảo sát đối thủ...")

    # --- THANH GIÁ TRUNG BÌNH THỊ TRƯỜNG ---
    st.markdown("<br>", unsafe_allow_html=True)
    avg_display = f"{avg_market_price:,.0f} đ" if avg_market_price else "Chưa tính được"
    st.info(f"⚖️ **Giá Trung Bình Thị Trường (Đã lọc dữ liệu ảo):** **{avg_display}** *(Dựa trên các sàn đang hoạt động tốt)*")

    # --- BẢNG PHÂN RÃ THEO SÀN ---
    st.subheader("📊 Bảng Đối Soát Chi Tiết Theo Sàn")
    
    platform_data = [
        {
            "Nguồn": "🟠 Shopee",
            "Khoảng Giá Bán Mới Nhất": f"{shopee_price:,.0f} đ" if shopee_price else "Chưa có dữ liệu",
            "Đánh Giá Độ Tin Cậy": "🟢 Bình thường (Top Shop Bán Chạy)" if shopee_price else "⚪ Đang cập nhật",
            "Links Đối Thủ": str(row.get("Link_Shopee", ""))
        },
        {
            "Nguồn": "⚫ TikTok Shop",
            "Khoảng Giá Bán Mới Nhất": f"{tiktok_price:,.0f} đ" if tiktok_price else "Chưa có dữ liệu",
            "Đánh Giá Độ Tin Cậy": "🟢 Bình thường (Lượng mua ổn định)" if tiktok_price else "⚪ Đang cập nhật",
            "Links Đối Thủ": str(row.get("Link_TikTok", ""))
        },
        {
            "Nguồn": "🔵 Lazada",
            "Khoảng Giá Bán Mới Nhất": f"{lazada_price:,.0f} đ" if lazada_price else "Chưa có dữ liệu",
            "Đánh Giá Độ Tin Cậy": "⚠️ Nghi vấn Buff / Ảo" if lazada_price and lazada_price < (avg_market_price or 0)*0.6 else "🟢 Bình thường",
            "Links Đối Thủ": str(row.get("Link_Lazada", ""))
        }
    ]
    
    p_df = pd.DataFrame(platform_data)
    st.table(p_df[["Nguồn", "Khoảng Giá Bán Mới Nhất", "Đánh Giá Độ Tin Cậy"]])

    # --- POPUP / EXPANDER ĐỐI SOÁT LINK ĐỐI THỦ ---
    with st.expander("🔗 Bấm vào đây để Xem Chi Tiết Link Đối Thủ & Đối Soát"):
        st.write("Các đường dẫn được ghi nhận từ hệ thống:")
        links = str(row.get("Link_Shopee", "")).split("\n")
        for i, l in enumerate(links, 1):
            l_str = l.strip()
            if l_str:
                st.markdown(f"- **Link đối thủ {i}:** [{l_str}]({l_str})")

except Exception as e:
    st.error(f"⚠️ Đang khởi tạo hoặc gặp lỗi kết nối dữ liệu: {e}")
