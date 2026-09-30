import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

MIN_VOLUME = 300000
TRADE_AMOUNT = 0.4          # 50 cent'e yakın
RSI_BUY = 30
RSI_SELL = 70

is_scanning = False
open_positions = {}


def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


async def send_log(context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        await context.bot.send_message(chat_id=CHAT_ID, text=text)
    except Exception as e:
        print("Log hatası:", e)


async def get_usdt_pairs():
    markets = exchange.load_markets()
    pairs = [s for s in markets if s.endswith('/USDT') and markets[s]['active']]
    return pairs


async def scan_and_trade(context: ContextTypes.DEFAULT_TYPE):
    global is_scanning, open_positions

    if is_scanning:
        return
    is_scanning = True

    try:
        pairs = await get_usdt_pairs()
        total = len(pairs)
        await send_log(context, f"🔍 Tarama başladı → {total} USDT paritesi")

        scanned = 0
        for symbol in pairs:
            scanned += 1

            if scanned % 25 == 0 or scanned == total:
                await send_log(context, f"[SCAN] {scanned}/{total} tamamlandı...")

            try:
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=50)
                closes = [x[4] for x in ohlcv]
                volumes = [x[5] for x in ohlcv]
                price = closes[-1]
                volume_usdt = volumes[-1] * price

                if volume_usdt < MIN_VOLUME:
                    continue

                rsi = calculate_rsi(closes)

                # === ALIM ===
                if rsi < RSI_BUY and symbol not in open_positions:
                    try:
                        amount = TRADE_AMOUNT / price
                        order = exchange.create_market_buy_order(symbol, amount)
                        open_positions[symbol] = price
                        await send_log(context,
                            f"✅ GERÇEK ALIM YAPILDI\n"
                            f"Parite: {symbol}\n"
                            f"Fiyat: {price:.6f}\n"
                            f"RSI: {rsi:.1f}\n"
                            f"Miktar: {TRADE_AMOUNT}$")
                    except Exception as e:
                        await send_log(context, f"❌ Alım hatası ({symbol}): {str(e)}")

                # === SATIM ===
                elif rsi > RSI_SELL and symbol in open_positions:
                    try:
                        balance = exchange.fetch_balance()
                        coin = symbol.split('/')[0]
                        free_amount = balance['free'].get(coin, 0)

                        if free_amount > 0:
                            order = exchange.create_market_sell_order(symbol, free_amount)
                            entry = open_positions[symbol]
                            profit_pct = ((price - entry) / entry) * 100
                            del open_positions[symbol]
                            await send_log(context,
                                f"💰 GERÇEK SATIM YAPILDI\n"
                                f"Parite: {symbol}\n"
                                f"Giriş: {entry:.6f}\n"
                                f"Çıkış: {price:.6f}\n"
                                f"Kâr: %{profit_pct:.2f}")
                    except Exception as e:
                        await send_log(context, f"❌ Satım hatası ({symbol}): {str(e)}")

            except Exception:
                continue

            await asyncio.sleep(0.25)

        await send_log(context, f"✅ TARAMA TAMAMLANDI {total}/{total}")

    except Exception as e:
        await send_log(context, f"❌ Hata: {str(e)}")
    finally:
        is_scanning = False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Oto Trader Bot (GERÇEK İŞLEM) aktif!\n\n"
        "/scan → Tarama + işlem başlat\n"
        "/status → Açık pozisyonlar"
    )


async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tarama ve gerçek işlem başlatılıyor...")
    await scan_and_trade(context)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not open_positions:
        await update.message.reply_text("Açık pozisyon yok.")
        return
    text = "📊 Açık Pozisyonlar:\n"
    for s, p in open_positions.items():
        text += f"• {s} → {p:.6f}\n"
    await update.message.reply_text(text)


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")
    def log_message(self, format, *args):
        return


def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"Web server started on port {port}")
    server.serve_forever()


def main():
    threading.Thread(target=run_web_server, daemon=True).start()

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan_cmd))
    app.add_handler(CommandHandler("status", status))
    print("Bot çalışıyor (GERÇEK İŞLEM MODU)...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    main()
