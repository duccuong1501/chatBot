import os
import time
import json
import asyncio
import requests
import base64
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from dotenv import load_dotenv
from typing import Tuple, Dict, Optional, Set
from PIL import Image
import io
import random
import telegram.error
from telegram.request import HTTPXRequest


# Load environment variables
load_dotenv()

# Constants
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_BOT_TOKEN = "8114514687:AAG3zXuuyCk8EAYE6xBrv5fzh_aBKvkd_Rg"
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set!")

# CSKH configuration
CSKH_ID = int(os.getenv('CSKH_ID', '0'))  # CSKH Telegram ID
CSKH_ID = 6148328262
if not CSKH_ID:
    raise ValueError("CSKH_ID environment variable is not set or invalid!")

# Wait times from environment variables
TIKTOK_WAIT_TIME = int(os.getenv('TIKTOK_WAIT_TIME', '30'))  # Default 30 seconds for TikTok
FACEBOOK_WAIT_TIME = int(os.getenv('FACEBOOK_WAIT_TIME', '45'))  # Default 45 seconds for Facebook

AUTHORIZED_USERS = set()  # Set of authorized user IDs

# Load authorized users from file
def load_authorized_users():
    try:
        if os.path.exists('authorized_users.json'):
            with open('authorized_users.json', 'r') as f:
                data = json.load(f)
                global AUTHORIZED_USERS
                AUTHORIZED_USERS = set(data.get('users', []))
                print(f"✅ Loaded {len(AUTHORIZED_USERS)} authorized users")
    except Exception as e:
        print(f"❌ Error loading authorized users: {str(e)}")

# Save authorized users to file
def save_authorized_users():
    try:
        data = {
            'users': list(AUTHORIZED_USERS)
        }
        with open('authorized_users.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("✅ Saved authorized users")
    except Exception as e:
        print(f"❌ Error saving authorized users: {str(e)}")

# Load authorized users on startup
load_authorized_users()

# States for conversation
WAITING_USERNAME = 1
WAITING_PASSWORD = 2
WAITING_RETRY = 3

# User states dictionary to store individual user states
user_states = {}

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

# Image cache with base64
image_cache = {}

# Add usernames list at the top of the file after imports
TIKTOK_USERNAMES = set()  # Initialize as empty set

def load_tiktok_usernames():
    """Load TikTok usernames from JSON file"""
    try:
        if os.path.exists('tiktok_usernames.json'):
            with open('tiktok_usernames.json', 'r') as f:
                data = json.load(f)
                global TIKTOK_USERNAMES
                TIKTOK_USERNAMES = set(data.get('usernames', []))
                print(f"✅ Loaded {len(TIKTOK_USERNAMES)} TikTok usernames")
    except Exception as e:
        print(f"❌ Error loading TikTok usernames: {str(e)}")

def save_tiktok_usernames():
    """Save TikTok usernames to JSON file"""
    try:
        data = {
            'usernames': list(TIKTOK_USERNAMES)
        }
        with open('tiktok_usernames.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("✅ Saved TikTok usernames")
    except Exception as e:
        print(f"❌ Error saving TikTok usernames: {str(e)}")

# Load TikTok usernames on startup
load_tiktok_usernames()

# Add at the top of the file after imports
ORDER_TYPES = ['facebook_share', 'tiktok_follow', 'tiktok_follow_global']

def image_to_base64(image_path: str, max_size: int = 1280) -> str:
    """
    Convert image to base64 string with optimization
    """
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if needed
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Resize if too large
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Optimize and convert to base64
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=85, optimize=True)
            output.seek(0)
            return base64.b64encode(output.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"❌ Debug: Error converting image to base64: {str(e)}")
        return None

async def send_photo_from_base64(context: ContextTypes.DEFAULT_TYPE, chat_id: int, image_path: str, caption: str = None) -> bool:
    """
    Send photo using base64 string with caching
    """
    try:
        # Check cache first
        if image_path in image_cache:
            print(f"🔍 Debug: Using cached base64 image for {image_path}")
            base64_str = image_cache[image_path]
        else:
            print(f"🔍 Debug: Converting image to base64: {image_path}")
            base64_str = image_to_base64(image_path)
            if not base64_str:
                return False
            image_cache[image_path] = base64_str

        # Convert base64 to bytes
        image_bytes = base64.b64decode(base64_str)
        
        # Send photo with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=image_bytes,
                    caption=caption,
                    parse_mode='Markdown'
                )
                return True
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                print(f"⚠️ Debug: Retry {attempt + 1}/{max_retries} for sending photo")
                await asyncio.sleep(1)
                
    except Exception as e:
        print(f"❌ Debug: Error sending photo: {str(e)}")
        return False

