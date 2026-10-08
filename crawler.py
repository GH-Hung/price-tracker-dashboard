import re
import time
import requests
import gspread
from google.oauth2.service_account import Credentials

SCRAPER_API_KEY = "3cbb08f59c160ba0f2f89b120c8685d0"

def extract_ids_from_url(url):
    """Trích xuất itemid và shopid từ đường link Shopee"""
    match = re.search(r'i\.(\d+)\.(\d+)', url)
    if match:
        return match.group(1), match.group(2)
    
    # Dạng link khác: -i.12345.67890
    match2 = re.search(r'-i\.(\d+)\.(\d+)', url)
    if match2:
        return match2.group(1), match2.group(2)
        
    return None, None

def get_shopee_price(url):
    clean_url = url.strip()
    shop_id, item_id = extract_ids_from_url(clean_url)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": clean_url,
        "X-Requested-With": "XMLHttpRequest"
    }

    # Cach 1: Gọi API Shopee nội bộ trực tiếp
    if shop_id and item_id:
        shopee_api_url = f"https://shopee.vn/api/v4/item/get?itemid={item_id}&shopid={shop_id}"
        try:
            res = requests.get(shopee_api_url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                item = data.get('data', {})
                price_raw = item.get('price') or item.get('price_min') or item.get('price_before_discount')
                if price_raw:
                    val = float(price_raw)
                    if val > 1000000:
                        val = val / 100000
                    if 5000 <= val <= 50000000:
                        return int(val)
        except Exception as e:
            print(f"Lỗi API Shopee: {e}")

    # Cach 2: Dùng ScraperAPI với cấu hình render trang web nâng cao
    try:
        payload = {
            'api_key': SCRAPER_API_KEY,
            'url': clean_url,
            'render': 'true',
            'country_code': 'vn'
        }
        res = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=25)
        if res.status_code == 200:
            text = res.text
            # Bóc tách bằng Regex các dạng hiển thị giá Shopee
            prices = re.findall(r'"price":\s*(\d+)', text)
            if not prices:
                prices = re.findall(r'"price_min":\s*(\d+)', text)
            if not prices:
                # Tìm dạng số tiền VND trong HTML (vd: 145.000 hoặc 145000)
                prices = re.findall(r'(\d{1,3}(?:\.\d{3})+)\s*(?:₫|đ|VND)', text, re.IGNORECASE)

            for p in prices:
                clean_p = str(p).replace('.', '').replace(',', '')
                if clean_p.isdigit():
                    val = float(clean_p)
                    if val > 100000000:
                        val = val / 100000
                    if 5000 <= val <= 50000000:
                        return int(val)
    except Exception as e:
        print(f"Lỗi ScraperAPI: {e}")

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
    
    for idx, row in enumerate(rows[1:], start=2):
        if len(row) > 8:
            link_content = row[8] # Cột I: Link_Shopee
            
            urls = re.findall(r'https?://[^\s,\"\']+', str(link_content))
            
            if not urls:
                continue

            if status_callback:
                status_callback(f"⏳ Đang quét Hàng {idx}: Bắt đầu cào {len(urls)} link Shopee...")

            collected_prices = []
            for url in urls:
                p = get_shopee_price(url)
                if p:
                    collected_prices.append(p)
                    if status_callback:
                        status_callback(f"🎯 Hàng {idx}: Lấy thành công giá {p:,.0f}đ")
                time.sleep(1)

            if collected_prices:
                avg_price = int(sum(collected_prices) / len(collected_prices))
                # Ghi giá trung bình vào Cột J (Cột 10)
                sheet.update_cell(idx, 10, avg_price)
                updated_count += 1
                if status_callback:
                    status_callback(f"✅ Hàng {idx}: Đã ghi giá {avg_price:,.0f}đ vào Google Sheet")

    return updated_count
