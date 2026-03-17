"""Money market fund calculation engine.

Computes basic info metrics (NAV, portfolio remaining days, 7-day yield,
14-day maturing asset scale) and 4 warning indicators for money market funds.

Wind API calls for bond maturity dates are replaced by DataProvider. When the
provider is unavailable, the calculator falls back to the end_date field stored
in the database at import time.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


class MoneyMarketCalculator:
    """Money market fund indicator calculator."""

    def __init__(self, data_provider=None):
        self.data_provider = data_provider

    def _get_maturity_date(self, code):
        """Get bond maturity date via DataProvider, return None if unavailable."""
        if self.data_provider and self.data_provider.is_available():
            return self.data_provider.get_bond_maturity(code)
        return None

    def _enrich_maturity_dates(self, df_merged, df_spd_bd, query_date):
        """Enrich merged DataFrame with maturity dates from DataProvider.

        For SPT_BD assets, tries DataProvider first, falls back to DB end_date.
        """
        if not df_spd_bd.empty and self.data_provider and self.data_provider.is_available():
            try:
                codes = df_spd_bd['security_full_code'].dropna().unique().tolist()
                maturity_map = {}
                for code in codes:
                    mat = self._get_maturity_date(code)
                    if mat:
                        maturity_map[code] = mat

                if maturity_map:
                    wind_df = pd.DataFrame(list(maturity_map.items()),
                                           columns=['security_full_code', 'maturity_date'])
                    df_merged = df_merged.merge(wind_df, on='security_full_code', how='left')
                    df_merged['证券到期日期'] = df_merged['maturity_date'].where(
                        df_merged['maturity_date'].notna(), df_merged['end_date'])
                    df_merged = df_merged.drop(columns=['maturity_date'], errors='ignore')
                else:
                    df_merged['证券到期日期'] = df_merged['end_date']
            except Exception as e:
                logger.error(f'Failed to get maturity dates: {e}')
                df_merged['证券到期日期'] = df_merged['end_date']
        else:
            df_merged['证券到期日期'] = df_merged['end_date']

        return df_merged

    @staticmethod
    def _filter_14day_maturing(df_merged):
        """Filter assets maturing within 14 days (inclusive, excluding already matured)."""
        df_merged['交易日期'] = pd.to_datetime(df_merged['position_date'])
        df_merged['证券到期日期'] = pd.to_datetime(df_merged['证券到期日期'])
        days_diff = (df_merged['证券到期日期'] - df_merged['交易日期']).dt.days
        return df_merged[(days_diff >= 0) & (days_diff <= 14)]

    def calculate_basic_info(self, df, query_date):
        """Calculate basic info metrics for money market fund.

        Args:
            df: DataFrame with money_market_fund_positions data
            query_date: Date to query

        Returns:
            dict with keys: fund_name, query_date, net_asset_billion,
            portfolio_days, yield_7d, asset_14days_billion
        """
        try:
            df_date = df[df['position_date'] == query_date].copy()
            if df_date.empty:
                logger.warning(f'No data for date {query_date}')
                return None

            # Deduplicate to avoid inflated ratios
            df_date = df_date.drop_duplicates(subset=[
                'fund_name', 'position_date', 'security_full_code',
                'market_value', 'accrued_interest', 'end_date',
            ])

            df_date['净值占比'] = (df_date['market_value'] + df_date['accrued_interest']) / df_date['fund_nav']
            df_date['证券市值'] = df_date['market_value'] + df_date['accrued_interest']

            first = df_date.iloc[0]
            fund_name = first['fund_name']
            net_asset = first['fund_nav'] / 1e8
            portfolio_days = first['portfolio_maturity']
            yield_7d = f"{first['yield_7d'] * 100:.2f}%"

            # 14-day maturing assets
            df_spd_bd = df_date[df_date['asset_type'] == 'SPT_BD'].copy()
            df_others = df_date[df_date['asset_type'].isin(['SPT_NGD', 'SPT_REPO'])].copy()
            df_merged = pd.concat([df_spd_bd, df_others], ignore_index=True)

            df_merged = self._enrich_maturity_dates(df_merged, df_spd_bd, query_date)
            filtered = self._filter_14day_maturing(df_merged)
            asset_14days = filtered['证券市值'].sum() / 1e8

            return {
                'fund_name': fund_name,
                'query_date': query_date.strftime('%Y-%m-%d'),
                'net_asset_billion': round(net_asset, 2),
                'portfolio_days': portfolio_days,
                'yield_7d': yield_7d,
                'asset_14days_billion': round(asset_14days, 2),
            }

        except Exception as e:
            logger.error(f'Failed to calculate basic info: {e}')
            return None

    def calculate_warning_indicators(self, df, query_date):
        """Calculate 4 warning indicators for money market fund.

        Indicators:
            1. 14-day maturing asset ratio (nav-weighted)
            2. Valuation volatility assets (SPT_BD nav ratio sum)
            3. Shadow price deviation
            4. Leverage ratio

        Args:
            df: DataFrame with money_market_fund_positions data
            query_date: Date to query

        Returns:
            dict with indicator values
        """
        try:
            df_date = df[df['position_date'] == query_date].copy()
            if df_date.empty:
                logger.warning(f'No data for date {query_date}')
                return None

            df_date = df_date.drop_duplicates(subset=[
                'fund_name', 'position_date', 'security_full_code',
                'market_value', 'accrued_interest', 'end_date',
            ])

            df_date['净值占比'] = (df_date['market_value'] + df_date['accrued_interest']) / df_date['fund_nav']
            df_date['证券市值'] = df_date['market_value'] + df_date['accrued_interest']

            first = df_date.iloc[0]
            fund_name = first['fund_name']

            # Indicator 2: Valuation volatility assets = sum of SPT_BD nav ratio
            indicator2 = df_date[df_date['asset_type'] == 'SPT_BD']['净值占比'].sum()

            # Indicator 3: Shadow price deviation
            indicator3 = first['shadow_price_deviation']

            # Indicator 4: Leverage ratio
            indicator4 = first['fund_total_asset'] / first['fund_nav']

            # Indicator 1: 14-day maturing asset nav ratio
            df_spd_bd = df_date[df_date['asset_type'] == 'SPT_BD'].copy()
            df_others = df_date[df_date['asset_type'].isin(['SPT_NGD', 'SPT_REPO'])].copy()
            df_merged = pd.concat([df_spd_bd, df_others], ignore_index=True)

            df_merged = self._enrich_maturity_dates(df_merged, df_spd_bd, query_date)
            filtered = self._filter_14day_maturing(df_merged)
            indicator1 = filtered['净值占比'].sum()

            return {
                'fund_name': fund_name,
                'query_date': query_date.strftime('%Y-%m-%d'),
                'indicator1_14day_maturity_ratio': indicator1,
                'indicator2_valuation_volatility': indicator2,
                'indicator3_shadow_deviation': indicator3,
                'indicator4_leverage': indicator4,
            }

        except Exception as e:
            logger.error(f'Failed to calculate warning indicators: {e}')
            return None

    @staticmethod
    def judge_warning_status(indicator_values, thresholds):
        """Determine warning status for each indicator.

        Args:
            indicator_values: dict with 4 indicator values
            thresholds: dict with threshold configuration

        Returns:
            dict with 4 status strings ('Normal' or 'Warning')
        """
        try:
            v1 = indicator_values['indicator1_14day_maturity_ratio']
            v2 = indicator_values['indicator2_valuation_volatility']
            v3 = indicator_values['indicator3_shadow_deviation']
            v4 = indicator_values['indicator4_leverage']

            t1 = thresholds.get('mm_indicator1_14day_maturity', 0.30)
            t2 = thresholds.get('mm_indicator2_valuation_volatility', 0.85)
            t3 = thresholds.get('mm_indicator3_shadow_deviation', -0.0008)
            t4 = thresholds.get('mm_indicator4_leverage', 1.15)

            # Indicator 1: (value + 10%) < threshold triggers warning
            s1 = 'Warning' if (v1 + 0.10) < t1 else 'Normal'
            s2 = 'Warning' if v2 >= t2 else 'Normal'
            s3 = 'Warning' if v3 >= t3 else 'Normal'
            s4 = 'Warning' if v4 >= t4 else 'Normal'

            return {
                'indicator1_status': s1,
                'indicator2_status': s2,
                'indicator3_status': s3,
                'indicator4_status': s4,
            }

        except Exception as e:
            logger.error(f'Failed to judge warning status: {e}')
            return {
                'indicator1_status': 'Unknown',
                'indicator2_status': 'Unknown',
                'indicator3_status': 'Unknown',
                'indicator4_status': 'Unknown',
            }