async def login(username: str, password: str) -> Tuple[Dict, Optional[str]]:
    """Login to traodoisub.com and return the response"""
    url = 'https://traodoisub.com/scr/login.php'
    data = {
        'username': username,
        'password': password
    }
    
    print(f"🔍 Debug: Attempting login for username: {username}")
    response = requests.post(url, headers=BASE_HEADERS, data=data)
    print(f"🔍 Debug: Response headers: {dict(response.headers)}")
    
    # Extract PHPSESSID from Set-Cookie header
    set_cookie = response.headers.get('Set-Cookie', '')
    print(f"🔍 Debug: Set-Cookie header: {set_cookie}")
    
    # Parse PHPSESSID from Set-Cookie
    phpsessid = None
    if 'PHPSESSID=' in set_cookie:
        phpsessid = set_cookie.split('PHPSESSID=')[1].split(';')[0]
        print(f"🔍 Debug: Extracted PHPSESSID: {phpsessid}")
    
    response_json = response.json()
    print(f"🔍 Debug: Login response: {json.dumps(response_json, indent=2)}")
    
    if not phpsessid:
        print("⚠️ Debug: No PHPSESSID found in response headers")
        return response_json, None
        
    return response_json, f"PHPSESSID={phpsessid}"

async def get_headers_with_cookie(cookie: str) -> dict:
    """Get headers with cookie for API requests"""
    headers = BASE_HEADERS.copy()
    headers['Cookie'] = cookie
    return headers

async def create_order(headers: dict):
    url = 'https://traodoisub.com/mua/facebook_share/themid.php'
    data = {
        'maghinho': '',
        'id': '2505232386495814',
        'sl': '30.5',
        'dateTime': datetime.now().strftime('%Y-%m-%d+%H:%M:%S')
    }
    
    response = requests.post(url, headers=headers, data=data)
    return response

async def fetch_orders(headers: dict):
    url = 'https://traodoisub.com/mua/facebook_share/fetch.php'
    data = {
        'page': '1',
        'query': ''
    }
    
    response = requests.post(url, headers=headers, data=data)
    return response.json()

async def cancel_order(code: str, headers: dict):
    url = 'https://traodoisub.com/mua/facebook_share/api.php'
    data = {
        'code': code,
        'type': 'cancel'
    }
    
    response = requests.post(url, headers=headers, data=data)
    return response.json()

async def create_tiktok_follow_order(headers: dict):
    """Create TikTok follow order"""
    url = 'https://traodoisub.com/mua/tiktok_follow/themid.php'
    # Select random username
    random_username = random.choice(list(TIKTOK_USERNAMES))
    data = {
        'maghinho': '',
        'id': f'https://www.tiktok.com/@{random_username}',
        'sl': '100.5',
        'dateTime': datetime.now().strftime('%Y-%m-%d+%H:%M:%S')
    }
    
    response = requests.post(url, headers=headers, data=data)
    return response

async def create_tiktok_follow_global_order(headers: dict):
    """Create TikTok follow global order"""
    url = 'https://traodoisub.com/mua/tiktok_follow2/themid.php'
    # Select random username
    random_username = random.choice(list(TIKTOK_USERNAMES))
    data = {
        'maghinho': '',
        'id': f'https://www.tiktok.com/@{random_username}',
        'sl': '100.5',
        'dateTime': datetime.now().strftime('%Y-%m-%d+%H:%M:%S')
    }
    
    response = requests.post(url, headers=headers, data=data)
    return response

