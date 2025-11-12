from pyrogram.errors import (
    InputUserDeactivated, UserNotParticipant, FloodWait, 
    UserIsBlocked, PeerIdInvalid, ChatAdminRequired
)
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
import sqlite3
import asyncio
import datetime
import time
import logging
from contextlib import contextmanager

# ==================== ⚙️ CONFIGURATION - EDIT HERE ====================
API_ID = 1  # Get from my.telegram.org
API_HASH = "eb9"  # Get from my.telegram.org
BOT_TOKEN = "6A"  # Get from @BotFather
OWNER_ID = 7548822418  # Your Telegram User ID

# Bot Messages
GROUP_WELCOME_TEXT = """🎉 Welcome, {user}!

Your join request has been approved! ✅

⚠️ You are currently **muted** for verification.

👇 Click the button below to unmute yourself:"""

UNMUTED_TEXT = """✅ **Verification Successful!**

🎊 Congratulations, {user}!

You have been **unmuted** in **{chat}**.

💬 You can now send messages and participate in the group!

🙏 Thank you for verifying!

━━━━━━━━━━━━━━━━━━━━
⚡ Powered by Auto Accept Bot"""

START_TEXT = """👋 Hello {mention}!

I'm an **Auto Request Accept Bot** that works for all channels.

🔹 Add me to your channel with admin rights
🔹 I'll automatically accept all join requests
🔹 Auto-mute users for verification
🔹 Users click button in group to unmute
🔹 Powered by Pyrogram

💡 Use /help for more information."""

HELP_TEXT = """📚 **Available Commands:**

**For All Users:**
/start - Start the bot
/help - Show this help message

**For Owner Only:**
/stats - Get bot statistics
/broadcast - Broadcast message to all users
/addsudo <user_id> - Add sudo user
/rmsudo <user_id> - Remove sudo user
/listsudo - List all sudo users

**For Sudo Users:**
/stats - Get bot statistics
/broadcast - Broadcast message to all users

⚡ **Auto Features:**
• Automatically accepts all join requests
• Mutes new members for verification
• Sends verification message in the group
• Unmutes users when they start the bot
• Stores user data securely
• Works 24/7 without interruption"""

# Database Configuration
DB_NAME = 'bot_database.db'

# Logging Configuration
LOG_LEVEL = logging.INFO

# Global variable to store bot username
BOT_USERNAME = None
# ==================== END CONFIGURATION ====================

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== DATABASE SETUP ====================

@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME, timeout=21)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def init_database():
    """Initialize database tables"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    joined_date TEXT
                )
            ''')
            
            # Sudo users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sudo_users (
                    user_id INTEGER PRIMARY KEY,
                    added_by INTEGER,
                    added_date TEXT
                )
            ''')
            
            # Muted users table (for verification)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS muted_users (
                    user_id INTEGER,
                    chat_id INTEGER,
                    chat_title TEXT,
                    muted_date TEXT,
                    PRIMARY KEY (user_id, chat_id)
                )
            ''')
            
            # Stats table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stats (
                    total_requests INTEGER DEFAULT 0,
                    total_messages_sent INTEGER DEFAULT 0,
                    total_unmuted INTEGER DEFAULT 0
                )
            ''')
            
            # Initialize stats if empty
            cursor.execute('SELECT COUNT(*) FROM stats')
            if cursor.fetchone()[0] == 0:
                cursor.execute('INSERT INTO stats (total_requests, total_messages_sent, total_unmuted) VALUES (0, 0, 0)')
            
            logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise

# Database helper functions
def add_user(user_id, username=None, first_name=None):
    """Add or update user in database"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name, joined_date)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, datetime.datetime.now().isoformat()))
            return True
    except Exception as e:
        logger.error(f"Error adding user {user_id}: {e}")
        return False

def get_all_users():
    """Get all user IDs"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users')
            return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return []

def get_user_count():
    """Get total user count"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error getting user count: {e}")
        return 0

