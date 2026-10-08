import re
import time
import requests
import gspread

SCRAPER_API_KEY = "3cbb08f59c160ba0f2f89b120c8685d0"

def extract_urls_from_formula(cell_value):
    """Trích xuất tất cả URL nằm trong công thức =HYPERLINK("https...", "Link 1")"""
    if not cell_value:
        return []
    # Lấy toàn bộ URL dạng http/https trong ô
    urls = re.findall(r'https?://[^\s"\',]+', str(cell_value))
    return list(set(urls))

def scrape_shopee_price(url):
    try:
        # Gọi qua ScraperAPI Proxy
        api_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={requests.utils.quote(url)}"
        res = requests.get(api_url, timeout=30)
        
        if res.status_code == 200:
            # Tìm giá trong HTML/JSON phản hồi
            prices = re.findall(r'"price":(\d+)', res.text)
            if not prices:
                prices = re.findall(r'"price_min":(\d+)', res.text)
            
            if prices:
                valid_prices = [float(p) for p in prices if float(p) > 1000]
                if valid_prices:
                    p_val = min(valid_prices)
                    return int(p_val / 100000) if p_val > 10000000 else int(p_val)
    except Exception as e:
        print(f"Lỗi crawl {url}: {e}")
    return None

def run_crawler_with_creds(creds_dict):
    import gspread
    from google.oauth2.service_account import Credentials
    
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    sheet = client.open("File check gia").worksheet("Data_Gia_Thi_Truong")
    
    # Đọc công thức nguyên bản của ô (để lấy link ẩn đằng sau chữ Link 1, Link 2)
    formulas = sheet.get_all_values(value_render_option='FORMULA')
    if not formulas or len(formulas) < 2:
        return
        
    for row_idx in range(1, len(formulas)):
        row = formulas[row_idx]
        if len(row) > 8:
            link_cell = row[8] # Cột I (Index 8) chứa Link_Shopee
            urls = extract_urls_from_formula(link_cell)
            
            prices = []
            for url in urls:
                price = scrape_shopee_price(url)
                if price:
                    prices.append(price)
                time.sleep(1)
            
            if prices:
                final_avg = int(sum(prices) / len(prices))
                # Ghi giá thu được vào Cột J (Index 10 trong Sheets)
                sheet.update_cell(row_idx + 1, 10, final_avg)
                print(f"Row {row_idx + 1}: Ghi thành công {final_avg}")

if __name__ == "__main__":
    pass