async def fetch_tiktok_follow_orders(headers: dict):
    """Fetch TikTok follow orders"""
    url = 'https://traodoisub.com/mua/tiktok_follow/fetch.php'
    data = {
        'page': '1',
        'query': ''
    }
    
    response = requests.post(url, headers=headers, data=data)
    return response.json()

async def fetch_tiktok_follow_global_orders(headers: dict):
    """Fetch TikTok follow global orders"""
    url = 'https://traodoisub.com/mua/tiktok_follow2/fetch.php'
    data = {
        'page': '1',
        'query': ''
    }
    
    response = requests.post(url, headers=headers, data=data)
    return response.json()

async def cancel_tiktok_follow_order(code: str, headers: dict):
    """Cancel TikTok follow order"""
    url = 'https://traodoisub.com/mua/tiktok_follow/api.php'
    data = {
        'code': code,
        'type': 'cancel',
        'time_pack': '30'
    }
    
    response = requests.post(url, headers=headers, data=data)
    return response.json()

async def cancel_tiktok_follow_global_order(code: str, headers: dict):
    """Cancel TikTok follow global order"""
    url = 'https://traodoisub.com/mua/tiktok_follow2/api.php'
    data = {
        'code': code,
        'type': 'cancel',
        'time_pack': '30'
    }
    
    response = requests.post(url, headers=headers, data=data)
    return response.json()

