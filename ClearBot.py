import asyncio
import sys
import os
import time
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel, MessageMediaDocument, MessageMediaPhoto, MessageMediaWebPage
from telethon.tl.functions.messages import DeleteHistoryRequest, GetHistoryRequest
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.errors import MessageIdInvalidError

# Add TgLiszt directory to path if it's not in the same directory
sys.path.append(os.path.join(os.path.dirname(__file__), 'TgLiszt'))

# Import TgLiszt modules
try:
    from TgLiszt.telegram import Telegram, SessionManager
except ImportError:
    try:
        from telegram import Telegram, SessionManager
    except ImportError:
        print("Error: TgLiszt module not found. Make sure it's in the same directory or in the TgLiszt subdirectory.")
        sys.exit(1)

# Constants
VERSION = "1.0.0"
CREATOR = "@l27_0"

# API credentials
API_ID = 23136380
API_HASH = "6ae6541159e229499615953de667675c"
SESSION_NAME = "Clear"

# Initialize the client
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# Store active operations
active_operations = {}

# Helper function to format time
def format_time(seconds):
    if seconds < 60:
        return f"{seconds:.1f} ثانیه"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} دقیقه"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} ساعت"

# Helper function to create operation
def create_operation(operation_type):
    operation_id = f"{operation_type}_{int(time.time())}"
    active_operations[operation_id] = {
        'cancel': False,
        'start_time': time.time(),
        'processed': 0,
        'success': 0,
        'failed': 0
    }
    return operation_id

# Helper function to update progress message
async def update_progress(message, operation_id, total, current, operation_name, progress_text):
    try:
        elapsed = time.time() - active_operations[operation_id]['start_time']
        progress = (current + 1) / total * 100 if total > 0 else 100
        await message.edit(
            f"🔄 **{progress_text} ({progress:.1f}%)**\n"
            f"📊 **تعداد کل {operation_name}:** {total}\n"
            f"✅ **موفق:** {active_operations[operation_id]['success']}\n"
            f"❌ **ناموفق:** {active_operations[operation_id]['failed']}\n"
            f"⏳ **زمان سپری شده:** {format_time(elapsed)}"
        )
    except MessageIdInvalidError:
        # If message can't be edited, send a new one
        await message.respond(
            f"🔄 **{progress_text} ({progress:.1f}%)**\n"
            f"📊 **تعداد کل {operation_name}:** {total}\n"
            f"✅ **موفق:** {active_operations[operation_id]['success']}\n"
            f"❌ **ناموفق:** {active_operations[operation_id]['failed']}\n"
            f"⏳ **زمان سپری شده:** {format_time(elapsed)}"
        )

# Helper function to show final results
async def show_final_results(message, operation_id, total, operation_name, success_text):
    try:
        elapsed = time.time() - active_operations[operation_id]['start_time']
        await message.edit(
            f"✅ **{success_text}**\n"
            f"📊 **تعداد کل {operation_name}:** {total}\n"
            f"✅ **موفق:** {active_operations[operation_id]['success']}\n"
            f"❌ **ناموفق:** {active_operations[operation_id]['failed']}\n"
            f"⏳ **زمان کل:** {format_time(elapsed)}"
        )
    except MessageIdInvalidError:
        # If message can't be edited, send a new one
        await message.respond(
            f"✅ **{success_text}**\n"
            f"📊 **تعداد کل {operation_name}:** {total}\n"
            f"✅ **موفق:** {active_operations[operation_id]['success']}\n"
            f"❌ **ناموفق:** {active_operations[operation_id]['failed']}\n"
            f"⏳ **زمان کل:** {format_time(elapsed)}"
        )

# Helper function to parse date string
def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

# Command handler for date-based cleanup
@client.on(events.NewMessage(outgoing=True, pattern=r'^delete before (\d{4}-\d{2}-\d{2})$'))
async def delete_before_date_cmd(event):
    await event.delete()
    date_str = event.pattern_match.group(1)
    date = parse_date(date_str)
    if not date:
        await event.respond("❌ **فرمت تاریخ نامعتبر است. لطفاً از فرمت YYYY-MM-DD استفاده کنید.**")
        return
    await delete_before_date(event, date)