def add_sudo_user(user_id, added_by):
    """Add sudo user"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO sudo_users (user_id, added_by, added_date)
                VALUES (?, ?, ?)
            ''', (user_id, added_by, datetime.datetime.now().isoformat()))
            return True
    except Exception as e:
        logger.error(f"Error adding sudo user {user_id}: {e}")
        return False

def remove_sudo_user(user_id):
    """Remove sudo user"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sudo_users WHERE user_id = ?', (user_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error removing sudo user {user_id}: {e}")
        return False

def is_sudo_user(user_id):
    """Check if user is sudo"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM sudo_users WHERE user_id = ?', (user_id,))
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking sudo status: {e}")
        return False

def get_all_sudo_users():
    """Get all sudo users"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM sudo_users')
            return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching sudo users: {e}")
        return []

def add_muted_user(user_id, chat_id, chat_title):
    """Add muted user to database"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO muted_users (user_id, chat_id, chat_title, muted_date)
                VALUES (?, ?, ?, ?)
            ''', (user_id, chat_id, chat_title, datetime.datetime.now().isoformat()))
            return True
    except Exception as e:
        logger.error(f"Error adding muted user {user_id}: {e}")
        return False

def get_muted_user(user_id):
    """Get muted user information"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, chat_id, chat_title FROM muted_users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            if result:
                return {'user_id': result[0], 'chat_id': result[1], 'chat_title': result[2]}
            return None
    except Exception as e:
        logger.error(f"Error getting muted user {user_id}: {e}")
        return None

def remove_muted_user(user_id, chat_id):
    """Remove user from muted list"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM muted_users WHERE user_id = ? AND chat_id = ?', (user_id, chat_id))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error removing muted user {user_id}: {e}")
        return False

def increment_stats():
    """Increment request count"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE stats SET total_requests = total_requests + 1')
    except Exception as e:
        logger.error(f"Error incrementing stats: {e}")

def increment_messages_sent():
    """Increment messages sent count"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE stats SET total_messages_sent = total_messages_sent + 1')
    except Exception as e:
        logger.error(f"Error incrementing messages sent: {e}")

def increment_unmuted():
    """Increment unmuted count"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE stats SET total_unmuted = total_unmuted + 1')
    except Exception as e:
        logger.error(f"Error incrementing unmuted: {e}")