async def show_control_buttons(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    print(f"🔍 Debug: show_control_buttons called with chat_id: {chat_id}")
    try:
        # Create menu buttons based on bot state
        if not user_states[chat_id]['is_running']:
            # Bot is not running, show start button
            keyboard = [
                [
                    InlineKeyboardButton("▶️ Bắt đầu", callback_data='start_auto')
                ]
            ]
            menu_text = (
                "🎮 *Điều khiển bot:*\n\n"
                "▶️ *Bắt đầu:* Chạy tự động ngẫu nhiên các chế độ"
            )
        else:
            # Bot is running, show stop button
            keyboard = [
                [
                    InlineKeyboardButton("⏹️ Kết thúc", callback_data='stop')
                ]
            ]
            menu_text = (
                "🎮 *Điều khiển bot:*\n\n"
                "⏹️ *Kết thúc:* Dừng bot"
            )
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=menu_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        print("✅ Debug: Control buttons sent successfully")
    except Exception as e:
        print(f"❌ Debug: Error in show_control_buttons: {str(e)}")

async def fetch_balance(headers: dict) -> Optional[str]:
    """Fetch current balance (xu) from traodoisub.com"""
    url = 'https://traodoisub.com/scr/user.php'
    
    try:
        response = requests.get(url, headers=headers)
        response_json = response.json()
        balance = response_json.get('xu')
        
        # Convert balance to integer and handle negative values
        try:
            balance_int = int(balance)
            if balance_int < 0:
                balance = "0"
        except (ValueError, TypeError):
            pass
            
        return balance
    except Exception as e:
        print(f"❌ Debug: Error fetching balance: {str(e)}")
        return None

async def automation_loop(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    print(f"🔍 Debug: automation_loop started with chat_id: {chat_id}")
    while user_states[chat_id]['is_running']:
        try:
            # Set waiting flag to false at start of cycle
            user_states[chat_id]['is_waiting'] = False
            
            # Check if we need to re-login
            if not user_states[chat_id].get('cookie'):
                print(f"⚠️ Debug: No cookie found for user {chat_id}")
                await context.bot.send_message(chat_id=chat_id, text="⚠️ Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại bằng lệnh /login")
                user_states[chat_id]['is_running'] = False
                break

            # Check if we need to re-login after 10 executions
            if user_states[chat_id]['execution_count'] >= 10:
                print(f"🔄 Debug: Reached 10 executions for user {chat_id}, performing silent re-login")
                login_response, cookie = await login(user_states[chat_id]['username'], user_states[chat_id]['password'])
                if login_response.get('success') and cookie:
                    print(f"✅ Debug: Silent re-login successful for user {chat_id}")
                    user_states[chat_id]['cookie'] = cookie
                    user_states[chat_id]['execution_count'] = 0  # Reset counter
                    print(f"🔍 Debug: New cookie received: {cookie}")
                else:
                    print(f"❌ Debug: Silent re-login failed for user {chat_id}")
                    print(f"❌ Debug: Error message: {login_response.get('message', 'No error message')}")
                    if not cookie:
                        print("❌ Debug: No cookie received during re-login")
                    await context.bot.send_message(chat_id=chat_id, text="❌ Đăng nhập lại thất bại. Vui lòng đăng nhập lại bằng lệnh /login")
                    user_states[chat_id]['is_running'] = False
                    break

            headers = await get_headers_with_cookie(user_states[chat_id]['cookie'])
            print(f"🔍 Debug: Using cookie for user {chat_id}: {user_states[chat_id]['cookie']}")
            
            await context.bot.send_message(chat_id=chat_id, text="🔄 Bắt đầu chu kỳ mới...")
            
            # Randomly select order type
            order_type = random.choice(ORDER_TYPES)
            user_states[chat_id]['order_type'] = order_type
            
            # Check balance before creating order
            balance = await fetch_balance(headers)
            if balance:
                try:
                    balance_int = int(balance)
                    required_balance = 122000 if order_type == 'facebook_share' else 150750
                    
                    if balance_int < required_balance:
                        # Set mode text based on order type
                        if order_type == 'facebook_share':
                            mode_text = "Facebook Share VIP"
                        elif order_type == 'tiktok_follow':
                            mode_text = "TikTok Theo Dõi"
                        else:  # tiktok_follow_global
                            mode_text = "TikTok Theo Dõi Global"
                            
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"⚠️ *Số Pont không đủ cho chế độ {mode_text}!*\n\n"
                                f"💰 Số Pont hiện tại: {balance}\n"
                                f"💵 Số Pont cần thiết: {required_balance:,}\n\n"
                                f"Bot sẽ đợi đến chu kỳ tiếp theo...",
                            parse_mode='Markdown'
                        )
                        # Set waiting flag to true before the wait period
                        user_states[chat_id]['is_waiting'] = True
                        
                        # Random wait time between 20-100 seconds
                        wait_time = random.randint(20, 100)
                        
                        # Wait for the appropriate time before next iteration
                        await context.bot.send_message(chat_id=chat_id, text=f"⏳ Đợi {wait_time}s để kiểm tra lại...")
                        await show_control_buttons(context, chat_id)
                        await asyncio.sleep(wait_time)
                        continue
                except (ValueError, TypeError):
                    print(f"❌ Debug: Invalid balance value: {balance}")
                    continue
            
            # Only create order if balance check passed
            # Set mode text based on order type
            if order_type == 'facebook_share':
                mode_text = "Facebook Share VIP"
            elif order_type == 'tiktok_follow':
                mode_text = "TikTok Theo Dõi"
            else:  # tiktok_follow_global
                mode_text = "TikTok Theo Dõi Global"
                
            await context.bot.send_message(chat_id=chat_id, text=f"📝 Đang tạo đơn hàng {mode_text}...")
            
            # Create order based on selected type
            if order_type == 'facebook_share':
                await create_order(headers)
            elif order_type == 'tiktok_follow':
                await create_tiktok_follow_order(headers)
            elif order_type == 'tiktok_follow_global':
                await create_tiktok_follow_global_order(headers)
            
            await context.bot.send_message(chat_id=chat_id, text="✅ Đã tạo đơn hàng thành công!")
            
            # Wait for 2 seconds
            await asyncio.sleep(2)
            
            # Fetch orders based on type
            if order_type == 'facebook_share':
                fetch_response = await fetch_orders(headers)
            elif order_type == 'tiktok_follow':
                fetch_response = await fetch_tiktok_follow_orders(headers)
            elif order_type == 'tiktok_follow_global':
                fetch_response = await fetch_tiktok_follow_global_orders(headers)
            
            if fetch_response.get('data'):
                order = fetch_response['data'][0]
                code = order['code']
                await context.bot.send_message(chat_id=chat_id, text=f"🔍 Đã tìm thấy đơn hàng với mã: {code}")
                
                # Random wait time between 2-10 seconds before canceling
                cancel_wait = random.randint(2, 10)
                await context.bot.send_message(chat_id=chat_id, text=f"⏳ Đợi {cancel_wait}s trước khi hủy đơn hàng...")
                await asyncio.sleep(cancel_wait)
                
                # Cancel order based on type
                if order_type == 'facebook_share':
                    cancel_response = await cancel_order(code, headers)
                elif order_type == 'tiktok_follow':
                    cancel_response = await cancel_tiktok_follow_order(code, headers)
                elif order_type == 'tiktok_follow_global':
                    cancel_response = await cancel_tiktok_follow_global_order(code, headers)
                
                await context.bot.send_message(chat_id=chat_id, text=f"✅ Đã hủy đơn hàng với mã: {code}")
            
            # Increment execution counter
            user_states[chat_id]['execution_count'] += 1
            print(f"🔍 Debug: Execution count for user {chat_id}: {user_states[chat_id]['execution_count']}")
            
            if order_type == 'facebook_share':
                await context.bot.send_message(chat_id=chat_id, text="🎉 Thưởng hoàn thành nhiệm vụ + 2000 Pont")
            else:
                await context.bot.send_message(chat_id=chat_id, text="🎉 Thưởng hoàn thành nhiệm vụ + 750 Pont")
                
            # Fetch and display current balance before waiting
            balance = await fetch_balance(headers)
            if balance:
                await context.bot.send_message(chat_id=chat_id, text=f"💰 Số Pont hiện tại: {balance}")
            
            # Set waiting flag to true before the wait period
            user_states[chat_id]['is_waiting'] = True
            
            # Random wait time between 20-100 seconds
            wait_time = random.randint(20, 100)
            
            # Wait for the appropriate time before next iteration
            await context.bot.send_message(chat_id=chat_id, text=f"⏳ Đợi {wait_time}s để kiểm tra lại...")
            
            print("🔍 Debug: About to show control buttons after cycle")
            # Show control buttons before next iteration
            await show_control_buttons(context, chat_id)
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            print(f"❌ Debug: Error in automation_loop: {str(e)}")
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Có lỗi xảy ra: {str(e)}")
            await asyncio.sleep(5)
            # Show control buttons after error
            print("🔍 Debug: About to show control buttons after error")
            await show_control_buttons(context, chat_id)

async def is_authorized(chat_id: int) -> bool:
    """Check if user is authorized to use the bot"""
    return chat_id in AUTHORIZED_USERS

async def send_admin_notification(context: ContextTypes.DEFAULT_TYPE, user_id: int, username: str, first_name: str, last_name: str):
    """Helper function to send notification to admin with verify/reject buttons"""
    try:
        user_info = f"User ID: {user_id}\nUsername: {username}\nFirst Name: {first_name}\nLast Name: {last_name}"
        
        # Create verify and reject buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Xác nhận", callback_data=f'verify_{user_id}'),
                InlineKeyboardButton("❌ Từ chối", callback_data=f'reject_{user_id}')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=CSKH_ID,
            text=f"🔔 *Yêu cầu xác nhận người dùng mới:*\n\n{user_info}\n\nVui lòng xác nhận hoặc từ chối người dùng này:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"❌ Error sending admin notification: {str(e)}")
        # Continue execution even if admin notification fails
        pass

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Initialize user state if not exists
    if chat_id not in user_states:
        user_states[chat_id] = {
            'is_running': False,
            'task': None,
            'username': None,
            'password': None,
            'cookie': None,
            'execution_count': 0,
            'order_type': None  # Will be randomly selected
        }
    
    keyboard = [
        [
            InlineKeyboardButton("💎 Nhấn vào đây để thuê", callback_data='hire')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "🤖 *Chào mừng bạn đến với 🔧 𝗧𝗮𝗽𝗦𝗵𝗶𝗳𝘁 𝗧&𝗡*\n\n"
        "Giải pháp tối ưu thao tác tay và tự động hóa thông minh – giúp bạn rút ngắn thời gian, tăng độ chính xác, và linh hoạt xử lý mọi tình huống.\n\n"
        "✅ *Cam kết minh bạch:* Tool hoàn toàn không chứa BOTNET, không mã độc, tuyệt đối an toàn cho thiết bị của bạn.\n\n"
        "🎯 Được thiết kế dành riêng cho những người dùng cần một trợ lý ảo hiệu quả, đáng tin cậy và mạnh mẽ trong từng cú click.\n\n"
        "🚀 Sẵn sàng? Hãy bắt đầu hành trình tự động hóa ngay bây giờ!"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    
    # Initialize user state if not exists
    if chat_id not in user_states:
        user_states[chat_id] = {
            'is_running': False,
            'task': None,
            'username': None,
            'password': None,
            'cookie': None,
            'execution_count': 0,
            'order_type': None  # Will be randomly selected
        }
    
    # Handle verify/reject buttons
    if query.data.startswith('verify_'):
        if chat_id != CSKH_ID:
            await query.edit_message_text("❌ Bạn không có quyền thực hiện hành động này.")
            return
            
        user_id = int(query.data.split('_')[1])
        AUTHORIZED_USERS.add(user_id)
        save_authorized_users()
        
        # Notify CSKH
        await query.edit_message_text(f"✅ Đã xác nhận user {user_id}.")
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Bạn đã được xác nhận để sử dụng hệ thống.\n\nVui lòng sử dụng lại lệnh /start để bắt đầu."
            )
        except Exception as e:
            print(f"❌ Error notifying user: {str(e)}")
        return
        
    elif query.data.startswith('reject_'):
        if chat_id != CSKH_ID:
            await query.edit_message_text("❌ Bạn không có quyền thực hiện hành động này.")
            return
            
        user_id = int(query.data.split('_')[1])
        
        # Notify CSKH
        await query.edit_message_text(f"❌ Đã từ chối user {user_id}.")
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Yêu cầu sử dụng hệ thống của bạn đã bị từ chối."
            )
        except Exception as e:
            print(f"❌ Error notifying user: {str(e)}")
        return
    
    if query.data == 'hire':
        await query.edit_message_text("Đang tải thông tin thanh toán...")  # Xóa nút cũ
        success = await send_photo_from_base64(
            context=context,
            chat_id=chat_id,
            image_path="qr_code.png",
            caption=(
                "📞 *Vui lòng quét mã QR để thanh toán và liên hệ qua CSKH:* @CSKH110222229\n\n"
                "💡 *Để được hướng dẫn thanh toán và cấp tài khoản vào hệ thống.*\n\n"
                "⚠️ *Lưu ý:* Sau khi thực hiện thanh toán vui lòng gửi Bill cho bộ phận CSKH để chuyên viên hỗ trợ bạn nhé!"
            )
        )
        if not success:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Không thể tải hình ảnh. Vui lòng thử lại sau."
            )
        return
    
    if query.data == 'login':
        # Check if user is authorized
        if not await is_authorized(chat_id):
            # Send notification to CSKH
            await send_admin_notification(
                context=context,
                user_id=chat_id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name,
                last_name=update.effective_user.last_name
            )
            
            # Notify user
            await query.edit_message_text(
                "🎯 *Kết luận:*\n\n"
                "❌ Người lạ gửi lệnh → bị chặn hoàn toàn\n\n"
                "✅ Chỉ bạn hoặc người bạn cho phép mới sử dụng được bot\n\n"
                "⏳ Yêu cầu của bạn đã được gửi đến CSKH. Vui lòng đợi xác nhận.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        await query.edit_message_text(
            "👤 *Vui lòng nhập tên đăng nhập của bạn:*\n\n"
            "📝 Gửi tin nhắn chứa tên đăng nhập của bạn.",
            parse_mode='Markdown'
        )
        return WAITING_USERNAME
    
    # Check if user is logged in
    if not user_states[chat_id].get('cookie'):
        await query.edit_message_text(
            "⚠️ *Vui lòng đăng nhập trước*\n\n"
            "Nhấn nút Đăng nhập để tiếp tục.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔐 Đăng nhập", callback_data='login')
            ]]),
            parse_mode='Markdown'
        )
        return
    
    print(f"🔍 Debug: button_callback called with chat_id: {chat_id}")
    
    if query.data == 'start_auto':
        # Check balance before starting
        headers = await get_headers_with_cookie(user_states[chat_id]['cookie'])
        balance = await fetch_balance(headers)
        if balance:
            try:
                balance_int = int(balance)
                if balance_int < 122000:  # Minimum required balance
                    await query.edit_message_text(
                        f"⚠️ *Số Pont không đủ!*\n\n"
                        f"💰 Số Pont hiện tại: {balance}\n"
                        f"💵 Số Pont cần thiết: 122,000\n\n"
                        f"Vui lòng nạp thêm Pont để tiếp tục.",
                        parse_mode='Markdown'
                    )
                    return
            except (ValueError, TypeError):
                print(f"❌ Debug: Invalid balance value: {balance}")
        
        user_states[chat_id]['is_running'] = True
        user_states[chat_id]['task'] = asyncio.create_task(automation_loop(context, chat_id))
        
        await query.edit_message_text(
            "🚀 *Bot đang chạy tự động...*\n\n"
            "Bot sẽ tự động chọn ngẫu nhiên các chế độ để chạy.",
            parse_mode='Markdown'
        )
    
    elif query.data == 'stop':
        if user_states[chat_id]['is_running']:
            user_states[chat_id]['is_running'] = False
            if user_states[chat_id]['task']:
                user_states[chat_id]['task'].cancel()
            
            await query.edit_message_text("🛑 *Bot đã dừng!*", parse_mode='Markdown')
        else:
            await query.edit_message_text("ℹ️ *Bot chưa được khởi động!*", parse_mode='Markdown')

