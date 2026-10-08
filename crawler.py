import re
import time
import requests
import gspread
from google.oauth2.service_account import Credentials

SCRAPER_API_KEY = "3cbb08f59c160ba0f2f89b120c8685d0"

def get_gsheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    import streamlit as st
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

def extract_urls(cell_value):
    if not cell_value:
        return []
    return list(set(re.findall(r'https?://[^\s"\')]+', str(cell_value))))

def resolve_redirect_url(url):
    """Giải mã link rút gọn shope.ee thành link shopee.vn chính thức"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        return res.url
    except Exception:
        return url

def scrape_shopee_price_via_proxy(raw_url):
    try:
        # Step 1: Giải mã link rút gọn
        final_url = resolve_redirect_url(raw_url)
        
        # Step 2: Gọi ScraperAPI với render JS
        target_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={requests.utils.quote(final_url)}&render=true"
        
        response = requests.get(target_url, timeout=35)
        if response.status_code == 200:
            html_text = response.text
            
            # Tìm giá trong mã nguồn JSON/HTML của Shopee
            price_matches = re.findall(r'"price":(\d+)', html_text)
            if not price_matches:
                price_matches = re.findall(r'"price_min":(\d+)', html_text)
                
            if price_matches:
                valid_prices = [float(p) for p in price_matches if float(p) > 1000]
                if valid_prices:
                    min_p = min(valid_prices)
                    # Quy đổi giá đơn vị chuẩn
                    return int(min_p / 100000) if min_p > 10000000 else int(min_p)
    except Exception as e:
        print(f"Lỗi cào URL {raw_url}: {e}")
    return None

def run_crawler_process():
    client = get_gsheet_client()
    sheet = client.open("File check gia").worksheet("Data_Gia_Thi_Truong")
    
    # Lấy dữ liệu công thức ô để bắt được các Link đằng sau chữ "Link 1", "Link 2"
    raw_formulas = sheet.get_all_values(value_render_option='FORMULA')
    if not raw_formulas:
        return

    headers = raw_formulas[0]
    
    try:
        col_shopee_link_idx = headers.index("Link_Shopee")
        col_shopee_price_idx = headers.index("Gia_Doi_Thu_Shopee")
    except ValueError as e:
        print(f"Lỗi không tìm thấy đúng tên cột: {e}")
        return

    for row_idx in range(1, len(raw_formulas)):
        row = raw_formulas[row_idx]
        shopee_cell = row[col_shopee_link_idx] if col_shopee_link_idx < len(row) else ""
        urls = extract_urls(shopee_cell)
        
        collected_prices = []
        for url in urls:
            price = scrape_shopee_price_via_proxy(url)
            if price:
                collected_prices.append(price)
            time.sleep(1)

        if collected_prices:
            avg_price = int(sum(collected_prices) / len(collected_prices))
            # Ghi số nguyên thuần túy vào Google Sheet
            sheet.update_cell(row_idx + 1, col_shopee_price_idx + 1, avg_price)
            print(f"✅ Hàng {row_idx + 1}: Ghi thành công giá {avg_price}")

if __name__ == "__main__":
    run_crawler_process()