async def delete_before_date(event, target_date):
    operation_id = create_operation("delete_before_date")
    message = await event.respond(
        f"🔄 **در حال پاکسازی پیام‌های قبل از {target_date.strftime('%Y-%m-%d')}...**\n"
        "⏳ لطفاً صبر کنید..."
    )
    
    try:
        dialogs = await client.get_dialogs()
        total_messages = 0
        deleted_messages = 0
        failed_messages = 0
        
        for dialog in dialogs:
            if active_operations[operation_id]['cancel']:
                break
                
            try:
                # Get message history
                messages = await client(GetHistoryRequest(
                    peer=dialog.entity,
                    limit=100,  # Process in chunks
                    offset_date=target_date,
                    offset_id=0,
                    max_id=0,
                    min_id=0,
                    add_offset=0,
                    hash=0
                ))
                
                if not messages.messages:
                    continue
                
                total_messages += len(messages.messages)
                
                # Delete messages
                for msg in messages.messages:
                    try:
                        await client.delete_messages(dialog.entity, msg.id)
                        deleted_messages += 1
                        active_operations[operation_id]['success'] += 1
                        
                        if deleted_messages % 10 == 0:  # Update progress every 10 messages
                            await update_progress(
                                message, 
                                operation_id, 
                                total_messages, 
                                deleted_messages, 
                                "پیام", 
                                f"در حال پاکسازی پیام‌های قبل از {target_date.strftime('%Y-%m-%d')}..."
                            )
                        
                        await asyncio.sleep(0.5)  # Prevent flood
                    except Exception as e:
                        failed_messages += 1
                        active_operations[operation_id]['failed'] += 1
                
            except Exception as e:
                continue
        
        await show_final_results(
            message, 
            operation_id, 
            total_messages, 
            "پیام", 
            f"عملیات پاکسازی پیام‌های قبل از {target_date.strftime('%Y-%m-%d')} به پایان رسید"
        )
        
    except Exception as e:
        try:
            await message.edit(f"❌ **خطا در عملیات پاکسازی پیام‌ها:** {str(e)}")
        except MessageIdInvalidError:
            await event.respond(f"❌ **خطا در عملیات پاکسازی پیام‌ها:** {str(e)}")
    finally:
        if operation_id in active_operations:
            del active_operations[operation_id]

# Command handler for keyword-based cleanup
@client.on(events.NewMessage(outgoing=True, pattern=r'^delete contains (.+)$'))
async def delete_contains_cmd(event):
    await event.delete()
    keyword = event.pattern_match.group(1)
    await delete_contains(event, keyword)

async def delete_contains(event, keyword):
    operation_id = create_operation("delete_contains")
    message = await event.respond(
        f"🔄 **در حال پاکسازی پیام‌های حاوی '{keyword}'...**\n"
        "⏳ لطفاً صبر کنید..."
    )
    
    try:
        dialogs = await client.get_dialogs()
        total_messages = 0
        deleted_messages = 0
        failed_messages = 0
        
        for dialog in dialogs:
            if active_operations[operation_id]['cancel']:
                break
                
            try:
                # Get message history
                async for msg in client.iter_messages(dialog.entity, limit=None):
                    if active_operations[operation_id]['cancel']:
                        break
                        
                    try:
                        if msg.text and keyword.lower() in msg.text.lower():
                            await msg.delete()
                            deleted_messages += 1
                            active_operations[operation_id]['success'] += 1
                            
                            if deleted_messages % 10 == 0:  # Update progress every 10 messages
                                await update_progress(
                                    message, 
                                    operation_id, 
                                    total_messages, 
                                    deleted_messages, 
                                    "پیام", 
                                    f"در حال پاکسازی پیام‌های حاوی '{keyword}'..."
                                )
                            
                            await asyncio.sleep(0.5)  # Prevent flood
                    except Exception as e:
                        failed_messages += 1
                        active_operations[operation_id]['failed'] += 1
                
            except Exception as e:
                continue
        
        await show_final_results(
            message, 
            operation_id, 
            total_messages, 
            "پیام", 
            f"عملیات پاکسازی پیام‌های حاوی '{keyword}' به پایان رسید"
        )
        
    except Exception as e:
        try:
            await message.edit(f"❌ **خطا در عملیات پاکسازی پیام‌ها:** {str(e)}")
        except MessageIdInvalidError:
            await event.respond(f"❌ **خطا در عملیات پاکسازی پیام‌ها:** {str(e)}")
    finally:
        if operation_id in active_operations:
            del active_operations[operation_id]

# Command handler for file cleanup
@client.on(events.NewMessage(outgoing=True, pattern=r'^delete files$'))
async def delete_files_cmd(event):
    await event.delete()
    await delete_files(event)