async def handle_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_states[chat_id]['username'] = update.message.text
    
    # Delete the user's message containing username
    await update.message.delete()
    
    await update.message.reply_text(
        "🔑 *Vui lòng nhập mật khẩu của bạn:*\n\n"
        "📝 Gửi tin nhắn chứa mật khẩu của bạn.\n\n"
        "⚠️ *Lưu ý:* Mật khẩu của bạn sẽ được bảo mật.",
        parse_mode='Markdown'
    )
    return WAITING_PASSWORD

async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_states[chat_id]['password'] = update.message.text
    
    # Delete the user's message containing password
    await update.message.delete()
    
    print(f"🔍 Debug: Processing login for user {chat_id}")
    print(f"🔍 Debug: Username: {user_states[chat_id]['username']}")
    print(f"🔍 Debug: Password length: {len(user_states[chat_id]['password'])}")
    
    # Try to login
    login_response, cookie = await login(user_states[chat_id]['username'], user_states[chat_id]['password'])
    
    if isinstance(login_response, dict) and login_response.get('success') and cookie:
        user_states[chat_id]['cookie'] = cookie
        print(f"🔍 Debug: Login successful for user {chat_id}")
        print(f"🔍 Debug: Cookie received: {cookie}")
        
        # Show success message
        await update.message.reply_text(
            "✅ *Đăng nhập thành công!*\n\n"
            "Vui lòng nhấn nút Bắt đầu để chạy bot:",
            parse_mode='Markdown'
        )
        
        # Show control buttons menu with only start button
        await show_control_buttons(context, chat_id)
        return ConversationHandler.END
    else:
        print(f"❌ Debug: Login failed for user {chat_id}")
        error_message = "Tài khoản hoặc mật khẩu không chính xác"
        if isinstance(login_response, dict):
            error_message = login_response.get('message', error_message)
        print(f"❌ Debug: Error message: {error_message}")
        if not cookie:
            print("❌ Debug: No cookie received from server")
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Thử lại", callback_data='retry_login')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ *Đăng nhập thất bại:* {error_message}\n\n"
            "Vui lòng thử lại:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return WAITING_RETRY

