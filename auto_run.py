import os
import time
import json
import asyncio
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv

# Configure logging to only print to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Account configuration
USERNAME = "Chicken7net2"
PASSWORD = "123123q"

if not all([USERNAME, PASSWORD]):
    logger.error("Please set DEFAULT_USERNAME and DEFAULT_PASSWORD in .env file")
    raise ValueError("Please set DEFAULT_USERNAME and DEFAULT_PASSWORD in .env file")

# Headers for API requests
BASE_HEADERS = {
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'accept-language': 'en,en-US;q=0.9,vi;q=0.8',
    'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'origin': 'https://traodoisub.com',
    'referer': 'https://traodoisub.com/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
    'x-requested-with': 'XMLHttpRequest'
}

async def login(username: str, password: str):
    """Login to traodoisub.com and return the response"""
    url = 'https://traodoisub.com/scr/login.php'
    data = {
        'username': username,
        'password': password
    }
    
    logger.info(f"Đang đăng nhập: {username}")
    response = requests.post(url, headers=BASE_HEADERS, data=data)
    
    # Extract PHPSESSID from Set-Cookie header
    set_cookie = response.headers.get('Set-Cookie', '')
    phpsessid = None
    if 'PHPSESSID=' in set_cookie:
        phpsessid = set_cookie.split('PHPSESSID=')[1].split(';')[0]
    
    response_json = response.json()
    if response_json.get('success'):
        logger.info("✅ Đăng nhập thành công")
    else:
        logger.error(f"❌ Đăng nhập thất bại: {response_json.get('message', 'Lỗi không xác định')}")
    
    return response_json, f"PHPSESSID={phpsessid}" if phpsessid else None

async def get_headers_with_cookie(cookie: str):
    """Get headers with cookie for API requests"""
    headers = BASE_HEADERS.copy()
    headers['Cookie'] = cookie
    return headers

async def create_order(headers):
    url = 'https://traodoisub.com/mua/facebook_share/themid.php'
    data = {
        'maghinho': '',
        'id': '2505232386495814',
        'sl': '30.5',
        'dateTime': datetime.now().strftime('%Y-%m-%d+%H:%M:%S')
    }
    
    logger.info("🔄 Đang tạo đơn hàng...")
    response = requests.post(url, headers=headers, data=data)
    logger.info("✅ Đã tạo đơn hàng")
    return response

async def fetch_orders(headers):
    url = 'https://traodoisub.com/mua/facebook_share/fetch.php'
    data = {
        'page': '1',
        'query': ''
    }
    
    logger.info("🔍 Đang tìm đơn hàng...")
    response = requests.post(url, headers=headers, data=data)
    response_json = response.json()
    if response_json.get('data'):
        logger.info(f"✅ Đã tìm thấy {len(response_json['data'])} đơn hàng")
    else:
        logger.warning("⚠️ Không tìm thấy đơn hàng nào")
    return response_json

async def cancel_order(code: str, headers):
    url = 'https://traodoisub.com/mua/facebook_share/api.php'
    data = {
        'code': code,
        'type': 'cancel'
    }
    
    logger.info(f"🔄 Đang hủy đơn hàng: {code}")
    response = requests.post(url, headers=headers, data=data)
    response_json = response.json()
    return response_json

async def main_loop():
    """Main automation loop"""
    logger.info("🚀 Bắt đầu vòng lặp chính...")
    execution_count = 0
    
    while True:
        try:
            # Login if needed (first time or after 10 executions)
            if execution_count == 0 or execution_count >= 10:
                login_response, cookie = await login(USERNAME, PASSWORD)
                if not login_response.get('success') or not cookie:
                    logger.error("❌ Đăng nhập thất bại, đợi 5 phút...")
                    await asyncio.sleep(300)  # Wait 5 minutes before retry
                    continue
                execution_count = 0  # Reset counter after successful login
                logger.info("🔄 Đã đăng nhập lại sau 10 lần thực hiện")

            headers = await get_headers_with_cookie(cookie)
            
            # Create order
            await create_order(headers)
            
            # Wait for 2 seconds
            await asyncio.sleep(2)
            
            # Fetch and cancel order
            fetch_response = await fetch_orders(headers)
            if fetch_response.get('data'):
                order = fetch_response['data'][0]
                code = order['code']
                await cancel_order(code, headers)
            
            # Increment execution counter
            execution_count += 1
            logger.info(f"⏳ Hoàn thành chu kỳ {execution_count}/10, đợi 45 giây...")
            
            # Wait for 45 seconds before next iteration
            await asyncio.sleep(45)
            
        except Exception as e:
            logger.error(f"❌ Lỗi: {str(e)}")
            logger.info("⏳ Đợi 5 phút trước khi thử lại...")
            await asyncio.sleep(300)  # Wait 5 minutes before retry

if __name__ == '__main__':
    logger.info("🤖 Bắt đầu tự động hóa...")
    asyncio.run(main_loop()) 