def get_stats():
    """Get bot statistics"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT total_requests, total_messages_sent, total_unmuted FROM stats')
            result = cursor.fetchone()
            return {'requests': result[0], 'messages': result[1], 'unmuted': result[2]}
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {'requests': 0, 'messages': 0, 'unmuted': 0}

# ==================== BOT INITIALIZATION ====================
Bot = Client(
    name='AutoAcceptBot',
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ==================== FILTERS ====================
def is_owner(_, __, m):
    return m.from_user.id == OWNER_ID

def is_sudo(_, __, m):
    return m.from_user.id == OWNER_ID or is_sudo_user(m.from_user.id)

owner_filter = filters.create(is_owner)
sudo_filter = filters.create(is_sudo)

# ==================== COMMAND HANDLERS ====================

@Bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    """Start command handler with deep link parameter support"""
    user = message.from_user
    add_user(user.id, user.username, user.first_name)
    
    # Check if there's a start parameter (deep link)
    if len(message.command) > 1:
        param = message.command[1]
        
        # Check if it's an unmute request
        if param.startswith('unmute_'):
            try:
                # Parse parameter: unmute_chatid_userid
                parts = param.split('_')
                if len(parts) != 3:
                    await message.reply_text("❌ Invalid verification link!")
                    return
                
                chat_id = int(parts[1])
                user_id = int(parts[2])
                
                # Verify the user clicking is the same as the target user
                if user.id != user_id:
                    await message.reply_text("❌ This verification link is not for you!")
                    return
                
                # Get muted user info
                muted_info = get_muted_user(user_id)
                
                if not muted_info:
                    await message.reply_text("⚠️ You are not in the muted list or already unmuted!")
                    return
                
                # Unmute the user (give all permissions)
                try:
                    await client.restrict_chat_member(
                        chat_id=chat_id,
                        user_id=user_id,
                        permissions=ChatPermissions(
                            can_send_messages=True,
                            can_send_media_messages=True,
                            can_send_other_messages=True,
                            can_send_polls=True,
                            can_add_web_page_previews=True,
                            can_change_info=False,
                            can_invite_users=True,
                            can_pin_messages=False
                        )
                    )
                    
                    # Remove from muted users database
                    remove_muted_user(user_id, chat_id)
                    
                    # Increment unmuted stats
                    increment_unmuted()
                    
                    logger.info(f"🔓 Unmuted user {user_id} in chat {chat_id}")
                    
                    # Send success message
                    success_buttons = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton('📢 Updates', url='https://t.me/+k4rG8HAlLAhjZjg1'),
                            InlineKeyboardButton('💬 Support', url='https://t.me/TheSupportPing')
                        ]
                    ])
                    
                    await message.reply_text(
                        UNMUTED_TEXT.format(user=user.mention, chat=muted_info['chat_title']),
                        reply_markup=success_buttons
                    )
                    
                except ChatAdminRequired:
                    logger.error(f"❌ Bot lacks admin rights in chat {chat_id}")
                    await message.reply_text("❌ Bot lacks admin permissions to unmute you! Please contact group admins.")
                except Exception as e:
                    logger.error(f"❌ Error unmuting user {user_id}: {e}")
                    await message.reply_text("❌ Failed to unmute. Please contact support!")
                    
            except Exception as e:
                logger.error(f"❌ Error processing unmute request: {e}")
                await message.reply_text("❌ An error occurred during verification!")
            
            return
    
    # Normal start message (no deep link parameter)
    button = InlineKeyboardMarkup([
        [
            InlineKeyboardButton('📢 Updates', url='https://t.me/+k4rG8HAlLAhjZjg1'),
            InlineKeyboardButton('💬 Support', url='https://t.me/TheSupportPing')
        ],
        [
            InlineKeyboardButton('ℹ️ Help', callback_data='help')
        ]
    ])
    
    await message.reply_text(
        text=START_TEXT.format(mention=user.mention),
        disable_web_page_preview=True,
        reply_markup=button
    )
    logger.info(f"User {user.id} started the bot")

@Bot.on_message(filters.command("help") & filters.private)
async def help_handler(client, message):
    """Help command handler"""
    await message.reply_text(HELP_TEXT)

@Bot.on_message(filters.command("stats") & sudo_filter & filters.private)
async def stats_handler(client, message):
    """Statistics command handler"""
    total_users = get_user_count()
    stats_data = get_stats()
    sudo_count = len(get_all_sudo_users())
    
    stats_text = f"""📊 **Bot Statistics**

👥 Total Users: `{total_users}`
✅ Requests Accepted: `{stats_data['requests']}`
💌 Group Messages Sent: `{stats_data['messages']}`
🔓 Users Unmuted: `{stats_data['unmuted']}`
🛡️ Sudo Users: `{sudo_count}`
👑 Owner: `{OWNER_ID}`

📅 Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    
    await message.reply_text(stats_text)
    logger.info(f"Stats requested by {message.from_user.id}")

