import re
import time
import requests
import hmac
import hashlib
import gspread
from google.oauth2.service_account import Credentials

SCRAPER_API_KEY = "3cbb08f59c160ba0f2f89b120c8685d0"

def extract_item_and_shop_id(url):
    """Trích xuất shop_id và item_id từ URL Shopee bất kỳ"""
    match = re.search(r'i\.(\d+)\.(\d+)', url) or re.search(r'-i\.(\d+)\.(\d+)', url)
    if match:
        return match.group(1), match.group(2)
    return None, None

def get_real_shopee_price(url, partner_config=None):
    """
    Hàm lấy giá THẬT 100%. Trả về None nếu bị chặn, tuyệt đối KHÔNG sinh giá giả.
    """
    clean_url = url.strip()
    shop_id, item_id = extract_item_and_shop_id(clean_url)

    # 1. Nếu cấu hình Shopee Partner API
    if partner_config and shop_id and item_id:
        try:
            partner_id = int(partner_config.get("partner_id"))
            partner_key = partner_config.get("partner_key")
            timestamp = int(time.time())
            path = "/api/v2/item/get_item_base_info"
            
            # Tạo signature chuẩn Shopee Open API v2
            base_string = f"{partner_id}{path}{timestamp}"
            sign = hmac.new(partner_key.encode('utf-8'), base_string.encode('utf-8'), hashlib.sha256).hexdigest()
            
            api_url = f"https://partner.shopeemobile.com{path}?partner_id={partner_id}&timestamp={timestamp}&sign={sign}&item_id_list={item_id}"
            res = requests.get(api_url, timeout=10)
            if res.status_code == 200:
                res_json = res.json()
                items = res_json.get("response", {}).get("item_list", [])
                if items:
                    price_info = items[0].get("price_info", [])
                    if price_info:
                        return int(price_info[0].get("current_price"))
        except Exception as e:
            print(f"Lỗi Partner API: {e}")

    # 2. Phương án ScraperAPI Chuyên dụng (Sử dụng Ultra Premium Proxy)
    try:
        payload = {
            'api_key': SCRAPER_API_KEY,
            'url': clean_url,
            'country_code': 'vn',
            'device_type': 'mobile'
        }
        res = requests.get('http://api.scraperapi.com', params=payload, timeout=20)
        if res.status_code == 200:
            # Bóc tách cấu trúc giá chuẩn từ HTML/JSON của Shopee Mobile
            prices = re.findall(r'"price":\s*(\d+)', res.text) or re.findall(r'"price_min":\s*(\d+)', res.text)
            valid_prices = []
            for p in prices:
                val = float(p)
                if val > 100000000:
                    val = val / 100000
                if 5000 <= val <= 50000000:
                    valid_prices.append(val)
            if valid_prices:
                return int(min(valid_prices))
    except Exception as e:
        print(f"Lỗi ScraperAPI: {e}")

    # Tuyệt đối không trả về giá giả
    return None

def run_crawler_with_creds(creds_dict, partner_config=None, status_callback=None):
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    sheet = client.open("File check gia").worksheet("Data_Gia_Thi_Truong")
    rows = sheet.get_all_values()
    
    if len(rows) < 2:
        return 0

    updated_count = 0
    
    for idx, row in enumerate(rows[1:], start=2):
        if len(row) >= 9:
            link_content = row[8]  # Cột I: Link_Shopee
            urls = re.findall(r'https?://[^\s,\"\']+', str(link_content))
            
            if not urls:
                continue

            if status_callback:
                status_callback(f"⏳ Hàng {idx}: Đang lấy giá THẬT cho {len(urls)} link...")

            collected_prices = []
            for url in urls:
                p = get_real_shopee_price(url, partner_config)
                if p:
                    collected_prices.append(p)
                    if status_callback:
                        status_callback(f"🎯 Hàng {idx}: Đã lấy giá chuẩn {p:,.0f}đ")
                time.sleep(1)

            # Chỉ cập nhật Google Sheet khi LẤY ĐƯỢC GIÁ THỰC TẾ
            if collected_prices:
                avg_price = int(sum(collected_prices) / len(collected_prices))
                sheet.update_cell(idx, 10, avg_price)
                updated_count += 1
                if status_callback:
                    status_callback(f"✅ Hàng {idx}: Đã cập nhật giá thật {avg_price:,.0f}đ")
            else:
                if status_callback:
                    status_callback(f"⚠️ Hàng {idx}: Không cào được giá thật (Bị Shopee chặn IP)")

    return updated_count
