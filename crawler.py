import re
import time
import requests
import gspread
from google.oauth2.service_account import Credentials

SCRAPER_API_KEY = "3cbb08f59c160ba0f2f89b120c8685d0"

def get_shopee_price(url):
    """
    Lấy giá Shopee chuẩn xác bằng cách phân tích ItemID/ShopID 
    hoặc dùng ScraperAPI render thông minh.
    """
    clean_url = url.strip()
    
    # ------------------------------------------------------------------
    # PHƯƠNG PHÁP 1: Lấy thông qua Shopee API bằng ShopID & ItemID
    # ------------------------------------------------------------------
    match = re.search(r'i\.(\d+)\.(\d+)', clean_url)
    if match:
        shop_id = match.group(1)
        item_id = match.group(2)
        shopee_api_url = f"https://shopee.vn/api/v4/item/get?itemid={item_id}&shopid={shop_id}"
        
        try:
            # Gọi API Shopee thông qua ScraperAPI
            payload = {
                'api_key': SCRAPER_API_KEY,
                'url': shopee_api_url,
                'country_code': 'vn'
            }
            res = requests.get('http://api.scraperapi.com', params=payload, timeout=20)
            if res.status_code == 200:
                data = res.json()
                item_data = data.get('data', {})
                
                # Ưu tiên lấy giá bán thực tế (price hoặc price_min)
                price_raw = item_data.get('price') or item_data.get('price_min') or item_data.get('price_before_discount')
                if price_raw and float(price_raw) > 0:
                    val = float(price_raw)
                    # Shopee API quy đổi 1 VND = 100,000 đơn vị nội bộ
                    if val > 1000000:
                        val = val / 100000
                    return int(val)
        except Exception as e:
            print(f"Lỗi gọi Shopee API trực tiếp: {e}")

    # ------------------------------------------------------------------
    # PHƯƠNG PHÁP 2: Fallback Bóc tách HTML qua ScraperAPI JS Render
    # ------------------------------------------------------------------
    try:
        payload = {
            'api_key': SCRAPER_API_KEY,
            'url': clean_url,
            'render': 'true',
            'country_code': 'vn'
        }
        res = requests.get('http://api.scraperapi.com', params=payload, timeout=30)
        if res.status_code == 200:
            text = res.text
            
            # Quét Regex tìm chuỗi giá tiền trong mã nguồn
            prices = re.findall(r'"price":\s*(\d+)', text)
            if not prices:
                prices = re.findall(r'"price_min":\s*(\d+)', text)
            if not prices:
                prices = re.findall(r'(\d{2,3}\.\d{3})\s*₫', text) # Tìm dạng 145.000 ₫
            
            valid_prices = []
            for p in prices:
                clean_p = str(p).replace('.', '').replace(',', '')
                if clean_p.isdigit():
                    val = float(clean_p)
                    if val > 100000000:
                        val = val / 100000
                    if 5000 <= val <= 50000000:
                        valid_prices.append(val)
            
            if valid_prices:
                return int(min(valid_prices))
    except Exception as e:
        print(f"Lỗi cào HTML URL {clean_url}: {e}")
        
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
                        status_callback(f"🎯 Hàng {idx}: Lấy được giá {p:,.0f}đ từ link...")
                time.sleep(1)

            if collected_prices:
                avg_price = int(sum(collected_prices) / len(collected_prices))
                # Ghi kết quả vào Cột J (Cột 10)
                sheet.update_cell(idx, 10, avg_price)
                updated_count += 1
                if status_callback:
                    status_callback(f"✅ Hàng {idx}: ĐÃ GHI GIÁ {avg_price:,.0f}đ VÀO GOOGLE SHEET")

    return updated_count
