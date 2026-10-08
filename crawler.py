import re
import time
import requests
import gspread
from google.oauth2.service_account import Credentials

SCRAPER_API_KEY = "3cbb08f59c160ba0f2f89b120c8685d0"

def get_shopee_price(url):
    """Bóc tách giá đối thủ từ Shopee qua ScraperAPI"""
    try:
        payload = {
            'api_key': SCRAPER_API_KEY,
            'url': url.strip(),
            'keep_headers': 'true'
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        res = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=25)
        if res.status_code == 200:
            text = res.text
            # Trích xuất giá từ cấu trúc dữ liệu Shopee
            prices = re.findall(r'"price":\s*(\d+)', text)
            if not prices:
                prices = re.findall(r'"price_min":\s*(\d+)', text)
            
            if prices:
                valid_prices = []
                for p in prices:
                    val = float(p)
                    if val > 100000000: # Xử lý đơn vị giá Shopee nội bộ (x100.000)
                        val = val / 100000
                    if 5000 <= val <= 50000000:
                        valid_prices.append(val)
                
                if valid_prices:
                    return int(min(valid_prices))
    except Exception as e:
        print(f"Lỗi cào URL {url}: {e}")
    return None

def run_crawler_with_creds(creds_dict, status_callback=None):
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    sheet = client.open("File check gia").worksheet("Data_Gia_Thi_Truong")
    rows = sheet.get_all_values()
    
    if len(rows) < 2:
        return 0

    updated_count = 0
    
    # Duyệt từng dòng từ hàng 2
    for idx, row in enumerate(rows[1:], start=2):
        if len(row) > 8:
            link_content = row[8] # Cột I: Link_Shopee
            
            # Quét tất cả đường link chứa http/https trong ô
            urls = re.findall(r'https?://[^\s,\"\']+', str(link_content))
            
            if not urls:
                continue

            if status_callback:
                status_callback(f"⏳ Đang quét Hàng {idx}: Tìm thấy {len(urls)} link...")

            collected_prices = []
            for url in urls:
                p = get_shopee_price(url)
                if p:
                    collected_prices.append(p)
                time.sleep(1)

            if collected_prices:
                avg_price = int(sum(collected_prices) / len(collected_prices))
                # Ghi kết quả vào Cột J (Cột thứ 10)
                sheet.update_cell(idx, 10, avg_price)
                updated_count += 1
                if status_callback:
                    status_callback(f"✅ Hàng {idx}: Cập nhật giá {avg_price:,.0f}đ")

    return updated_count
