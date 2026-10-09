"""Abstract Base Connector for Exchange Execution."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class BaseExchangeConnector(ABC):
    """Abstract interface decoupling the Harvester logic from specific exchanges."""

    @abstractmethod
    def get_mid_price(self, symbol: str) -> float:
        """Fetches the latest mid or mark price for the given symbol."""
        pass

    @abstractmethod
    def get_orderbook(self, symbol: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Fetches top bids and asks levels: (bids, asks)."""
        pass

    @abstractmethod
    def close_position(self, symbol: str, side: str, size: float, reduce_only: bool = True) -> Dict[str, Any]:
        """Executes position closure order (market or pegged limit)."""
        pass