async def delete_files(event):
    operation_id = create_operation("delete_files")
    message = await event.respond(
        "🔄 **در حال پاکسازی فایل‌های ارسالی...**\n"
        "⏳ لطفاً صبر کنید..."
    )
    
    try:
        dialogs = await client.get_dialogs()
        total_messages = 0
        deleted_messages = 0
        failed_messages = 0
        
        for dialog in dialogs:
            if active_operations[operation_id]['cancel']:
                break
                
            try:
                # Get message history
                async for msg in client.iter_messages(dialog.entity, limit=None):
                    if active_operations[operation_id]['cancel']:
                        break
                        
                    try:
                        if msg.media and not isinstance(msg.media, MessageMediaWebPage):
                            await msg.delete()
                            deleted_messages += 1
                            active_operations[operation_id]['success'] += 1
                            
                            if deleted_messages % 10 == 0:  # Update progress every 10 messages
                                await update_progress(
                                    message, 
                                    operation_id, 
                                    total_messages, 
                                    deleted_messages, 
                                    "فایل", 
                                    "در حال پاکسازی فایل‌های ارسالی..."
                                )
                            
                            await asyncio.sleep(0.5)  # Prevent flood
                    except Exception as e:
                        failed_messages += 1
                        active_operations[operation_id]['failed'] += 1
                
            except Exception as e:
                continue
        
        await show_final_results(
            message, 
            operation_id, 
            total_messages, 
            "فایل", 
            "عملیات پاکسازی فایل‌های ارسالی به پایان رسید"
        )
        
    except Exception as e:
        try:
            await message.edit(f"❌ **خطا در عملیات پاکسازی فایل‌ها:** {str(e)}")
        except MessageIdInvalidError:
            await event.respond(f"❌ **خطا در عملیات پاکسازی فایل‌ها:** {str(e)}")
    finally:
        if operation_id in active_operations:
            del active_operations[operation_id]

# Command handler for forwarded messages cleanup
@client.on(events.NewMessage(outgoing=True, pattern=r'^delete forwarded$'))
async def delete_forwarded_cmd(event):
    await event.delete()
    await delete_forwarded(event)

async def delete_forwarded(event):
    operation_id = create_operation("delete_forwarded")
    message = await event.respond(
        "🔄 **در حال پاکسازی پیام‌های فوروارد شده...**\n"
        "⏳ لطفاً صبر کنید..."
    )
    
    try:
        dialogs = await client.get_dialogs()
        total_messages = 0
        deleted_messages = 0
        failed_messages = 0
        
        for dialog in dialogs:
            if active_operations[operation_id]['cancel']:
                break
                
            try:
                # Get message history
                async for msg in client.iter_messages(dialog.entity, limit=None):
                    if active_operations[operation_id]['cancel']:
                        break
                        
                    try:
                        if msg.forward:
                            await msg.delete()
                            deleted_messages += 1
                            active_operations[operation_id]['success'] += 1
                            
                            if deleted_messages % 10 == 0:  # Update progress every 10 messages
                                await update_progress(
                                    message, 
                                    operation_id, 
                                    total_messages, 
                                    deleted_messages, 
                                    "پیام", 
                                    "در حال پاکسازی پیام‌های فوروارد شده..."
                                )
                            
                            await asyncio.sleep(0.5)  # Prevent flood
                    except Exception as e:
                        failed_messages += 1
                        active_operations[operation_id]['failed'] += 1
                
            except Exception as e:
                continue
        
        await show_final_results(
            message, 
            operation_id, 
            total_messages, 
            "پیام", 
            "عملیات پاکسازی پیام‌های فوروارد شده به پایان رسید"
        )
        
    except Exception as e:
        try:
            await message.edit(f"❌ **خطا در عملیات پاکسازی پیام‌های فوروارد شده:** {str(e)}")
        except MessageIdInvalidError:
            await event.respond(f"❌ **خطا در عملیات پاکسازی پیام‌های فوروارد شده:** {str(e)}")
    finally:
        if operation_id in active_operations:
            del active_operations[operation_id]

