import re
import time
import requests
import gspread
from google.oauth2.service_account import Credentials

SCRAPER_API_KEY = "3cbb08f59c160ba0f2f89b120c8685d0"

def resolve_and_get_price(url):
    """
    Bóc tách giá từ URL Shopee thông qua ScraperAPI
    """
    try:
        # Gọi ScraperAPI bật render JavaScript để vượt qua các trang chờ của Shopee
        payload = {
            'api_key': SCRAPER_API_KEY,
            'url': url,
            'keep_headers': 'true'
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        
        res = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=25)
        if res.status_code == 200:
            text = res.text
            
            # Tìm các dạng biểu diễn giá tiền trong mã nguồn Shopee
            prices = re.findall(r'"price":\s*(\d+)', text)
            if not prices:
                prices = re.findall(r'"price_min":\s*(\d+)', text)
            if not prices:
                prices = re.findall(r'(\d{5,9})\s*₫', text)

            if prices:
                valid_prices = []
                for p in prices:
                    val = float(p)
                    # Shopee thường nhân giá với 100,000 trong API nội bộ
                    if val > 100000000:
                        val = val / 100000
                    if 5000 <= val <= 50000000:  # Giá hợp lệ từ 5k đến 50 triệu
                        valid_prices.append(val)
                
                if valid_prices:
                    return int(min(valid_prices))
    except Exception as e:
        print(f"Lỗi cào URL {url}: {e}")
    return None

def extract_all_links_from_cell(sheet, worksheet_name, cell_address):
    """
    Sử dụng API v4 để lấy toàn bộ Hyperlink ẩn trong RichText của ô Google Sheet
    """
    try:
        # Lấy chi tiết thông tin ô bao gồm cả Hyperlink cấu trúc RichText
        spreadsheet_id = sheet.id
        service = sheet.client.auth.build('sheets', 'v4', credentials=sheet.client.auth.credentials)
        result = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            ranges=f"{worksheet_name}!{cell_address}",
            fields="sheets/data/rowData/values/textFormatRuns"
        ).execute()

        urls = []
        sheets = result.get('sheets', [])
        if sheets:
            data = sheets[0].get('data', [])
            if data and 'rowData' in data[0]:
                row_data = data[0]['rowData']
                if row_data and 'values' in row_data[0]:
                    values = row_data[0]['values'][0]
                    runs = values.get('textFormatRuns', [])
                    for run in runs:
                        link = run.get('format', {}).get('link', {}).get('uri')
                        if link:
                            urls.append(link)
        return list(set(urls))
    except Exception as e:
        print(f"Lỗi bóc tách hyperlink ô {cell_address}: {e}")
        return []

def run_crawler_with_creds(creds_dict, status_callback=None):
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    ws_name = "Data_Gia_Thi_Truong"
    sheet = client.open("File check gia")
    worksheet = sheet.worksheet(ws_name)
    
    # Lấy toàn bộ công thức và văn bản
    all_values = worksheet.get_all_values()
    if len(all_values) < 2:
        return

    updated_count = 0
    
    # Duyệt từ dòng 2 trở đi
    for row_idx in range(2, len(all_values) + 1):
        cell_addr = f"I{row_idx}"  # Cột I: Link_Shopee
        
        # 1. Trích xuất URL từ công thức thường
        cell_val = worksheet.acell(cell_addr, value_render_option='FORMULA').value
        urls = re.findall(r'https?://[^\s"\',)]+', str(cell_val))
        
        # 2. Nếu không tìm thấy trong công thức, trích xuất từ RichText Hyperlink
        if not urls:
            urls = extract_all_links_from_cell(sheet, ws_name, cell_addr)
            
        if not urls:
            continue

        if status_callback:
            status_callback(f"⏳ Đang quét Hàng {row_idx}: Tìm thấy {len(urls)} link...")

        collected_prices = []
        for url in urls:
            p = resolve_and_get_price(url)
            if p:
                collected_prices.append(p)
            time.sleep(1)

        if collected_prices:
            avg_price = int(sum(collected_prices) / len(collected_prices))
            # Ghi vào Cột J (Gia_Doi_Thu_Shopee)
            worksheet.update_cell(row_idx, 10, avg_price)
            updated_count += 1
            if status_callback:
                status_callback(f"✅ Hàng {row_idx}: Đã cập nhật giá {avg_price:,.0f}đ")
                
    return updated_count