@Bot.on_message(filters.command("broadcast") & sudo_filter & filters.private)
async def broadcast_handler(client, message):
    """Broadcast command handler"""
    if not message.reply_to_message:
        return await message.reply_text("❌ Please reply to a message to broadcast it!")
    
    b_msg = message.reply_to_message
    users = get_all_users()
    total_users = len(users)
    
    if total_users == 0:
        return await message.reply_text("❌ No users found in database!")
    
    sts = await message.reply_text("🔄 Broadcasting your message...")
    
    success = 0
    failed = 0
    deleted = 0
    blocked = 0
    start_time = time.time()
    
    for user_id in users:
        try:
            await b_msg.copy(chat_id=user_id)
            success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await b_msg.copy(chat_id=user_id)
                success += 1
            except:
                failed += 1
        except InputUserDeactivated:
            deleted += 1
            failed += 1
        except UserIsBlocked:
            blocked += 1
            failed += 1
        except PeerIdInvalid:
            deleted += 1
            failed += 1
        except Exception as e:
            logger.error(f"Broadcast error for {user_id}: {e}")
            failed += 1
        
        # Update progress every 20 users
        if (success + failed) % 20 == 0:
            try:
                await sts.edit_text(
                    f"🔄 **Broadcasting...**\n\n"
                    f"Total: `{total_users}`\n"
                    f"✅ Success: `{success}`\n"
                    f"❌ Failed: `{failed}`\n"
                    f"🗑️ Deleted: `{deleted}`\n"
                    f"🚫 Blocked: `{blocked}`"
                )
            except:
                pass
        
        await asyncio.sleep(0.1)
    
    time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
    
    await sts.delete()
    await message.reply_text(
        f"✅ **Broadcast Completed!**\n\n"
        f"⏱️ Time: `{time_taken}`\n"
        f"👥 Total Users: `{total_users}`\n"
        f"✅ Success: `{success}`\n"
        f"❌ Failed: `{failed}`\n"
        f"🗑️ Deleted: `{deleted}`\n"
        f"🚫 Blocked: `{blocked}`"
    )
    logger.info(f"Broadcast completed by {message.from_user.id}: {success}/{total_users} successful")

@Bot.on_message(filters.command("addsudo") & owner_filter & filters.private)
async def add_sudo_handler(client, message):
    """Add sudo user command (Owner only)"""
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/addsudo <user_id>`")
    
    try:
        user_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ Invalid user ID! Please provide a numeric ID.")
    
    if user_id == OWNER_ID:
        return await message.reply_text("❌ Owner is already a sudo user!")
    
    if is_sudo_user(user_id):
        return await message.reply_text(f"⚠️ User `{user_id}` is already a sudo user!")
    
    if add_sudo_user(user_id, OWNER_ID):
        await message.reply_text(f"✅ User `{user_id}` added as sudo user successfully!")
        logger.info(f"Sudo user added: {user_id}")
        
        try:
            await client.send_message(
                user_id,
                "🎉 **Congratulations!**\n\nYou have been promoted to **Sudo User** by the bot owner.\n\n"
                "You now have access to admin commands like /stats and /broadcast."
            )
        except:
            pass
    else:
        await message.reply_text(f"❌ Failed to add user `{user_id}` as sudo user!")

@Bot.on_message(filters.command("rmsudo") & owner_filter & filters.private)
async def remove_sudo_handler(client, message):
    """Remove sudo user command (Owner only)"""
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/rmsudo <user_id>`")
    
    try:
        user_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ Invalid user ID! Please provide a numeric ID.")
    
    if user_id == OWNER_ID:
        return await message.reply_text("❌ Cannot remove owner from sudo list!")
    
    if not is_sudo_user(user_id):
        return await message.reply_text(f"⚠️ User `{user_id}` is not a sudo user!")
    
    if remove_sudo_user(user_id):
        await message.reply_text(f"✅ User `{user_id}` removed from sudo users successfully!")
        logger.info(f"Sudo user removed: {user_id}")
        
        try:
            await client.send_message(
                user_id,
                "⚠️ **Notice**\n\nYour sudo user privileges have been revoked by the bot owner."
            )
        except:
            pass
    else:
        await message.reply_text(f"❌ Failed to remove user `{user_id}` from sudo users!")

@Bot.on_message(filters.command("listsudo") & owner_filter & filters.private)
async def list_sudo_handler(client, message):
    """List all sudo users (Owner only)"""
    sudo_users = get_all_sudo_users()
    
    if not sudo_users:
        return await message.reply_text("📝 No sudo users found.")
    
    sudo_list = "\n".join([f"• `{user_id}`" for user_id in sudo_users])
    await message.reply_text(
        f"🛡️ **Sudo Users List** ({len(sudo_users)}):\n\n{sudo_list}\n\n👑 Owner: `{OWNER_ID}`"
    )

# ==================== AUTO ACCEPT HANDLER ====================

