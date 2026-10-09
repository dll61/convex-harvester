"""Mock Exchange Connector for Zero-Risk Local Simulations & Testing."""

from typing import Any, Dict, List, Tuple
from .base import BaseExchangeConnector


class MockExchangeConnector(BaseExchangeConnector):
    """Simulated exchange connector with programmable prices and orderbooks."""

    def __init__(self, initial_price: float = 100.0):
        self.current_price = initial_price
        self.bids: List[Dict[str, Any]] = [
            {"px": initial_price - 0.01, "sz": 1000.0, "n": 3},
            {"px": initial_price - 0.02, "sz": 1500.0, "n": 5},
        ]
        self.asks: List[Dict[str, Any]] = [
            {"px": initial_price + 0.01, "sz": 1000.0, "n": 3},
            {"px": initial_price + 0.02, "sz": 1500.0, "n": 4},
        ]
        self.closed_orders: List[Dict[str, Any]] = []

    def set_price(self, price: float) -> None:
        """Updates the simulated price."""
        self.current_price = price
        self.bids[0]["px"] = round(price - 0.01, 4)
        self.asks[0]["px"] = round(price + 0.01, 4)

    def set_orderbook(self, bids: List[Dict[str, Any]], asks: List[Dict[str, Any]]) -> None:
        """Sets custom orderbook levels."""
        self.bids = bids
        self.asks = asks

    def get_mid_price(self, symbol: str) -> float:
        return self.current_price

    def get_orderbook(self, symbol: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self.bids, self.asks

    def close_position(self, symbol: str, side: str, size: float, reduce_only: bool = True) -> Dict[str, Any]:
        order = {
            "symbol": symbol,
            "side": side,
            "size": size,
            "exit_price": self.current_price,
            "status": "FILLED",
        }
        self.closed_orders.append(order)
        return order
