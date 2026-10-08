import re
import time
import requests
import gspread
from google.oauth2.service_account import Credentials

SCRAPER_API_KEY = "3cbb08f59c160ba0f2f89b120c8685d0"

# 1. Kết nối Google Sheet
def get_gsheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    import streamlit as st
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

# 2. Trích xuất URL từ các ô dạng Hyperlink ẩn hoặc text
def extract_urls(cell_value):
    if not cell_value:
        return []
    return list(set(re.findall(r'https?://[^\s"\')]+', str(cell_value))))

# 3. Hàm cào giá Shopee qua ScraperAPI (Vượt anti-bot 100%)
def scrape_shopee_price_via_proxy(url):
    try:
        # Đường dẫn gọi qua proxy của ScraperAPI
        target_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={requests.utils.quote(url)}&render=true"
        
        response = requests.get(target_url, timeout=30)
        if response.status_code == 200:
            html_text = response.text
            
            # Tìm giá bằng Regex bóc tách chuỗi JSON/HTML của Shopee
            price_matches = re.findall(r'"price":(\d+)', html_text)
            if not price_matches:
                price_matches = re.findall(r'"price_min":(\d+)', html_text)
                
            if price_matches:
                valid_prices = [float(p) for p in price_matches if float(p) > 1000]
                if valid_prices:
                    min_p = min(valid_prices)
                    # Quy đổi giá đơn vị Shopee (chuẩn hóa giá nguyên)
                    return int(min_p / 100000) if min_p > 10000000 else int(min_p)
    except Exception as e:
        print(f"Lỗi cào URL {url}: {e}")
    return None

# 4. Tiến trình quét toàn bộ hàng trong Google Sheet
def run_crawler_process():
    print("🚀 Bắt đầu tiến trình quét giá qua ScraperAPI...")
    client = get_gsheet_client()
    sheet = client.open("File check gia").worksheet("Data_Gia_Thi_Truong")
    
    # Lấy định dạng công thức để không bị sót Hyperlink ẩn
    raw_formulas = sheet.get_all_values(value_render_option='FORMULA')
    if not raw_formulas:
        return

    headers = raw_formulas[0]
    
    try:
        col_shopee_link_idx = headers.index("Link_Shopee")
        col_shopee_price_idx = headers.index("Gia_Doi_Thu_Shopee")
    except ValueError as e:
        print(f"Lỗi tên cột trên Google Sheet: {e}")
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
            # Tính giá trung bình nếu có nhiều link đối thủ
            avg_price = int(sum(collected_prices) / len(collected_prices))
            sheet_row_number = row_idx + 1
            sheet_col_number = col_shopee_price_idx + 1
            
            # Ghi số nguyên thuần túy vào Google Sheet
            sheet.update_cell(sheet_row_number, sheet_col_number, avg_price)
            print(f"✅ Hàng {sheet_row_number}: Đã cập nhật giá {avg_price:,.0f} đ")
        else:
            print(f"⚠️ Hàng {row_idx + 1}: Chưa lấy được dữ liệu.")

if __name__ == "__main__":
    run_crawler_process()
