import asyncio
import json
import websockets
import math
import os
from telegram import Bot

# --- CONFIGURATION (Keep your current keys here) ---
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
APP_ID = os.getenv('APP_ID')
DERIV_TOKEN = os.getenv('DERIV_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# The indices you want to track
SYMBOLS = ["R_100", "R_75", "R_50", "R_25"]

bot = Bot(token=TELEGRAM_TOKEN)
# Store latest prices in a dictionary for /price command
last_prices = {symbol: 0 for symbol in SYMBOLS}

async def check_strategy(candles, symbol_name):
    """Analyzes patterns and sends signals with the index name"""
    if len(candles) < 2: return
    
    curr = candles[-1]
    prev = candles[-2]
    
    # Update global price tracker for this specific symbol
    last_prices[symbol_name] = curr['close']
    
    pattern_name = None
    
    # 1. Bullish Engulfing
    if curr['close'] > prev['open'] and curr['open'] < prev['close'] and prev['close'] < prev['open']:
        pattern_name = "Bullish Engulfing 📈"
    # 2. Bearish Engulfing
    elif curr['close'] < prev['open'] and curr['open'] > prev['close'] and prev['close'] > prev['open']:
        pattern_name = "Bearish Engulfing 📉"
    # 3. Hammer
    body = abs(curr['close'] - curr['open'])
    lower_wick = min(curr['open'], curr['close']) - curr['low']
    if body > 0 and lower_wick > (body * 2) and (curr['high'] - max(curr['open'], curr['close'])) < body:
        pattern_name = "Hammer 🔨"

    if pattern_name:
        index_display = symbol_name.replace("R_", "Volatility ")
        message = (
            f"🎯 **New Signal Detected!**\n"
            f"Index: **{index_display}**\n"
            f"Pattern: {pattern_name}\n"
            f"Price: {curr['close']}"
        )
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
        print(f"Signal sent for {index_display}: {pattern_name}")

async def handle_telegram_commands():
    """Checks for new messages like /price on Telegram every few seconds"""
    last_update_id = 0
    while True:
        try:
            updates = await bot.get_updates(offset=last_update_id + 1, timeout=10)
            for update in updates:
                last_update_id = update.update_id
                if update.message and update.message.text == "/price":
                    price_text = "\n".join([f"📊 {s.replace('R_', 'V')}: {last_prices[s]}" for s in SYMBOLS])
                    await bot.send_message(chat_id=CHAT_ID, text=f"**Current Prices:**\n{price_text}", parse_mode='Markdown')
        except Exception:
            pass
        await asyncio.sleep(2)

async def market_loop(ws):
    while True:
        try:
            raw_msg = await ws.recv()
            msg = json.loads(raw_msg)
            
            # 1. Handle Initial History (Full Candles)
            if 'candles' in msg:
                symbol = msg.get('echo_req', {}).get('ticks_history')
                if symbol and msg['candles']:
                    # Update with the latest candle's close price
                    last_prices[symbol] = msg['candles'][-1]['close']
                    await check_strategy(msg['candles'], symbol)
            
            # 2. Handle Live Updates (The FIX for the "Same Price" Bug)
            elif 'ohlc' in msg:
                ohlc_data = msg['ohlc']
                symbol = ohlc_data.get('symbol')
                if symbol:
                    # Capture the live closing price as it changes
                    current_close = ohlc_data['close']
                    last_prices[symbol] = current_close
                    
                    # Convert single OHLC update to a list so check_strategy works
                    await check_strategy([ohlc_data], symbol)
                    
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed. Reconnecting...")
            break
        except Exception as e:
            print(f"Error in market loop: {e}")

async def main():
    url = f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}"
    
    while True:
        try:
            print(f"🔄 Connecting to monitor: {', '.join(SYMBOLS)}")
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({"authorize": DERIV_TOKEN}))
                
                # Subscribe to all indices
                for symbol in SYMBOLS:
                    await ws.send(json.dumps({
                        "ticks_history": symbol,
                        "count": 50,
                        "end": "latest",
                        "granularity": 60,
                        "style": "candles",
                        "subscribe": 1
                    }))
                
                print("✅ All indices subscribed. Monitoring live...")
                await bot.send_message(chat_id=CHAT_ID, text="🤖 Multi-Index Bot is ONLINE.")
                
                await asyncio.gather(
                    market_loop(ws),
                    handle_telegram_commands()
                )
        except Exception as e:
            print(f"⚠️ Connection error: {e}. Retrying in 10s...")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())