# Help command handler
@client.on(events.NewMessage(outgoing=True, pattern=r'^/help$|^help$'))
async def help_handler(event):
    help_text = f'''
**🤖 ClearBot {VERSION} راهنما**

**دستورات:**

`leave group` - خروج از تمام گروه ها
`leave channel` - خروج از تمام کانال ها
`delete pv` - حذف تاریخچه چت های خصوصی
`delete bot` - حذف تاریخچه چت با بات ها
`delete before YYYY-MM-DD` - حذف پیام‌های قبل از تاریخ مشخص شده
`delete contains کلمه` - حذف پیام‌های حاوی کلمه خاص
`delete files` - حذف تمام فایل‌های ارسالی
`delete forwarded` - حذف پیام‌های فوروارد شده
`/help` یا `help` - نمایش این راهنما

**سازنده:** {CREATOR}
'''
    await event.reply(help_text)
    await event.delete()

# Command handlers
@client.on(events.NewMessage(outgoing=True, pattern=r'^leave group$'))
async def leave_groups_cmd(event):
    await event.delete()
    await leave_groups(event)

@client.on(events.NewMessage(outgoing=True, pattern=r'^leave channel$'))
async def leave_channels_cmd(event):
    await event.delete()
    await leave_channels(event)

@client.on(events.NewMessage(outgoing=True, pattern=r'^delete pv$'))
async def delete_private_chats_cmd(event):
    await event.delete()
    await delete_private_chats(event)

@client.on(events.NewMessage(outgoing=True, pattern=r'^delete bot$'))
async def delete_bot_chats_cmd(event):
    await event.delete()
    await delete_bot_chats(event)

# Main operation functions
async def leave_groups(event):
    operation_id = create_operation("leave_groups")
    message = await event.respond(
        "🔄 **در حال پردازش گروه ها...**\n"
        "⏳ لطفاً صبر کنید..."
    )
    
    try:
        dialogs = await client.get_dialogs()
        groups = [dialog for dialog in dialogs if isinstance(dialog.entity, (Chat)) or 
                 (isinstance(dialog.entity, Channel) and dialog.entity.megagroup)]
        
        total_groups = len(groups)
        success_list = []
        failed_list = []
        
        await update_progress(message, operation_id, total_groups, 0, "گروه ها", "در حال خروج از گروه ها...")
        
        for i, dialog in enumerate(groups):
            if active_operations[operation_id]['cancel']:
                break
                
            try:
                group_name = dialog.name or "بدون نام"
                await client.delete_dialog(dialog.entity)
                active_operations[operation_id]['success'] += 1
                success_list.append(f"✅ {group_name}")
                
                if (i + 1) % 3 == 0 or i == len(groups) - 1:
                    await update_progress(message, operation_id, total_groups, i, "گروه ها", "در حال خروج از گروه ها...")
                
                await asyncio.sleep(1)
            except Exception as e:
                active_operations[operation_id]['failed'] += 1
                failed_list.append(f"❌ {group_name}: {str(e)}")
        
        await show_final_results(message, operation_id, total_groups, "گروه ها", "عملیات خروج از گروه ها به پایان رسید")
        
    except Exception as e:
        try:
            await message.edit(f"❌ **خطا در عملیات خروج از گروه ها:** {str(e)}")
        except MessageIdInvalidError:
            await event.respond(f"❌ **خطا در عملیات خروج از گروه ها:** {str(e)}")
    finally:
        if operation_id in active_operations:
            del active_operations[operation_id]

async def leave_channels(event):
    operation_id = create_operation("leave_channels")
    message = await event.respond(
        "🔄 **در حال پردازش کانال ها...**\n"
        "⏳ لطفاً صبر کنید..."
    )
    
    try:
        dialogs = await client.get_dialogs()
        channels = [dialog for dialog in dialogs if isinstance(dialog.entity, Channel) and not dialog.entity.megagroup]
        
        total_channels = len(channels)
        success_list = []
        failed_list = []
        
        await update_progress(message, operation_id, total_channels, 0, "کانال ها", "در حال خروج از کانال ها...")
        
        for i, dialog in enumerate(channels):
            if active_operations[operation_id]['cancel']:
                break
                
            try:
                channel_name = dialog.name or "بدون نام"
                await client(LeaveChannelRequest(dialog.entity))
                active_operations[operation_id]['success'] += 1
                success_list.append(f"✅ {channel_name}")
                
                if (i + 1) % 3 == 0 or i == len(channels) - 1:
                    await update_progress(message, operation_id, total_channels, i, "کانال ها", "در حال خروج از کانال ها...")
                
                await asyncio.sleep(1)
            except Exception as e:
                active_operations[operation_id]['failed'] += 1
                failed_list.append(f"❌ {channel_name}: {str(e)}")
        
        await show_final_results(message, operation_id, total_channels, "کانال ها", "عملیات خروج از کانال ها به پایان رسید")
        
    except Exception as e:
        try:
            await message.edit(f"❌ **خطا در عملیات خروج از کانال ها:** {str(e)}")
        except MessageIdInvalidError:
            await event.respond(f"❌ **خطا در عملیات خروج از کانال ها:** {str(e)}")
    finally:
        if operation_id in active_operations:
            del active_operations[operation_id]