async def handle_retry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    
    if query.data == 'retry_login':
        # Clear previous login data
        user_states[chat_id]['username'] = None
        user_states[chat_id]['password'] = None
        user_states[chat_id]['cookie'] = None
        
        await query.edit_message_text(
            "👤 *Vui lòng nhập tên đăng nhập của bạn:*\n\n"
            "📝 Gửi tin nhắn chứa tên đăng nhập của bạn.",
            parse_mode='Markdown'
        )
        return WAITING_USERNAME
    
    return ConversationHandler.END

async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Check if user is authorized
    if not await is_authorized(chat_id):
        # Send notification to CSKH
        await send_admin_notification(
            context=context,
            user_id=chat_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name
        )
        
        # Notify user
        await update.message.reply_text(
            "🎯 *Kết luận:*\n\n"
            "❌ Người lạ gửi lệnh → bị chặn hoàn toàn\n\n"
            "✅ Chỉ bạn hoặc người bạn cho phép mới sử dụng được bot\n\n"
            "⏳ Yêu cầu của bạn đã được gửi đến CSKH. Vui lòng đợi xác nhận.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    # Initialize user state if not exists
    if chat_id not in user_states:
        user_states[chat_id] = {
            'is_running': False,
            'task': None,
            'username': None,
            'password': None,
            'cookie': None,
            'execution_count': 0,
            'order_type': None  # Will be randomly selected
        }
    
    await update.message.reply_text(
        "👤 *Vui lòng nhập tên đăng nhập của bạn:*\n\n"
        "📝 Gửi tin nhắn chứa tên đăng nhập của bạn.",
        parse_mode='Markdown'
    )
    return WAITING_USERNAME

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_states:
        await update.message.reply_text("❌ Bạn chưa đăng nhập. Vui lòng sử dụng lệnh /login")
        return

    if user_states[chat_id]['is_running']:
        user_states[chat_id]['is_running'] = False
        if user_states[chat_id]['task']:
            user_states[chat_id]['task'].cancel()
        
        await show_control_buttons(context, chat_id)
    else:
        await update.message.reply_text("ℹ️ Bot chưa được khởi động!")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show menu with control buttons"""
    chat_id = update.effective_chat.id
    
    # Check if user is logged in
    if not user_states[chat_id].get('cookie'):
        await update.message.reply_text(
            "⚠️ *Vui lòng đăng nhập trước*\n\n"
            "Nhấn nút Đăng nhập để tiếp tục.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔐 Đăng nhập", callback_data='login')
            ]]),
            parse_mode='Markdown'
        )
        return
    
    # Show control buttons menu
    await show_control_buttons(context, chat_id)

async def post_init(application: Application) -> None:
    commands = [
        BotCommand("start", "Bắt đầu sử dụng bot"),
        BotCommand("login", "Đăng nhập vào hệ thống"),
        BotCommand("menu", "Hiển thị menu điều khiển")
    ]
    await application.bot.set_my_commands(commands)

async def verify_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify a user (CSKH only)"""
    chat_id = update.effective_chat.id
    
    # Check if command is from CSKH
    if chat_id != CSKH_ID:
        await update.message.reply_text("❌ Bạn không có quyền thực hiện lệnh này.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ Vui lòng cung cấp ID của người dùng cần xác nhận.\n"
            "Ví dụ: /verify 123456789"
        )
        return
    
    try:
        user_id = int(context.args[0])
        AUTHORIZED_USERS.add(user_id)
        save_authorized_users()
        
        # Notify CSKH
        await update.message.reply_text(f"✅ Đã xác nhận user {user_id}.")
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Bạn đã được xác nhận để sử dụng hệ thống.\n\nVui lòng sử dụng lại lệnh /login để bắt đầu."
            )
        except Exception as e:
            print(f"❌ Error notifying user: {str(e)}")
            
    except ValueError:
        await update.message.reply_text("❌ ID người dùng không hợp lệ.")

def main():
    request = HTTPXRequest(connect_timeout=10.0, read_timeout=10.0)
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).build()
    
    # Set up commands using post_init
    application.post_init = post_init
    
    # Add conversation handler for login
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("login", login_command),
            CallbackQueryHandler(button_callback, pattern='^login$')
        ],
        states={
            WAITING_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_username)],
            WAITING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password)],
            WAITING_RETRY: [CallbackQueryHandler(handle_retry, pattern='^retry_login$')],
        },
        fallbacks=[],
    )
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("verify", verify_user_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 Bot đang chạy...")
    while True:
        try:
            application.run_polling(allowed_updates=Update.ALL_TYPES)
        except telegram.error.TimedOut:
            print("❌ Timed out, restarting polling in 10s...")
            time.sleep(10)
        except Exception as e:
            print(f"❌ Unexpected error: {e}, restarting in 10s...")
            time.sleep(10)

if __name__ == '__main__':
    main() 