import re
import time
import requests
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

# 1. Kết nối Google Sheet
def get_gsheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    import streamlit as st
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

# 2. Thuật toán lọc giá ảo / Buff đơn
def filter_abnormal_prices(price_list):
    valid_prices = [p for p in price_list if p and p > 0]
    if not valid_prices:
        return None, "⚪ Chưa có dữ liệu"
    
    if len(valid_prices) == 1:
        return valid_prices[0], "🟢 Bình thường"
        
    avg_price = sum(valid_prices) / len(valid_prices)
    cleaned_prices = [p for p in valid_prices if p >= avg_price * 0.5]
    
    status = "⚠️ Nghi vấn Buff / Ảo (Đã lọc)" if len(cleaned_prices) < len(valid_prices) else "🟢 Bình thường"
    final_avg = sum(cleaned_prices) / len(cleaned_prices) if cleaned_prices else avg_price
    return final_avg, status

# 3. Trích xuất tất cả URLs từ ô Google Sheet (kể cả hyperlink ẩn)
def extract_urls(cell_value):
    if not cell_value:
        return []
    cell_str = str(cell_value)
    # Lấy các link dạng http/https trong văn bản hoặc công thức =HYPERLINK("url", "label")
    urls = re.findall(r'https?://[^\s"\')]+', cell_str)
    return list(set(urls))

# 4. Hàm cào giá Shopee (Hỗ trợ link rút gọn shope.ee và link đầy đủ)
def scrape_shopee_price(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
        "Referer": "https://shopee.vn/"
    }
    
    try:
        session = requests.Session()
        # Nếu là link rút gọn, lấy URL gốc sau khi Redirect
        if "shope.ee" in url or "vn.shp.ee" in url:
            res_redirect = session.get(url, headers=headers, allow_redirects=True, timeout=8)
            url = res_redirect.url

        # Cách 1: Giải mã ShopID và ItemID từ URL
        match = re.search(r'i\.(\d+)\.(\d+)', url)
        if not match:
            match = re.search(r'product/(\d+)/(\d+)', url)
            
        if match:
            shop_id, item_id = match.group(1), match.group(2)
            api_url = f"https://shopee.vn/api/v4/item/get?itemid={item_id}&shopid={shop_id}"
            res = session.get(api_url, headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                item = data.get("data", {})
                price_min = item.get("price_min", 0) or item.get("price", 0)
                if price_min > 0:
                    return price_min / 100000.0

        # Cách 2: Bóc tách trực tiếp từ giao diện trang HTML nếu API bị chặn
        res_page = session.get(url, headers=headers, timeout=8)
        if res_page.status_code == 200:
            price_match = re.search(r'"price":(\d+)', res_page.text)
            if price_match:
                p_val = float(price_match.group(1))
                return p_val / 100000.0 if p_val > 1000000 else p_val

    except Exception as e:
        print(f"Lỗi cào URL {url}: {e}")
    return None

# 5. Tiến trình cào và ghi dữ liệu
def run_crawler_process():
    client = get_gsheet_client()
    sheet = client.open("File check gia").worksheet("Data_Gia_Thi_Truong")
    
    # Lấy dữ liệu công thức để trích xuất Hyperlink ẩn
    raw_formulas = sheet.get_all_values(value_render_option='FORMULA')
    if not raw_formulas:
        return

    headers = raw_formulas[0]
    
    try:
        col_shopee_link_idx = headers.index("Link_Shopee")
        col_shopee_price_idx = headers.index("Gia_Doi_Thu_Shopee")
    except ValueError as e:
        print(f"Không tìm thấy cột: {e}")
        return

    print("🚀 Bắt đầu tiến trình quét giá Shopee...")

    for row_idx in range(1, len(raw_formulas)):
        row = raw_formulas[row_idx]
        shopee_cell_value = row[col_shopee_link_idx] if col_shopee_link_idx < len(row) else ""
        
        # Trích xuất các URLs thực sự
        urls = extract_urls(shopee_cell_value)
        collected_prices = []

        for url in urls:
            if "shopee" in url or "shp.ee" in url:
                price = scrape_shopee_price(url)
                if price:
                    collected_prices.append(price)
                time.sleep(0.5)

        # Tính giá trung bình chuẩn
        final_price, status = filter_abnormal_prices(collected_prices)
        
        # Ghi kết quả vào Google Sheet
        sheet_row_number = row_idx + 1
        sheet_col_number = col_shopee_price_idx + 1
        
        if final_price:
            sheet.update_cell(sheet_row_number, sheet_col_number, round(final_price))
            print(f"✅ Hàng {sheet_row_number}: Đã cập nhật giá {final_price:,.0f} đ")
        else:
            print(f"⚠️ Hàng {sheet_row_number}: Không cào được giá từ link.")

if __name__ == "__main__":
    run_crawler_process()
