import json
import os
from datetime import date, datetime
from typing import Optional

from app.data_provider.base import DataProvider


class CsvDataProvider(DataProvider):
    """Data provider that reads from local JSON/CSV files.

    This is the default provider for the demo version.
    All market data is loaded from sample_data/bond_market_data.json at init.
    """

    def __init__(self, data_dir=None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'sample_data')
        self.data_dir = os.path.abspath(data_dir)
        self._bond_data = {}
        self._stock_data = {}
        self._load_data()

    def _load_data(self):
        bond_file = os.path.join(self.data_dir, 'bond_market_data.json')
        if os.path.exists(bond_file):
            with open(bond_file, 'r', encoding='utf-8') as f:
                self._bond_data = json.load(f)

        stock_file = os.path.join(self.data_dir, 'stock_market_data.json')
        if os.path.exists(stock_file):
            with open(stock_file, 'r', encoding='utf-8') as f:
                self._stock_data = json.load(f)

    def _get_bond(self, bond_code: str) -> dict:
        return self._bond_data.get(bond_code, {})

    def _get_stock(self, stock_code: str) -> dict:
        return self._stock_data.get(stock_code, {})

    def get_bond_maturity(self, bond_code: str) -> Optional[date]:
        val = self._get_bond(bond_code).get('maturity_date')
        if val:
            return datetime.strptime(val, '%Y-%m-%d').date()
        return None

    def get_bond_duration(self, bond_code: str) -> Optional[float]:
        return self._get_bond(bond_code).get('duration')

    def get_bond_convexity(self, bond_code: str) -> Optional[float]:
        return self._get_bond(bond_code).get('convexity')

    def get_bond_ytm(self, bond_code: str) -> Optional[float]:
        return self._get_bond(bond_code).get('ytm')

    def get_bond_implied_rating(self, bond_code: str) -> Optional[str]:
        return self._get_bond(bond_code).get('implied_rating')

    def get_bond_industry(self, bond_code: str) -> Optional[str]:
        return self._get_bond(bond_code).get('industry')

    def get_bond_issuer(self, bond_code: str) -> Optional[str]:
        return self._get_bond(bond_code).get('issuer')

    def is_lgfv_bond(self, bond_code: str) -> bool:
        return self._get_bond(bond_code).get('is_lgfv', False)

    def get_bond_remaining_maturity(self, bond_code: str) -> Optional[float]:
        return self._get_bond(bond_code).get('remaining_maturity')

    def get_bond_bpv(self, bond_code: str) -> Optional[float]:
        return self._get_bond(bond_code).get('bpv')

    def get_bond_rating(self, bond_code: str) -> Optional[str]:
        return self._get_bond(bond_code).get('bond_rating')

    def get_bond_province(self, bond_code: str) -> Optional[str]:
        return self._get_bond(bond_code).get('province')

    def get_bond_type(self, bond_code: str) -> Optional[str]:
        return self._get_bond(bond_code).get('bond_type')

    def get_stock_beta(self, stock_code: str) -> Optional[float]:
        return self._get_stock(stock_code).get('beta')

    def get_stock_volatility(self, stock_code: str) -> Optional[float]:
        return self._get_stock(stock_code).get('volatility')

    def get_convertible_bond_premium(self, bond_code: str) -> Optional[float]:
        return self._get_bond(bond_code).get('pure_bond_premium')

    def get_conversion_premium(self, bond_code: str) -> Optional[float]:
        return self._get_bond(bond_code).get('conversion_premium')

    def is_available(self) -> bool:
        return True
