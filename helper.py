import asyncio
import json
import websockets
import math
from telegram import Bot

# --- CONFIGURATION (Keep your current keys here) ---
import os
from dotenv import load_dotenv

load_dotenv() # This pulls the data from your hidden .env file

# --- CONFIGURATION (Safe Version) ---
APP_ID = os.getenv('APP_ID')
DERIV_TOKEN = os.getenv('DERIV_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

bot = Bot(token=TELEGRAM_TOKEN)
last_price = 0  # Global variable to store the latest price

async def check_strategy(candles):
    global last_price
    curr = candles[-1]
    last_price = curr['close'] # Update the latest price
    
    # ... (Your existing RSI/BB strategy logic goes here) ...

async def handle_telegram_commands():
    """Checks for new messages like /price on Telegram every few seconds"""
    last_update_id = 0
    while True:
        try:
            updates = await bot.get_updates(offset=last_update_id + 1, timeout=10)
            for update in updates:
                last_update_id = update.update_id
                if update.message and update.message.text == "/price":
                    await bot.send_message(chat_id=CHAT_ID, text=f"📊 Current Volatility 100 Price: {last_price}")
        except Exception:
            pass
        await asyncio.sleep(2) # Don't overwhelm the API

async def main():
    url = f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}"
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"authorize": DERIV_TOKEN}))
        await ws.send(json.dumps({"ticks_history": "R_100", "count": 50, "end": "latest", "granularity": 60, "style": "candles", "subscribe": 1}))
        
        print("Bot is active. Try sending /price in Telegram!")
        await bot.send_message(chat_id=CHAT_ID, text="🤖 Trading Helper is ONLINE. Send /price to check the market.")
        
        # Run the market watcher and the telegram listener at the same time
        await asyncio.gather(
            market_loop(ws),
            handle_telegram_commands()
        )

async def market_loop(ws):
    while True:
        msg = json.loads(await ws.recv())
        if 'candles' in msg:
            await check_strategy(msg['candles'])
        elif 'ohlc' in msg:
            global last_price
            last_price = msg['ohlc']['close']

async def check_strategy(candles):
    global last_price
    # Need at least 2 candles to compare current vs previous
    if len(candles) < 2: return
    
    curr = candles[-1]
    prev = candles[-2]
    last_price = curr['close']
    
    # --- Pattern Logic ---
    pattern_name = None
    
    # 1. Bullish Engulfing
    if curr['close'] > prev['open'] and curr['open'] < prev['close'] and prev['close'] < prev['open']:
        pattern_name = "Bullish Engulfing 📈"
        
    # 2. Bearish Engulfing
    elif curr['close'] < prev['open'] and curr['open'] > prev['close'] and prev['close'] > prev['open']:
        pattern_name = "Bearish Engulfing 📉"
        
    # 3. Hammer (Bottom reversal)
    body = abs(curr['close'] - curr['open'])
    lower_wick = min(curr['open'], curr['close']) - curr['low']
    if lower_wick > (body * 2) and (curr['high'] - max(curr['open'], curr['close'])) < body:
        pattern_name = "Hammer 🔨"

    # --- RSI & BB Integration (Optional Confluence) ---
    # If a pattern is found, send the message
    if pattern_name:
        message = (
            f"🎯 **New Signal Detected!**\n"
            f"Pattern: {pattern_name}\n"
            f"Price: {curr['close']}\n"
            f"Index: Volatility 100"
        )
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
        print(f"Signal sent: {pattern_name}")
            

asyncio.run(main())
