"""
AI-Powered Indian Stock Market Screener Scheduler & Alerts Dispatcher
- Runs background daemon monitoring IST time (Asia/Kolkata)
- Executes daily NSE/BSE scan automatically at ~9:00 AM IST on trading days
- Dispatches top shortlisted setups via:
  1. Local Dashboard Notifications & State JSON
  2. Telegram Bot Alerts (HTML formatted with Entry, Targets, SL & R:R)
  3. Email Alerts (SMTP)
"""

import os
import json
import time
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date
from pathlib import Path
import pytz
import requests
from dotenv import load_dotenv

from .ai_screener_engine import ai_screener, REPORT_FILE, ALERTS_CONFIG_FILE, IST

BASE_DIR = Path(__file__).resolve().parent.parent

class ScreenerScheduler:
    def __init__(self):
        self._lock = threading.Lock()
        self.last_scan_date = None
        self._is_scanning = False
        self._init_alerts_config()
        self.start_daemon()

    def _init_alerts_config(self):
        if not ALERTS_CONFIG_FILE.exists():
            default_config = {
                "telegram_enabled": False,
                "telegram_bot_token": "",
                "telegram_chat_id": "",
                "email_enabled": False,
                "email_to": "",
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
                "smtp_user": "",
                "smtp_password": "",
                "auto_scan_at_9am": True
            }
            try:
                with open(ALERTS_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=2)
            except Exception:
                pass

    def get_alerts_config(self) -> dict:
        load_dotenv(BASE_DIR / ".env", override=True)
        config = {
            "telegram_enabled": False,
            "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
            "email_enabled": False,
            "email_to": os.getenv("ALERT_EMAIL_TO", ""),
            "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
            "smtp_port": int(os.getenv("SMTP_PORT", 587)),
            "smtp_user": os.getenv("SMTP_USER", ""),
            "smtp_password": os.getenv("SMTP_PASSWORD", ""),
            "auto_scan_at_9am": True
        }
        if ALERTS_CONFIG_FILE.exists():
            try:
                with open(ALERTS_CONFIG_FILE, "r", encoding="utf-8") as f:
                    file_cfg = json.load(f)
                    config.update(file_cfg)
            except Exception:
                pass

        if config.get("telegram_bot_token") and config.get("telegram_chat_id"):
            config["telegram_enabled"] = True
        if config.get("smtp_user") and config.get("email_to"):
            config["email_enabled"] = True

        return config

    def save_alerts_config(self, new_cfg: dict):
        current = self.get_alerts_config()
        current.update(new_cfg)
        try:
            with open(ALERTS_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2)
            return {"success": True, "config": current}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def start_daemon(self):
        t = threading.Thread(target=self._scheduler_loop, daemon=True, name="AIEngine9AMDaemon")
        t.start()
        print("[ScreenerScheduler] Background 9:00 AM IST monitoring daemon active.")

    def _scheduler_loop(self):
        while True:
            try:
                now_ist = datetime.now(IST)
                today_str = now_ist.strftime("%Y-%m-%d")

                # Check if it is ~9:00 AM IST on a weekday (between 9:00 and 9:05 AM IST)
                is_weekday = now_ist.weekday() < 5 # Mon-Fri
                is_9am_window = (now_ist.hour == 9 and 0 <= now_ist.minute <= 5)

                if is_weekday and is_9am_window and self.last_scan_date != today_str and not self._is_scanning:
                    cfg = self.get_alerts_config()
                    if cfg.get("auto_scan_at_9am", True):
                        print(f"[ScreenerScheduler] ⏰ 9:00 AM IST reached on {today_str}! Triggering automatic market scan...")
                        self.run_scan_and_alert()
                        self.last_scan_date = today_str

                time.sleep(30)
            except Exception as e:
                print(f"[ScreenerScheduler Loop Error] {e}")
                time.sleep(60)

    def run_scan_and_alert(self) -> dict:
        """Executes the scan and dispatches alerts."""
        with self._lock:
            self._is_scanning = True
            try:
                report = ai_screener.run_market_scan()
                self._dispatch_alerts(report)
                return report
            finally:
                self._is_scanning = False

    def _dispatch_alerts(self, report: dict):
        cfg = self.get_alerts_config()
        top_stocks = report.get("top_opportunities", [])[:5]
        if not top_stocks:
            return

        date_str = datetime.now(IST).strftime("%d %b %Y")

        # 1. Format Telegram Message
        msg_lines = [
            f"🚀 <b>AI INDIAN STOCK SCREENER - 9:00 AM IST REPORT</b>",
            f"📅 <i>{date_str} | Session Preparation</i>\n",
            f"📊 <b>Market Sentiment:</b> {report.get('summary', {}).get('market_sentiment', 'BULLISH')}",
            f"🔍 <b>Top High-Probability BUY Setups:</b>\n"
        ]

        for idx, s in enumerate(top_stocks, 1):
            msg_lines.append(
                f"<b>{idx}. {s['name']} ({s['symbol']})</b> - <code>{s['recommendation']} ({s['confidence_score']}%)</code>\n"
                f"  • CMP: ₹{s['cmp']:,.2f} | {s['trade_type']}\n"
                f"  • 📌 <b>Entry:</b> ₹{s['entry_price']:,.2f} ({s['entry_range']})\n"
                f"  • 🎯 <b>Target 1:</b> ₹{s['target_1']:,.2f} (+{s['target_1_gain_pct']}%)\n"
                f"  • 🚀 <b>Target 2:</b> ₹{s['target_2']:,.2f} (+{s['target_2_gain_pct']}%)\n"
                f"  • 🛑 <b>Stop-Loss:</b> ₹{s['stop_loss']:,.2f} (-{s['stop_loss_pct']}%)\n"
                f"  • ⚖️ <b>R:R:</b> {s['risk_reward']} | {s['pattern']}\n"
            )

        msg_lines.append(f"⚠️ <i>Strict risk management applies. Place bracket orders with SL.</i>")
        telegram_text = "\n".join(msg_lines)

        # Send Telegram if configured
        if cfg.get("telegram_enabled") and cfg.get("telegram_bot_token") and cfg.get("telegram_chat_id"):
            self._send_telegram(cfg["telegram_bot_token"], cfg["telegram_chat_id"], telegram_text)

        # Send Email if configured
        if cfg.get("email_enabled") and cfg.get("smtp_user") and cfg.get("email_to"):
            self._send_email(cfg, f"AI Stock Screener: Top Setups for {date_str}", telegram_text)

    def _send_telegram(self, bot_token: str, chat_id: str, html_text: str) -> tuple:
        """
        Sends HTML formatted alert to Telegram chat.
        Returns (success: bool, message: str).
        """
        if not bot_token or not chat_id:
            return False, "Bot Token aur Chat ID dono required hain."
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": html_text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            r = requests.post(url, json=payload, timeout=8)
            res = r.json()
            if r.status_code == 200 and res.get("ok"):
                print("[ScreenerAlerts] Telegram alert delivered successfully.")
                return True, "✅ Telegram test alert delivered successfully! Telegram app me check karein."
            else:
                desc = res.get("description", r.text)
                print(f"[ScreenerAlerts] Telegram error: {desc}")
                if "can't send messages to the bot" in desc:
                    return False, f"⚠️ Telegram Error: Aapne Chat ID me bot ka apna username daala hai (@{chat_id.replace('@','')}). Bot khud ko message nahi bhej sakta. Kripya pehle Telegram app me @{chat_id.replace('@','')} ko '/start' bhejein, fir 'Auto-Detect Chat ID' par click karein."
                elif "chat not found" in desc:
                    return False, f"⚠️ Telegram Error: Chat not found. Pehle Telegram app me bot ko '/start' message bhejein."
                return False, f"Telegram API Error: {desc}"
        except Exception as e:
            print(f"[ScreenerAlerts] Telegram exception: {e}")
            return False, f"Telegram Connection Error: {str(e)}"

    def detect_telegram_chat_id(self, bot_token: str) -> tuple:
        """
        Fetches recent updates to automatically find the user's numeric chat ID
        after they send /start or any text to the bot.
        """
        try:
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            r = requests.get(url, timeout=6)
            res = r.json()
            if not res.get("ok"):
                return None, res.get("description", "Failed to contact Telegram API")
            updates = res.get("result", [])
            if not updates:
                return None, "Bot par koi naya message nahi mila. Pehle Telegram app me bot ko '/start' ya koi message bhejein, fir yahan Detect par click karein."
            
            for upd in reversed(updates):
                msg = upd.get("message") or upd.get("channel_post") or upd.get("my_chat_member", {}).get("chat")
                if msg and "chat" in msg:
                    chat_id = str(msg["chat"]["id"])
                    name = msg["chat"].get("first_name", msg["chat"].get("title", "User"))
                    return chat_id, f"Chat ID detected: {chat_id} ({name})"
                elif msg and "id" in msg:
                    chat_id = str(msg["id"])
                    return chat_id, f"Chat ID detected: {chat_id}"
            return None, "Chat ID recent updates me detect nahi ho paya."
        except Exception as e:
            return None, str(e)

    def _send_email(self, cfg: dict, subject: str, body_text: str) -> bool:
        try:
            msg = MIMEMultipart()
            msg["From"] = cfg["smtp_user"]
            msg["To"] = cfg["email_to"]
            msg["Subject"] = subject
            # Replace HTML tags for plain text email
            plain_text = body_text.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "").replace("<code>", "").replace("</code>", "")
            msg.attach(MIMEText(plain_text, "plain"))

            server = smtplib.SMTP(cfg.get("smtp_host", "smtp.gmail.com"), int(cfg.get("smtp_port", 587)), timeout=10)
            server.starttls()
            server.login(cfg["smtp_user"], cfg["smtp_password"])
            server.send_message(msg)
            server.quit()
            print("[ScreenerAlerts] Email alert sent successfully.")
            return True
        except Exception as e:
            print(f"[ScreenerAlerts] Email sending error: {e}")
            return False

screener_scheduler = ScreenerScheduler()

