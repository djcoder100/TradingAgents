# competition/mt5_fill_poller.py
"""Background thread for polling MT5 order fills.

MT5 has no webhook capability, so we poll order history periodically to detect fills.
Each registered order is checked every 1 second; when status changes (PENDING → FILLED),
the callback is invoked.
"""

import logging
import threading
import time
from typing import Callable, Dict, Optional, Any

from competition.mt5_config import FILL_POLL_INTERVAL_S

logger = logging.getLogger(__name__)


class MT5FillPoller:
    """Background thread that polls MT5 for order fills.

    Usage:
        poller = MT5FillPoller(mt5_module)
        poller.register_order(order_id, callback=on_fill)
        poller.start()
        # ... when done
        poller.stop()
    """

    def __init__(self, mt5_module):
        self._mt5 = mt5_module
        self._orders: Dict[str, Dict[str, Any]] = {}  # order_id → {status, callback, registered_at, ...}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_statuses: Dict[str, str] = {}  # order_id → last known status (for change detection)

    def register_order(
        self,
        order_id: str,
        callback: Callable[[str, Dict[str, Any]], None],
        order_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register an order for fill polling.

        Args:
            order_id: Unique order ID from broker
            callback: Function to call on fill: callback(order_id, fill_details)
            order_data: Optional metadata to attach (ticker, action, etc.)
        """
        with self._lock:
            self._orders[order_id] = {
                "callback": callback,
                "registered_at": time.time(),
                "data": order_data or {},
            }
            logger.debug("Registered order %s for fill polling", order_id)

    def unregister_order(self, order_id: str) -> None:
        """Stop polling this order (e.g., after fill or cancellation)."""
        with self._lock:
            if order_id in self._orders:
                del self._orders[order_id]
                logger.debug("Unregistered order %s from fill polling", order_id)

    def start(self) -> None:
        """Start the background polling thread."""
        if self._running:
            logger.warning("Poller already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("MT5 fill poller started (interval: %.1f s)", FILL_POLL_INTERVAL_S)

    def stop(self) -> None:
        """Stop the polling thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            logger.info("MT5 fill poller stopped")

    def _poll_loop(self) -> None:
        """Main polling loop (runs in background thread)."""
        try:
            while self._running:
                self._check_orders()
                time.sleep(FILL_POLL_INTERVAL_S)
        except Exception as e:
            logger.error("Fill poller crashed: %s", e)

    def _check_orders(self) -> None:
        """Check status of all registered orders."""
        with self._lock:
            order_ids = list(self._orders.keys())

        for order_id in order_ids:
            try:
                # Query order status from MT5
                order_info = self._mt5.order_get(ticket=int(order_id))

                if order_info is None:
                    logger.debug("Order %s not found in MT5 (may be filled/closed)", order_id)
                    # Assume it was filled or cancelled; unregister it
                    self.unregister_order(order_id)
                    continue

                status = order_info.type_status  # TRADE_ORDER_STATE_PLACED, FILLED, EXPIRED, etc.
                last_status = self._last_statuses.get(order_id)

                # Check if status changed
                if status != last_status:
                    logger.debug("Order %s status changed: %s → %s", order_id, last_status, status)
                    self._last_statuses[order_id] = status

                    # If filled or reached a terminal state, invoke callback
                    if self._is_terminal_status(status):
                        with self._lock:
                            if order_id in self._orders:
                                callback = self._orders[order_id]["callback"]
                                order_data = self._orders[order_id]["data"]
                                callback(order_id, self._order_info_to_dict(order_info, order_data))
                        self.unregister_order(order_id)

            except Exception as e:
                logger.error("Error checking order %s: %s", order_id, e)

    @staticmethod
    def _is_terminal_status(status: str) -> bool:
        """Check if an order has reached a terminal state."""
        # Terminal states: FILLED, EXPIRED, REJECTED, CANCELLED, etc.
        terminal = (
            "FILLED" in status or
            "EXPIRED" in status or
            "REJECTED" in status or
            "CANCELLED" in status or
            "CLOSED" in status
        )
        return terminal

    @staticmethod
    def _order_info_to_dict(order_info, extra_data: Dict) -> Dict[str, Any]:
        """Convert MT5 order_info object to a dict."""
        return {
            "order_id": order_info.ticket,
            "symbol": order_info.symbol,
            "type": order_info.type,
            "type_status": order_info.type_status,
            "state": order_info.state,
            "time_setup": order_info.time_setup,
            "price_open": order_info.price_open,
            "sl": order_info.sl,
            "tp": order_info.tp,
            "volume_initial": order_info.volume_initial,
            "volume_current": order_info.volume_current,
            "time_fill": order_info.time_fill,
            "time_expiration": order_info.time_expiration,
            "comment": order_info.comment,
            **extra_data,
        }