async def delete_private_chats(event):
    operation_id = create_operation("delete_pv")
    message = await event.respond(
        "🔄 **در حال پردازش چت های خصوصی...**\n"
        "⏳ لطفاً صبر کنید..."
    )
    
    try:
        dialogs = await client.get_dialogs()
        private_chats = [dialog for dialog in dialogs if isinstance(dialog.entity, User) and not dialog.entity.bot]
        
        total_chats = len(private_chats)
        success_list = []
        failed_list = []
        
        await update_progress(message, operation_id, total_chats, 0, "چت ها", "در حال پاک کردن چت های خصوصی...")
        
        for i, dialog in enumerate(private_chats):
            if active_operations[operation_id]['cancel']:
                break
                
            try:
                user_name = getattr(dialog.entity, 'first_name', '') or "بدون نام"
                if hasattr(dialog.entity, 'last_name') and dialog.entity.last_name:
                    user_name += f" {dialog.entity.last_name}"
                
                await client(DeleteHistoryRequest(
                    peer=dialog.entity,
                    max_id=0,
                    revoke=True
                ))
                active_operations[operation_id]['success'] += 1
                success_list.append(f"✅ {user_name}")
                
                if (i + 1) % 3 == 0 or i == len(private_chats) - 1:
                    await update_progress(message, operation_id, total_chats, i, "چت ها", "در حال پاک کردن چت های خصوصی...")
                
                await asyncio.sleep(1)
            except Exception as e:
                active_operations[operation_id]['failed'] += 1
                failed_list.append(f"❌ {user_name}: {str(e)}")
        
        await show_final_results(message, operation_id, total_chats, "چت ها", "عملیات پاک کردن چت های خصوصی به پایان رسید")
        
    except Exception as e:
        try:
            await message.edit(f"❌ **خطا در عملیات پاک کردن چت های خصوصی:** {str(e)}")
        except MessageIdInvalidError:
            await event.respond(f"❌ **خطا در عملیات پاک کردن چت های خصوصی:** {str(e)}")
    finally:
        if operation_id in active_operations:
            del active_operations[operation_id]

async def delete_bot_chats(event):
    operation_id = create_operation("delete_bots")
    message = await event.respond(
        "🔄 **در حال پردازش بات ها...**\n"
        "⏳ لطفاً صبر کنید..."
    )
    
    try:
        dialogs = await client.get_dialogs()
        bots = [dialog for dialog in dialogs if isinstance(dialog.entity, User) and dialog.entity.bot]
        
        total_bots = len(bots)
        success_list = []
        failed_list = []
        
        await update_progress(message, operation_id, total_bots, 0, "بات ها", "در حال پاک کردن چت بات ها...")
        
        for i, dialog in enumerate(bots):
            if active_operations[operation_id]['cancel']:
                break
                
            try:
                bot_name = dialog.name or "بدون نام"
                await client(DeleteHistoryRequest(
                    peer=dialog.entity,
                    max_id=0,
                    revoke=True
                ))
                active_operations[operation_id]['success'] += 1
                success_list.append(f"✅ {bot_name}")
                
                if (i + 1) % 3 == 0 or i == len(bots) - 1:
                    await update_progress(message, operation_id, total_bots, i, "بات ها", "در حال پاک کردن چت بات ها...")
                
                await asyncio.sleep(1)
            except Exception as e:
                active_operations[operation_id]['failed'] += 1
                failed_list.append(f"❌ {bot_name}: {str(e)}")
        
        await show_final_results(message, operation_id, total_bots, "بات ها", "عملیات پاک کردن چت بات ها به پایان رسید")
        
    except Exception as e:
        try:
            await message.edit(f"❌ **خطا در عملیات پاک کردن چت بات ها:** {str(e)}")
        except MessageIdInvalidError:
            await event.respond(f"❌ **خطا در عملیات پاک کردن چت بات ها:** {str(e)}")
    finally:
        if operation_id in active_operations:
            del active_operations[operation_id]

async def main():
    await client.start()
    print(f"ClearBot {VERSION} is running...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main()) 