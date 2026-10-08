import re
import time
import requests
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

# 1. Kết nối Google Sheet
def get_gsheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    # Tải credentials từ Streamlit Secrets hoặc file json
    import streamlit as st
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

# 2. Thuật toán lọc giá ảo / Buff đơn
def filter_abnormal_prices(price_list):
    """
    Loại bỏ mức giá bất thường (ví dụ quá thấp do mua kèm đèo/buff ảo)
    Trả về (Giá trung bình chuẩn, Trạng thái cảnh báo)
    """
    valid_prices = [p for p in price_list if p and p > 0]
    if not valid_prices:
        return None, "⚪ Chưa có dữ liệu"
    
    # Nếu chỉ có 1 giá
    if len(valid_prices) == 1:
        return valid_prices[0], "🟢 Bình thường"
        
    # Tính trung bình & lọc outlier đơn giản
    avg_price = sum(valid_prices) / len(valid_prices)
    cleaned_prices = [p for p in valid_prices if p >= avg_price * 0.5] # Loại bỏ giá bé hơn 50% trung bình (nghi vấn buff)
    
    if len(cleaned_prices) < len(valid_prices):
        status = "⚠️ Nghi vấn Buff / Ảo (Đã lọc nhiễu)"
    else:
        status = "🟢 Bình thường"
        
    final_avg = sum(cleaned_prices) / len(cleaned_prices) if cleaned_prices else avg_price
    return final_avg, status

# 3. Hàm cào giá Shopee từ Link (Sử dụng API Public/Header)
def scrape_shopee_price(url):
    try:
        # Bóc tách ItemID và ShopID từ đường dẫn Shopee
        match = re.search(r'i\.(\d+)\.(\d+)', url)
        if not match:
            # Tìm dạng link sp: shopee.vn/product/shopid/itemid
            match = re.search(r'product/(\d+)/(\d+)', url)
            
        if match:
            shop_id, item_id = match.group(1), match.group(2)
            api_url = f"https://shopee.vn/api/v4/item/get?itemid={item_id}&shopid={shop_id}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            res = requests.get(api_url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                item = data.get("data", {})
                price = item.get("price", 0) / 100000 # Shopee nhân giá trị thực với 100,000
                return price
    except Exception as e:
        print(f"Lỗi cào link {url}: {e}")
    return None

# 4. Tiến trình chạy quét toàn bộ Google Sheet
def run_crawler_process():
    client = get_gsheet_client()
    sheet = client.open("File check gia").sheet1
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    print("🚀 Đang khởi chạy Bot cào giá...")
    
    for idx, row in df.iterrows():
        shopee_links = str(row.get("Link_Shopee", "")).split("\n")
        collected_prices = []
        
        for link in shopee_links:
            link = link.strip()
            if "shopee.vn" in link:
                price = scrape_shopee_price(link)
                if price:
                    collected_prices.append(price)
                time.sleep(1) # Tránh bị rate-limit
                
        # Tính toán giá chuẩn sau khi lọc nhiễu
        final_price, status = filter_abnormal_prices(collected_prices)
        
        if final_price:
            # Ghi kết quả vào dòng tương ứng trên Google Sheet (Cột J - Gia_Doi_Thu_Shopee)
            row_number = idx + 2 # Hàng trong Sheet bắt đầu từ 2
            sheet.update_cell(row_number, 10, final_price) # Cột 10 là Gia_Doi_Thu_Shopee
            print(f"Row {row_number} [{row.get('SKU')}]: Giá Shopee = {final_price:,.0f} đ ({status})")

if __name__ == "__main__":
    run_crawler_process()