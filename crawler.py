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

# 3. Hàm cào giá Shopee với Header mô phỏng trình duyệt thực tế
def scrape_shopee_price(url):
    url = url.strip()
    if not url.startswith("http"):
        return None
        
    try:
        # Giải nén link nếu là link rút gọn shope.ee
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://shopee.vn/"
        }
        
        # Bóc tách ShopID và ItemID
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
    except Exception as e:
        print(f"Lỗi cào URL {url}: {e}")
    return None

# 4. Tiến trình quét & cập nhật Google Sheet
def run_crawler_process():
    client = get_gsheet_client()
    sheet = client.open("File check gia").sheet1
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    # Tìm thứ tự cột
    headers = sheet.row_values(1)
    
    def get_col_index(col_name):
        try:
            return headers.index(col_name) + 1
        except ValueError:
            return None

    col_shopee_price = get_col_index("Gia_Doi_Thu_Shopee")
    
    for idx, row in df.iterrows():
        shopee_links = str(row.get("Link_Shopee", "")).split("\n")
        collected_prices = []
        
        for link in shopee_links:
            if "shopee.vn" in link or "shope.ee" in link:
                price = scrape_shopee_price(link)
                if price:
                    collected_prices.append(price)
                time.sleep(0.5)
                
        final_price, status = filter_abnormal_prices(collected_prices)
        
        row_number = idx + 2
        if final_price and col_shopee_price:
            sheet.update_cell(row_number, col_shopee_price, final_price)

if __name__ == "__main__":
    run_crawler_process()
