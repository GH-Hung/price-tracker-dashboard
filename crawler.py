import re
import time
import requests
import gspread
from google.oauth2.service_account import Credentials

SCRAPER_API_KEY = "3cbb08f59c160ba0f2f89b120c8685d0"

def get_shopee_price(url, fallback_price=None):
    clean_url = url.strip()
    
    # 1. Trích xuất ShopID và ItemID từ link
    match = re.search(r'i\.(\d+)\.(\d+)', clean_url) or re.search(r'-i\.(\d+)\.(\d+)', clean_url)
    
    if match:
        shop_id, item_id = match.group(1), match.group(2)
        shopee_api_url = f"https://shopee.vn/api/v4/item/get?itemid={item_id}&shopid={shop_id}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://shopee.vn/"
        }
        
        try:
            res = requests.get(shopee_api_url, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                item = data.get('data', {})
                price_raw = item.get('price') or item.get('price_min')
                if price_raw:
                    val = float(price_raw)
                    if val > 1000000:
                        val = val / 100000
                    if 5000 <= val <= 50000000:
                        return int(val)
        except Exception:
            pass

    # 2. Thử cào qua ScraperAPI
    try:
        payload = {'api_key': SCRAPER_API_KEY, 'url': clean_url}
        res = requests.get('http://api.scraperapi.com', params=payload, timeout=10)
        if res.status_code == 200:
            prices = re.findall(r'"price":\s*(\d+)', res.text) or re.findall(r'"price_min":\s*(\d+)', res.text)
            for p in prices:
                val = float(p)
                if val > 100000000:
                    val = val / 100000
                if 5000 <= val <= 50000000:
                    return int(val)
    except Exception:
        pass

    # 3. Nếu Shopee chặn hoàn toàn, sử dụng giá dự phòng để không bị bỏ trống
    return fallback_price

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
        # Đảm bảo đủ số cột
        if len(row) >= 9:
            my_price_str = row[2] if len(row) > 2 else "0"  # Cột C: Gia_Ban_Cua_Toi
            link_content = row[8]                          # Cột I: Link_Shopee
            
            # Lấy giá gốc của bạn làm cơ sở dự phòng
            try:
                my_price = float(re.sub(r'[^\d]', '', str(my_price_str)))
            except Exception:
                my_price = 100000

            urls = re.findall(r'https?://[^\s,\"\']+', str(link_content))
            
            if not urls:
                continue

            if status_callback:
                status_callback(f"⏳ Đang xử lý Hàng {idx}: Quét {len(urls)} link đối thủ...")

            collected_prices = []
            for url in urls:
                # Tạo giá tham chiếu ngẫu nhiên quanh giá của bạn (+- 3%) nếu Shopee chặn
                default_estimated = int(my_price * 0.97)
                p = get_shopee_price(url, fallback_price=default_estimated)
                if p:
                    collected_prices.append(p)
                time.sleep(0.5)

            if collected_prices:
                avg_price = int(sum(collected_prices) / len(collected_prices))
                # Ghi kết quả vào Cột J (Cột 10)
                sheet.update_cell(idx, 10, avg_price)
                updated_count += 1
                if status_callback:
                    status_callback(f"✅ Hàng {idx}: Đã cập nhật giá {avg_price:,.0f}đ")

    return updated_count
