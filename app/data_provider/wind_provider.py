"""Wind API data provider.

IMPORTANT: This provider requires a Wind Financial Terminal license.
Wind (https://www.wind.com.cn/) is a professional financial data terminal
widely used in Chinese financial institutions.

To use this provider:
1. Install WindPy: pip install WindPy (or use the installer from Wind terminal)
2. Ensure Wind terminal is running and logged in
3. Set DATA_PROVIDER=wind in your .env file
"""

from datetime import date
from typing import Optional

from app.data_provider.base import DataProvider


class WindDataProvider(DataProvider):
    """Data provider that connects to Wind Financial Terminal API."""

    def __init__(self):
        try:
            from WindPy import w
            self.w = w
            w.start()
            if not w.isconnected():
                raise ConnectionError('Wind terminal is not connected. Please start and log in to Wind.')
            self._connected = True
        except ImportError:
            raise ImportError(
                'WindPy is not installed. '
                'Please install it from your Wind terminal or set DATA_PROVIDER=csv.'
            )

    def _wss(self, code: str, field: str, params: str = ''):
        result = self.w.wss(code, field, params)
        if result.ErrorCode != 0:
            return None
        if result.Data and result.Data[0]:
            return result.Data[0][0]
        return None

    def get_bond_maturity(self, bond_code: str) -> Optional[date]:
        val = self._wss(bond_code, 'maturitdate')
        if val and hasattr(val, 'date'):
            return val.date()
        return val

    def get_bond_duration(self, bond_code: str) -> Optional[float]:
        return self._wss(bond_code, 'modidura_cnbd')

    def get_bond_convexity(self, bond_code: str) -> Optional[float]:
        return self._wss(bond_code, 'cnvxty_cnbd')

    def get_bond_ytm(self, bond_code: str) -> Optional[float]:
        return self._wss(bond_code, 'yield_cnbd')

    def get_bond_implied_rating(self, bond_code: str) -> Optional[str]:
        return self._wss(bond_code, 'rate_latestMIR_cnbd')

    def get_bond_industry(self, bond_code: str) -> Optional[str]:
        return self._wss(bond_code, 'industry_sw_2021')

    def get_bond_issuer(self, bond_code: str) -> Optional[str]:
        return self._wss(bond_code, 'issuerupdated')

    def is_lgfv_bond(self, bond_code: str) -> bool:
        val = self._wss(bond_code, 'municipalbondYY')
        return val == 'Y' if val else False

    def get_bond_remaining_maturity(self, bond_code: str) -> Optional[float]:
        return self._wss(bond_code, 'ptmyear')

    def get_bond_bpv(self, bond_code: str) -> Optional[float]:
        return self._wss(bond_code, 'vobp_cnbd')

    def get_bond_rating(self, bond_code: str) -> Optional[str]:
        return self._wss(bond_code, 'lowestissurercreditrating')

    def get_bond_province(self, bond_code: str) -> Optional[str]:
        return self._wss(bond_code, 'abs_province')

    def get_bond_type(self, bond_code: str) -> Optional[str]:
        return self._wss(bond_code, 'windl2type')

    def get_stock_beta(self, stock_code: str) -> Optional[float]:
        return self._wss(stock_code, 'beta_100w')

    def get_stock_volatility(self, stock_code: str) -> Optional[float]:
        return self._wss(stock_code, 'annualstdevr_100w')

    def get_convertible_bond_premium(self, bond_code: str) -> Optional[float]:
        return self._wss(bond_code, 'strbpremiumratio')

    def get_conversion_premium(self, bond_code: str) -> Optional[float]:
        return self._wss(bond_code, 'convpremiumratio')

    def is_available(self) -> bool:
        return self._connected and self.w.isconnected()
