"""
Extends ~/tradingview/src/alerts/alert_system.py with a Telegram notification handler.

Usage:
    from alerts.advisor_alerts import AdvisorAlertSystem
    alert_sys = AdvisorAlertSystem()
    alert_sys.enable_telegram()
"""

import asyncio
import logging
import sys
import os
from typing import Optional

# Make the existing tradingview alert system importable
_TV_PATH = os.path.expanduser("~/tradingview/src")
if _TV_PATH not in sys.path:
    sys.path.insert(0, _TV_PATH)

from alerts.alert_system import AlertSystem, Alert, AlertPriority  # noqa: E402

logger = logging.getLogger(__name__)


def _telegram_handler(alert: Alert) -> None:
    """
    Synchronous handler that bridges into the async Telegram send.
    Falls back gracefully if Telegram is not configured.
    """
    try:
        from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
        from telegram import Bot

        priority_labels = {
            AlertPriority.LOW: "ℹ️",
            AlertPriority.MEDIUM: "⚠️",
            AlertPriority.HIGH: "🚨",
            AlertPriority.CRITICAL: "🔥",
        }
        emoji = priority_labels.get(alert.priority, "📢")
        text = f"{emoji} <b>[Alert] {alert.title}</b>\n{alert.message}"

        bot = Bot(token=TELEGRAM_BOT_TOKEN)

        # Run in event loop if one exists, otherwise create one
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="HTML")
                )
            else:
                loop.run_until_complete(
                    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="HTML")
                )
        except RuntimeError:
            asyncio.run(
                bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="HTML")
            )

    except Exception as e:
        logger.error(f"Telegram alert handler failed: {e}")


class AdvisorAlertSystem(AlertSystem):
    """
    AlertSystem extended with a Telegram notification handler.
    """

    def __init__(self, storage_path: str = "advisor_alerts.json"):
        super().__init__(storage_path=storage_path)
        logger.info("AdvisorAlertSystem initialized")

    def enable_telegram(self) -> None:
        """Add Telegram as a notification handler."""
        self.add_notification_handler(_telegram_handler)
        logger.info("Telegram notifications enabled for AdvisorAlertSystem")
