import re
import time
import requests
import gspread
from google.oauth2.service_account import Credentials

SCRAPER_API_KEY = "3cbb08f59c160ba0f2f89b120c8685d0"

def resolve_redirect_url(url):
    """Giải mã link rút gọn shope.ee về link gốc Shopee"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, allow_redirects=True, timeout=8)
        return res.url
    except Exception:
        return url

def scrape_shopee_price(raw_url):
    """Tải mã nguồn và lấy giá từ Shopee qua ScraperAPI"""
    try:
        final_url = resolve_redirect_url(raw_url)
        api_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={requests.utils.quote(final_url)}&render=true"
        
        res = requests.get(api_url, timeout=35)
        if res.status_code == 200:
            # Tìm các định dạng giá trong JSON / HTML của Shopee
            prices = re.findall(r'"price":(\d+)', res.text)
            if not prices:
                prices = re.findall(r'"price_min":(\d+)', res.text)
            
            if prices:
                valid_prices = [float(p) for p in prices if float(p) > 1000]
                if valid_prices:
                    p_val = min(valid_prices)
                    # Chuẩn hóa giá tiền Việt Nam (Ví dụ 6000000000 -> 60000)
                    return int(p_val / 100000) if p_val > 10000000 else int(p_val)
    except Exception as e:
        print(f"Lỗi cào URL {raw_url}: {e}")
    return None

def run_crawler_with_creds(creds_dict):
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    sheet = client.open("File check gia").worksheet("Data_Gia_Thi_Truong")
    
    # Ép Google Sheets trả về CÔNG THỨC nguyên bản (để lấy link ẩn đằng sau chữ Link 1, Link 2)
    formulas = sheet.get_all_values(value_render_option='FORMULA')
    if not formulas or len(formulas) < 2:
        return
        
    for row_idx in range(1, len(formulas)):
        row = formulas[row_idx]
        if len(row) > 8:
            link_cell_formula = row[8]  # Cột I (Index 8): Link_Shopee
            
            # Trích xuất tất cả URL bắt đầu bằng http/https ẩn trong công thức HYPERLINK
            urls = list(set(re.findall(r'https?://[^\s"\',)]+', str(link_cell_formula))))
            
            collected_prices = []
            for url in urls:
                price = scrape_shopee_price(url)
                if price and price > 0:
                    collected_prices.append(price)
                time.sleep(1)
            
            if collected_prices:
                avg_price = int(sum(collected_prices) / len(collected_prices))
                # Ghi giá trung bình vào Cột J (Hàng = row_idx + 1, Cột 10)
                sheet.update_cell(row_idx + 1, 10, avg_price)
                print(f"✅ Hàng {row_idx + 1}: Đã cập nhật giá {avg_price}đ")
