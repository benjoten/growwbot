import time
import threading
from datetime import datetime
import pyotp
from growwapi import GrowwAPI
from growwapi.groww.exceptions import GrowwAPIAuthenticationException, GrowwAPIException
from config import CONFIG

class GrowwClientManager:
    """
    Manages Groww API authentication lifecycle, session tokens, and account operations.
    Supports automatic TOTP code generation and token renewal.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.api_key = CONFIG.get("api_key", "")
        self.totp_secret = CONFIG.get("totp_secret", "")
        self.access_token = None
        self.client = None
        self.last_login_time = None
        self.last_totp_used = None
        self.last_error = None

    def get_current_totp(self) -> str:
        """Generates the current 6-digit TOTP code based on the base32 secret."""
        if not self.totp_secret:
            raise ValueError("TOTP secret is missing. Check your key.txt or .env file.")
        totp = pyotp.TOTP(self.totp_secret)
        return totp.now()

    def authenticate(self, force: bool = False) -> GrowwAPI:
        """
        Acquires or returns a valid GrowwAPI client instance.
        If force=True, forces generation of a new access token using TOTP.
        """
        with self._lock:
            # If we already have a client and not forced, return it
            if self.client and not force:
                return self.client

            if not self.api_key or not self.totp_secret:
                raise ValueError("Groww API Key or TOTP Secret not configured.")

            current_totp = self.get_current_totp()
            try:
                token = GrowwAPI.get_access_token(api_key=self.api_key, totp=current_totp)
                self.access_token = token
                self.client = GrowwAPI(token)
                self.last_login_time = datetime.now()
                self.last_totp_used = current_totp
                self.last_error = None
                return self.client
            except Exception as e:
                self.last_error = str(e)
                raise

    def _execute_with_retry(self, func):
        """Executes an API call, automatically re-authenticating if token expired."""
        try:
            client = self.authenticate(force=False)
            return func(client)
        except GrowwAPIAuthenticationException:
            # Token expired or invalidated, re-authenticate and retry once
            client = self.authenticate(force=True)
            return func(client)

    def get_profile(self) -> dict:
        """Fetches the user profile details."""
        return self._execute_with_retry(lambda c: c.get_user_profile())

    def get_funds(self) -> dict:
        """Fetches available funds and detailed margin breakdown."""
        return self._execute_with_retry(lambda c: c.get_available_margin_details())

    def get_holdings(self) -> list:
        """Fetches long-term stock holdings."""
        res = self._execute_with_retry(lambda c: c.get_holdings_for_user())
        if isinstance(res, dict) and "holdings" in res:
            return res["holdings"]
        return res if isinstance(res, list) else []

    def get_positions(self) -> list:
        """Fetches open / closed intraday and F&O positions."""
        res = self._execute_with_retry(lambda c: c.get_positions_for_user())
        if isinstance(res, dict) and "positions" in res:
            return res["positions"]
        return res if isinstance(res, list) else []

    def get_orders(self) -> list:
        """Fetches the day's order book."""
        res = self._execute_with_retry(lambda c: c.get_order_list())
        if isinstance(res, dict) and "order_list" in res:
            return res["order_list"]
        return res if isinstance(res, list) else []

    def get_dashboard_summary(self) -> dict:
        """
        Compiles high-level metrics for the trading dashboard:
        - Connection status
        - Profile
        - Funds summary
        - Holdings total investment calculation
        - Positions count
        - Orders count
        """
        try:
            profile = self.get_profile()
            funds = self.get_funds()
            holdings = self.get_holdings()
            positions = self.get_positions()
            orders = self.get_orders()

            total_invested = sum(
                (float(h.get("quantity", 0)) * float(h.get("average_price", 0)))
                for h in holdings
            )

            return {
                "success": True,
                "connected": True,
                "authenticated_at": self.last_login_time.strftime("%Y-%m-%d %H:%M:%S") if self.last_login_time else None,
                "profile": profile,
                "funds": funds,
                "holdings": holdings,
                "holdings_count": len(holdings),
                "total_invested": round(total_invested, 2),
                "positions": positions,
                "positions_count": len(positions),
                "orders": orders,
                "orders_count": len(orders),
            }
        except Exception as e:
            return {
                "success": False,
                "connected": False,
                "error": str(e),
                "authenticated_at": self.last_login_time.strftime("%Y-%m-%d %H:%M:%S") if self.last_login_time else None,
            }

groww_manager = GrowwClientManager()

