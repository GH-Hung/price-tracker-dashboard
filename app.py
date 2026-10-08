import streamlit as st
import pandas as pd
import re
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Dashboard Theo Dõi Giá Thị Trường", layout="wide")

# Connect Google Sheet
@st.cache_data(ttl=30)
def load_data():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("File check gia").worksheet("Data_Gia_Thi_Truong")
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def parse_price(val):
    if pd.isna(val) or val is None or val == "":
        return 0
    clean_str = re.sub(r'[^\d]', '', str(val))
    return float(clean_str) if clean_str else 0

try:
    df = load_data()
    
    # 1. Lấy dữ liệu sản phẩm từ Google Sheet
    if not df.empty:
        row = df.iloc[0]
        product_name = str(row.get("Ten_San_Pham", "Ram laptop 2gb ddr3 pc3 bus 1333"))
        my_price = parse_price(row.get("Gia_Ban_Cua_Toi", 0))
        promo_price = parse_price(row.get("Gia_Khuyen_Mai", 0)) or my_price
        shopee_price = parse_price(row.get("Gia_Doi_Thu_Shopee", 0))
    else:
        product_name = "Ram laptop 2gb ddr3 pc3 bus 1333"
        my_price = 65000
        promo_price = 65000
        shopee_price = 60000

    shopee_price_fmt = f"{shopee_price:,.0f}đ".replace(",", ".") if shopee_price > 0 else "Chưa có dữ liệu"

    # 2. Khai báo trực tiếp HTML Template
    HTML_TEMPLATE = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard Khảo Sát & So Sánh Giá Thị Trường</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f3f4f6; }}
        </style>
    </head>
    <body class="p-2 md:p-6">

        <div class="max-w-6xl mx-auto space-y-6">
            
            <!-- Header & Config -->
            <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 flex flex-wrap justify-between items-center gap-4">
                <div>
                    <h1 class="text-2xl font-bold text-gray-800"><i class="fa-solid fa-chart-line text-blue-600 mr-2"></i>Hệ Thống Theo Dõi Giá Thị Trường</h1>
                    <p class="text-sm text-gray-500">Tự động thu thập, lọc dữ liệu ảo & Cảnh báo dung sai</p>
                </div>
                <div class="flex items-center gap-3">
                    <span class="text-sm font-semibold text-gray-700">Dung sai cài đặt:</span>
                    <input type="number" value="5" id="toleranceInput" class="w-16 border rounded p-1 text-center font-bold text-blue-600" onchange="updateDashboard()">
                    <span class="text-gray-600 font-bold">%</span>
                </div>
            </div>

            <!-- Product Card Container -->
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                
                <!-- Top Product Info -->
                <div class="p-6 border-b border-gray-100 bg-gray-50 flex flex-wrap justify-between items-center gap-4">
                    <div class="flex items-center space-x-4">
                        <div class="w-16 h-16 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600 font-bold text-xl">SP</div>
                        <div>
                            <span class="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">SKU Đang Chọn</span>
                            <h2 class="text-lg font-bold text-gray-800 mt-1">{product_name}</h2>
                            <div class="text-sm text-gray-600 mt-0.5">
                                Giá bạn bán: <span class="font-bold text-gray-900">{my_price:,.0f}đ</span> | 
                                Giá KM: <span class="font-bold text-green-600">{promo_price:,.0f}đ</span>
                            </div>
                        </div>
                    </div>
                    
                    <div id="statusBadge" class="px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 border"></div>
                </div>

                <!-- Market Avg Summary -->
                <div class="px-6 py-3 bg-blue-50/50 border-b border-gray-100 flex justify-between items-center">
                    <div class="text-sm font-semibold text-gray-700">
                        <i class="fa-solid fa-scale-balanced text-blue-600 mr-1"></i> Giá Trung Bình Thị Trường (Đã lọc dữ liệu ảo): 
                        <span class="text-base font-bold text-blue-700 ml-1" id="avgMarketPrice">{shopee_price_fmt}</span>
                    </div>
                    <div class="text-xs text-gray-500">Dựa trên các sàn đang hoạt động tốt</div>
                </div>

                <!-- Detailed Platform Table -->
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse text-sm">
                        <thead>
                            <tr class="bg-gray-100/70 text-gray-600 border-b">
                                <th class="p-3 pl-6">Nguồn</th>
                                <th class="p-3">Khoảng Giá Bán Mới Nhất</th>
                                <th class="p-3">Đánh Giá Độ Tin Cậy Dữ Liệu</th>
                                <th class="p-3 pr-6 text-center">Đối Soát / Kiểm Tra</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-100 text-gray-700">
                            
                            <!-- Shopee -->
                            <tr class="hover:bg-gray-50">
                                <td class="p-3 pl-6 font-bold text-orange-600"><i class="fa-bag-shopping mr-1"></i> Shopee</td>
                                <td class="p-3 font-semibold text-gray-900">{shopee_price_fmt}</td>
                                <td class="p-3">
                                    <span class="bg-green-100 text-green-700 text-xs px-2.5 py-1 rounded-full font-semibold">🟢 Bình thường</span>
                                </td>
                                <td class="p-3 pr-6 text-center">
                                    <button onclick="openAuditModal('Shopee')" class="text-blue-600 hover:text-blue-800 text-xs font-semibold underline">🔗 Xem link đối thủ</button>
                                </td>
                            </tr>

                            <!-- TikTok -->
                            <tr class="hover:bg-gray-50">
                                <td class="p-3 pl-6 font-bold text-black"><i class="fa-tiktok mr-1"></i> TikTok Shop</td>
                                <td class="p-3 font-semibold text-gray-900">Chưa có dữ liệu</td>
                                <td class="p-3">
                                    <span class="bg-gray-100 text-gray-600 text-xs px-2.5 py-1 rounded-full font-semibold">⚪ Đang cập nhật</span>
                                </td>
                                <td class="p-3 pr-6 text-center">-</td>
                            </tr>

                            <!-- Lazada -->
                            <tr class="hover:bg-gray-50">
                                <td class="p-3 pl-6 font-bold text-blue-800"><i class="fa-heart mr-1"></i> Lazada</td>
                                <td class="p-3 font-semibold text-gray-900">Chưa có dữ liệu</td>
                                <td class="p-3">
                                    <span class="bg-gray-100 text-gray-600 text-xs px-2.5 py-1 rounded-full font-semibold">⚪ Đang cập nhật</span>
                                </td>
                                <td class="p-3 pr-6 text-center">-</td>
                            </tr>

                        </tbody>
                    </table>
                </div>

                <!-- Chart Section -->
                <div class="p-6 border-t border-gray-100 bg-white">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="font-bold text-gray-800 text-sm"><i class="fa-solid fa-chart-area text-blue-600 mr-2"></i>Biểu Đồ Xu Hướng Biến Động Giá Thị Trường</h3>
                    </div>
                    <div class="h-64">
                        <canvas id="priceTrendChart"></canvas>
                    </div>
                </div>

            </div>

        </div>

        <!-- JAVASCRIPT LOGIC -->
        <script>
            const myPrice = {promo_price};
            const avgMarket = {shopee_price if shopee_price > 0 else promo_price};

            function updateDashboard() {{
                const tolerancePct = parseFloat(document.getElementById('toleranceInput').value) || 5;
                const minAllowed = avgMarket * (1 - tolerancePct / 100);
                const maxAllowed = avgMarket * (1 + tolerancePct / 100);

                const badge = document.getElementById('statusBadge');

                if (myPrice < minAllowed) {{
                    badge.className = "px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 border bg-red-50 text-red-700 border-red-200";
                    badge.innerHTML = `<i class="fa-solid fa-circle-exclamation text-red-600"></i> CẢNH BÁO: Giá Thấp Hơn Thị Trường (> ${{tolerancePct}}%)`;
                }} else if (myPrice > maxAllowed) {{
                    badge.className = "px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 border bg-amber-50 text-amber-700 border-amber-200";
                    badge.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-amber-600"></i> CẢNH BÁO: Giá Cao Hơn Thị Trường (> ${{tolerancePct}}%)`;
                }} else {{
                    badge.className = "px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 border bg-green-50 text-green-700 border-green-200";
                    badge.innerHTML = `<i class="fa-solid fa-circle-check text-green-600"></i> AN TOÀN: Nằm Trong Dung Sai (±${{tolerancePct}}%)`;
                }}
            }}

            const ctx = document.getElementById('priceTrendChart').getContext('2d');
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: ['Ngày 1', 'Ngày 2', 'Hôm nay'],
                    datasets: [
                        {{
                            label: 'Giá Bán Của Bạn',
                            data: [{promo_price}, {promo_price}, {promo_price}],
                            borderColor: '#2563eb',
                            borderWidth: 3,
                            fill: false
                        }},
                        {{
                            label: 'Giá Shopee',
                            data: [{shopee_price}, {shopee_price}, {shopee_price}],
                            borderColor: '#ea580c',
                            borderWidth: 2,
                            fill: false
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ position: 'top' }} }}
                }}
            }});

            updateDashboard();
        </script>
    </body>
    </html>
    """

    # 3. Hiển thị HTML giao diện
    st.components.v1.html(HTML_TEMPLATE, height=950, scrolling=True)

except Exception as e:
    st.error(f"Đã xảy ra lỗi hệ thống: {e}")
