"""
DayTrader Autonomous System Scheduler
Schedules 9:00 AM IST Indian Market Scan and 24x7 Crypto Perpetuals Scan.
Runs in a background thread inside Flask or standalone.
"""
import time
import threading
import logging
from datetime import datetime
import pytz
from typing import Optional

from trader.bidirectional_engine import BiDirectionalTradingSystem, load_system_config

logger = logging.getLogger("DayTraderScheduler")
IST = pytz.timezone("Asia/Kolkata")

class SystemScheduler:
    def __init__(self, engine: Optional[BiDirectionalTradingSystem] = None):
        self.engine = engine or BiDirectionalTradingSystem()
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.last_equity_scan_date: Optional[str] = None
        self.last_crypto_scan_time: float = 0.0
        
    def start(self) -> None:
        """Starts background daemon scheduler."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("DayTrader Autonomous Scheduler background thread started.")

    def stop(self) -> None:
        """Stops background daemon scheduler."""
        self.running = False
        logger.info("DayTrader Autonomous Scheduler stopped.")

    def _run_loop(self) -> None:
        # Check if we should do initial scan on startup
        if not self.engine.latest_tickets:
            try:
                logger.info("Running initial startup scan...")
                self.engine.scan_all_universe()
            except Exception as e:
                logger.error(f"Startup scan failed: {e}")

        while self.running:
            try:
                now_ist = datetime.now(IST)
                today_str = now_ist.strftime("%Y-%m-%d")
                weekday = now_ist.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
                current_time_sec = time.time()
                
                # 1. Equities / Indices Check (9:00 AM IST on Weekdays)
                is_weekday = (weekday < 5)
                is_after_9am = (now_ist.hour > 9) or (now_ist.hour == 9 and now_ist.minute >= 0)
                
                if is_weekday and is_after_9am and (self.last_equity_scan_date != today_str):
                    logger.info(f"Triggering 9:00 AM IST Scheduled Scan for Indian Markets ({today_str})...")
                    self.engine.scan_all_universe()
                    self.last_equity_scan_date = today_str

                # 2. Crypto Perpetuals 24x7 Check (Every 15 minutes)
                crypto_interval_sec = 15 * 60
                if (current_time_sec - self.last_crypto_scan_time) >= crypto_interval_sec:
                    logger.info("Periodic 24x7 Crypto & Market scan refresh...")
                    self.engine.scan_all_universe()
                    self.last_crypto_scan_time = current_time_sec

            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                
            time.sleep(30)