@Bot.on_chat_join_request()
async def auto_accept_handler(client, join_request):
    """Automatically accept join requests, mute user, and send message in group"""
    global BOT_USERNAME
    
    user = join_request.from_user
    chat = join_request.chat
    
    try:
        # Get bot username if not already set
        if BOT_USERNAME is None:
            me = await client.get_me()
            BOT_USERNAME = me.username
        
        # Add user to database
        add_user(user.id, user.username, user.first_name)
        
        # Approve the request
        await join_request.approve()
        
        # Increment stats
        increment_stats()
        
        logger.info(f"✅ Approved join request from {user.id} ({user.first_name}) for {chat.title}")
        
        # Mute the user (restrict all permissions)
        try:
            await client.restrict_chat_member(
                chat_id=chat.id,
                user_id=user.id,
                permissions=ChatPermissions()
            )
            
            # Add to muted users database
            add_muted_user(user.id, chat.id, chat.title)
            
            logger.info(f"🔇 Muted user {user.id} in {chat.title}")
            
        except Exception as e:
            logger.error(f"❌ Failed to mute user {user.id}: {e}")
        
        # Send message in the GROUP with unmute button (deep link)
        try:
            # Create deep link: https://t.me/botusername?start=unmute_chatid_userid
            deep_link = f"https://t.me/{BOT_USERNAME}?start=unmute_{chat.id}_{user.id}"
            
            group_button = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton('🔓 CLICK TO UNMUTE', url=deep_link)
                ]
            ])
            
            await client.send_message(
                chat_id=chat.id,
                text=GROUP_WELCOME_TEXT.format(user=user.mention),
                reply_markup=group_button
            )
            
            # Increment message sent stats
            increment_messages_sent()
            
            logger.info(f"💌 Verification message sent in group {chat.title} for user {user.id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send message in group {chat.id}: {e}")
        
    except ChatAdminRequired:
        logger.error(f"❌ Bot lacks admin rights in {chat.title}")
    except FloodWait as e:
        logger.warning(f"⏳ FloodWait: Sleeping for {e.value} seconds")
        await asyncio.sleep(e.value)
        try:
            await join_request.approve()
            increment_stats()
        except Exception as retry_error:
            logger.error(f"❌ Retry failed: {retry_error}")
    except Exception as e:
        logger.error(f"❌ Error processing join request from {user.id}: {e}")

# ==================== CALLBACK QUERY HANDLER ====================

@Bot.on_callback_query()
async def callback_handler(client, callback_query):
    """Handle inline button callbacks"""
    data = callback_query.data
    
    if data == "help":
        await callback_query.message.edit_text(
            HELP_TEXT,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('🔙 Back', callback_data='back')
            ]])
        )
        await callback_query.answer()
    
    elif data == "back":
        button = InlineKeyboardMarkup([
            [
                InlineKeyboardButton('📢 Updates', url='https://t.me/+k4rG8HAlLAhjZjg1'),
                InlineKeyboardButton('💬 Support', url='https://t.me/TheSupportPing')
            ],
            [
                InlineKeyboardButton('ℹ️ Help', callback_data='help')
            ]
        ])
        await callback_query.message.edit_text(
            START_TEXT.format(mention=callback_query.from_user.mention),
            reply_markup=button
        )
        await callback_query.answer()
    
    else:
        await callback_query.answer()

# ==================== MAIN ====================

async def main():
    global BOT_USERNAME
    
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("🚀 Starting Auto Request Accept Bot...")
    logger.info(f"👑 Owner ID: {OWNER_ID}")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Initialize database
    init_database()
    
    # Start the bot
    await Bot.start()
    
    # Get bot username
    me = await Bot.get_me()
    BOT_USERNAME = me.username
    logger.info(f"🤖 Bot Username: @{BOT_USERNAME}")
    
    logger.info("✅ Bot is running and ready to accept requests!")
    logger.info("💌 Group message feature is active!")
    logger.info("🔇 Auto-mute verification system is active!")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Keep the bot running
    await idle()
    
    # Stop the bot gracefully
    await Bot.stop()

import os
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

def run_web_dummy():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    print(f"✅ Dummy server running on port {port}")
    server.serve_forever()

# Start a dummy web server so Render doesn't time out
threading.Thread(target=run_web_dummy, daemon=True).start()



if __name__ == "__main__":
    Bot.run(main())


