from abc import ABC, abstractmethod
from datetime import date
from typing import Optional


class DataProvider(ABC):
    """Abstract base class for market data providers.

    The demo version uses CsvDataProvider (local CSV/JSON files).
    Production can implement WindDataProvider (requires Wind terminal license).
    """

    @abstractmethod
    def get_bond_maturity(self, bond_code: str) -> Optional[date]:
        """Get bond maturity date."""

    @abstractmethod
    def get_bond_duration(self, bond_code: str) -> Optional[float]:
        """Get bond modified duration."""

    @abstractmethod
    def get_bond_convexity(self, bond_code: str) -> Optional[float]:
        """Get bond convexity."""

    @abstractmethod
    def get_bond_ytm(self, bond_code: str) -> Optional[float]:
        """Get bond yield to maturity."""

    @abstractmethod
    def get_bond_implied_rating(self, bond_code: str) -> Optional[str]:
        """Get bond implied credit rating (e.g., 'AAA', 'AA+', 'AA')."""

    @abstractmethod
    def get_bond_industry(self, bond_code: str) -> Optional[str]:
        """Get bond issuer industry classification."""

    @abstractmethod
    def get_bond_issuer(self, bond_code: str) -> Optional[str]:
        """Get bond issuer name."""

    @abstractmethod
    def is_lgfv_bond(self, bond_code: str) -> bool:
        """Check if bond is an LGFV (Local Government Financing Vehicle) bond."""

    @abstractmethod
    def get_bond_remaining_maturity(self, bond_code: str) -> Optional[float]:
        """Get remaining years to maturity."""

    @abstractmethod
    def get_bond_bpv(self, bond_code: str) -> Optional[float]:
        """Get basis point value."""

    @abstractmethod
    def get_bond_rating(self, bond_code: str) -> Optional[str]:
        """Get bond credit rating (issuer rating)."""

    @abstractmethod
    def get_bond_province(self, bond_code: str) -> Optional[str]:
        """Get bond issuer province."""

    @abstractmethod
    def get_bond_type(self, bond_code: str) -> Optional[str]:
        """Get bond type classification (e.g., windl2type)."""

    @abstractmethod
    def get_stock_beta(self, stock_code: str) -> Optional[float]:
        """Get stock beta (100-week)."""

    @abstractmethod
    def get_stock_volatility(self, stock_code: str) -> Optional[float]:
        """Get stock annualized volatility (100-week)."""

    @abstractmethod
    def get_convertible_bond_premium(self, bond_code: str) -> Optional[float]:
        """Get pure bond premium ratio for convertible bonds."""

    @abstractmethod
    def get_conversion_premium(self, bond_code: str) -> Optional[float]:
        """Get conversion premium ratio for convertible bonds."""

    def is_available(self) -> bool:
        """Check if the data provider is connected and available."""
        return True
