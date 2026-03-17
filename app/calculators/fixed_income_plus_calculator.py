"""Fixed Income Plus fund calculation engine.

Computes basic info metrics (NAV, asset allocation ratios, stock volatility/beta,
convertible bond premiums, portfolio duration) and 7 warning indicators.

Wind API calls are replaced by the DataProvider abstraction. When unavailable,
the calculator uses DB-snapshot fields stored at import time.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FixedIncomePlusCalculator:
    """Fixed Income Plus fund indicator calculator."""

    def __init__(self, db_session, data_provider=None):
        from app.models import (
            FixedIncomePlusFundPosition,
            FixedIncomePlusBasicInfoResult,
            FixedIncomePlusWarningIndicatorResult,
        )
        self.db = db_session
        self.Position = FixedIncomePlusFundPosition
        self.BasicResult = FixedIncomePlusBasicInfoResult
        self.WarningResult = FixedIncomePlusWarningIndicatorResult
        self.data_provider = data_provider

    # ── Data loading ────────────────────────────────────────────────────────

    def load_all_data(self, fund_name, date):
        """Load all position data for a fund on a given date."""
        from datetime import datetime as dt

        if isinstance(date, dt):
            date = date.date()

        positions = self.Position.query.filter(
            self.Position.fund_name == fund_name,
            self.Position.position_date == date,
        ).all()

        # Fallback: fuzzy match on fund name
        if not positions:
            positions = self.Position.query.filter(
                self.Position.fund_name.contains(fund_name),
                self.Position.position_date == date,
            ).all()

        if not positions:
            return None

        data = []
        for pos in positions:
            market_val = pos.market_value or 0
            accrued_int = pos.accrued_interest or 0
            nav = pos.fund_nav or 1
            asset_type = pos.asset_type or ''

            # Repo: use market value directly; others: market_value + accrued
            if asset_type == 'SPT_REPO':
                net_value_ratio = market_val / nav if nav else 0
            else:
                net_value_ratio = (market_val + accrued_int) / nav if nav else 0

            # Auto-classify bond type from asset_type if not stored
            bond_classification = pos.bond_classification
            if not bond_classification or bond_classification == 'None':
                if asset_type == 'SPT_CB':
                    bond_classification = '可转债'
                elif asset_type == 'SPT_BD':
                    sec_name = pos.security_name or ''
                    if '转债' in sec_name or 'CB' in sec_name.upper():
                        bond_classification = '可转债'
                    elif any(k in sec_name for k in ['国债', '政策', '国开']):
                        bond_classification = '利率债'
                    else:
                        bond_classification = '企业债'
                else:
                    bond_classification = '企业债'

            data.append({
                '产品名称': fund_name,
                '交易日期': date,
                'A_TYPE': asset_type,
                '证券代码': pos.security_full_code or '',
                'I_NAME': pos.security_name or '',
                '净值占比': net_value_ratio,
                'H_COUNT': pos.security_quantity or 0,
                'P_TOTALNAV': nav,
                'P_TOTAL_ASSET': pos.fund_total_asset or 0,
                '债券分类': bond_classification,
                '债券久期': pos.bond_duration or 0,
                '纯债溢价率': pos.pure_bond_premium or 0,
                '转股溢价率': pos.conversion_premium or 0,
                '股票beta': pos.stock_beta or 0,
                '股票波动率': pos.stock_volatility or 0,
                '隐含评级': pos.implied_rating or '',
                '行业分类': pos.industry_classification or '',
                '发行主体': pos.issuer or '',
                '剩余期限': pos.remaining_maturity or 999,
                '城投债标识': pos.municipal_bond_flag or '',
                'STMIRS': pos.stmirs_text or '',
                '债券类型': '',
            })

        return pd.DataFrame(data)

    # ── DataProvider enrichment ─────────────────────────────────────────────

    def _enrich_stock_data(self, df_stock):
        """Enrich stock positions with beta and volatility from DataProvider."""
        if df_stock is None or len(df_stock) == 0:
            return df_stock

        if not self.data_provider or not self.data_provider.is_available():
            logger.warning('DataProvider not available, using DB snapshots for stocks')
            return df_stock

        try:
            codes = [c for c in df_stock['证券代码'].unique() if c]
            if not codes:
                return df_stock

            rows = []
            for code in codes:
                rows.append({
                    '证券代码': code,
                    '股票beta': self.data_provider.get_stock_beta(code) or 0,
                    '股票波动率': self.data_provider.get_stock_volatility(code) or 0,
                })

            wind_df = pd.DataFrame(rows)
            df_stock = df_stock.merge(wind_df, on='证券代码', how='left',
                                      suffixes=('_old', ''))
            for col in ['股票beta_old', '股票波动率_old']:
                if col in df_stock.columns:
                    df_stock = df_stock.drop(columns=[col])

            return df_stock
        except Exception as e:
            logger.error(f'Failed to enrich stock data: {e}')
            return df_stock

    def _enrich_bond_data(self, df_bond):
        """Enrich bond positions with market data from DataProvider."""
        if df_bond is None or len(df_bond) == 0:
            return df_bond

        if not self.data_provider or not self.data_provider.is_available():
            logger.warning('DataProvider not available, using DB snapshots for bonds')
            return df_bond

        try:
            codes = [c for c in df_bond['证券代码'].unique() if c]
            if not codes:
                return df_bond

            # Check if key fields are missing
            key_cols = ['隐含评级', '行业分类', '发行主体', '剩余期限', '城投债标识', '债券久期', '债券类型']
            existing = [c for c in key_cols if c in df_bond.columns]
            missing = (len(existing) < len(key_cols)) or \
                      df_bond[existing].apply(lambda c: (c == '') | c.isna()).any(axis=1).any()

            if not missing:
                return df_bond

            rows = []
            for code in codes:
                bond_type = self.data_provider.get_bond_type(code) or ''

                # Classify bond type (mirroring original logic)
                if bond_type in ['国债', '政策银行债']:
                    classification = '利率债'
                elif bond_type in ['可转债', '可交换债']:
                    classification = '可转债'
                elif bond_type in ['超短期融资债券', '证券公司短期融资券', '一般短期融资券', '短期融资债券']:
                    classification = '短期融资券'
                elif bond_type in ['同业存单', '商业银行债', '地方政府债', '商业银行次级债券']:
                    classification = bond_type
                else:
                    classification = '企业债'

                rows.append({
                    '证券代码': code,
                    '债券类型': bond_type,
                    '债券久期': self.data_provider.get_bond_duration(code) or 0,
                    '隐含评级': self.data_provider.get_bond_implied_rating(code) or '',
                    '行业分类': self.data_provider.get_bond_industry(code) or '',
                    '发行主体': self.data_provider.get_bond_issuer(code) or '',
                    '剩余期限': self.data_provider.get_bond_remaining_maturity(code) or 999,
                    '城投债标识': 'Y' if self.data_provider.is_lgfv_bond(code) else 'N',
                    '债项评级': self.data_provider.get_bond_rating(code) or '',
                    '纯债溢价率': self.data_provider.get_convertible_bond_premium(code) or 0,
                    '转股溢价率': self.data_provider.get_conversion_premium(code) or 0,
                    '债券分类': classification,
                })

            wind_df = pd.DataFrame(rows)
            df_bond = df_bond.merge(
                wind_df, on='证券代码', how='left', suffixes=('_old', ''))
            old_cols = [c for c in df_bond.columns if c.endswith('_old')]
            if old_cols:
                df_bond = df_bond.drop(columns=old_cols)

            return df_bond
        except Exception as e:
            logger.error(f'Failed to enrich bond data: {e}')
            return df_bond

    # ── Main calculation ────────────────────────────────────────────────────

    def process_and_calculate(self, fund_name, date):
        """Run full calculation pipeline.

        Returns: (basic_info_dict, warning_indicators_dict)
        """
        logger.info(f'Calculating fixed income plus fund: {fund_name} - {date}')

        # 1. Load data
        df = self.load_all_data(fund_name, date)
        if df is None or len(df) == 0:
            logger.warning(f'No data found: {fund_name} - {date}')
            return None, None

        # 2. Split by asset type
        data_FX = df[df['A_TYPE'].isin(['SPT_CB', 'SPT_BD'])].copy()  # Bonds (incl. convertible)
        data_ST = df[df['A_TYPE'].isin(['SPT_S'])].copy()  # Stocks
        data_DB = df[df['A_TYPE'].isin(['SPT_DED'])].copy()  # Demand deposits
        # Reverse repo: A_TYPE=SPT_REPO and H_COUNT=1 (exclude normal repo with H_COUNT=-1)
        data_NG = df[(df['A_TYPE'].isin(['SPT_REPO'])) & (df['H_COUNT'] == 1)].copy()

        # 3. Enrich with DataProvider
        if len(data_ST) > 0:
            data_ST = self._enrich_stock_data(data_ST)
        if len(data_FX) > 0:
            data_FX = self._enrich_bond_data(data_FX)
            # Normalize STMIRS strings
            data_FX['STMIRS'] = (
                data_FX['STMIRS'].astype(str).str.strip()
                .str.replace('－', '-', regex=False)
                .str.replace('—', '-', regex=False)
                .str.replace('−', '-', regex=False)
                .str.replace('／', '/', regex=False)
                .str.replace('\\', '/', regex=False)
                .str.replace(' ', '', regex=False)
            )

        # 4. Stock metrics (weighted average)
        stock_volatility = 0
        stock_beta = 0
        stock_ratio = data_ST['净值占比'].sum() if len(data_ST) > 0 else 0

        if len(data_ST) > 0 and stock_ratio > 0:
            # Wind returns annualized volatility as percentage (e.g. 41.0), divide by 100
            stock_volatility = (data_ST['股票波动率'] * data_ST['净值占比']).sum() / stock_ratio / 100
            stock_beta = (data_ST['股票beta'] * data_ST['净值占比']).sum() / stock_ratio

        # 5. Convertible bond metrics
        convertible_bonds = data_FX[data_FX['债券分类'] == '可转债'].copy() if len(data_FX) > 0 else pd.DataFrame()
        pure_bond_premium = 0
        conversion_premium = 0
        convertible_ratio = 0

        if len(convertible_bonds) > 0:
            convertible_ratio = convertible_bonds['净值占比'].sum()
            if convertible_ratio > 0:
                pure_bond_premium = (convertible_bonds['纯债溢价率'] * convertible_bonds['净值占比']).sum() / convertible_ratio / 100
                conversion_premium = (convertible_bonds['转股溢价率'] * convertible_bonds['净值占比']).sum() / convertible_ratio / 100

        # 6. Portfolio duration
        portfolio_duration = (data_FX['净值占比'] * data_FX['债券久期']).sum() if len(data_FX) > 0 else 0

        # 7. Basic info
        basic_info = {
            'fund_name': fund_name,
            'query_date': date,
            'net_asset_billion': round(df['P_TOTALNAV'].iloc[0] / 1e8, 2) if len(df) > 0 else 0,
            'bond_ratio': round(data_FX[data_FX['债券分类'] != '可转债']['净值占比'].sum(), 4) if len(data_FX) > 0 else 0,
            'convertible_bond_ratio': round(convertible_ratio, 4),
            'stock_ratio': round(stock_ratio, 4),
            'demand_deposit_ratio': round(data_DB['净值占比'].sum(), 4) if len(data_DB) > 0 else 0,
            'repo_ratio': round(data_NG['净值占比'].sum(), 4) if len(data_NG) > 0 else 0,
            'stock_volatility': round(stock_volatility, 4),
            'stock_beta': round(stock_beta, 4),
            'pure_bond_premium_avg': round(pure_bond_premium, 4),
            'equity_premium_avg': round(conversion_premium, 4),
            'portfolio_duration': round(portfolio_duration, 2),
        }

        # 8. Warning indicators

        # Indicator 1: High-liquidity asset ratio
        rate_bonds = data_FX[data_FX['债券分类'].isin(['利率债'])]['净值占比'].sum() if len(data_FX) > 0 else 0

        aa_plus_short = 0
        if len(data_FX) > 0:
            aa_plus_short = data_FX[
                (data_FX['债券分类'].isin(['短期融资券', '同业存单', '商业银行债', '商业银行次级债券'])) &
                (data_FX['隐含评级'].isin(['AA+', 'AAA-', 'AAA']))
            ]['净值占比'].sum()

        aa_plus_corp = 0
        if len(data_FX) > 0:
            aa_plus_corp = data_FX[
                (data_FX['债券分类'].isin(['企业债'])) &
                ((data_FX['隐含评级'].isin(['AAA-', 'AAA'])) |
                 ((data_FX['隐含评级'].isin(['AA+'])) &
                  (~data_FX['行业分类'].isin(['房地产(2021)'])) &
                  (data_FX['剩余期限'].fillna(999) < 1)))
            ]['净值占比'].sum()

        deposit = data_DB['净值占比'].sum() if len(data_DB) > 0 else 0
        repo = data_NG['净值占比'].sum() if len(data_NG) > 0 else 0
        indicator1 = rate_bonds + aa_plus_short + aa_plus_corp + deposit + repo

        # Indicator 2: AA and below bonds combined ratio
        aa2_short = 0
        if len(data_FX) > 0:
            aa2_short = data_FX[
                (data_FX['债券分类'].isin(['短期融资券', '同业存单'])) &
                ((data_FX['隐含评级'].isin(['AA-', 'A+'])) |
                 ((data_FX['隐含评级'].isin(['AA(2)'])) &
                  (data_FX['STMIRS'].astype(str).isin(
                      ['45721', '45693', '45752', '45782', '4-/5', '4+/5', '5-/5', '5+/5']))))
            ]['净值占比'].sum()

        aa_below_corp = 0
        if len(data_FX) > 0:
            aa_below_corp = data_FX[
                (data_FX['债券分类'].isin(['企业债'])) &
                ((data_FX['隐含评级'].isin(['AA']) & data_FX['城投债标识'].isin(['否']) &
                  data_FX['STMIRS'].astype(str).isin(['45690', '45659', '2-/2', '2+/2'])) |
                 (data_FX['隐含评级'].isin(['AA-', 'A+', 'AA(2)'])) |
                 (data_FX['隐含评级'].isin(['AA+']) & data_FX['行业分类'].isin(['房地产(2021)'])) |
                 (data_FX['隐含评级'].isin(['AA']) & data_FX['行业分类'].isin(['房地产(2021)']) &
                  data_FX['STMIRS'].astype(str).isin(['45662', '1+/5', '1-/5'])) |
                 (data_FX['隐含评级'].isin(['AA']) &
                  data_FX['STMIRS'].astype(str).isin(
                      ['45721', '45693', '45752', '45782', '4-/5', '4+/5', '5-/5', '5+/5'])))
            ]['净值占比'].sum()

        aa2_bank = 0
        if len(data_FX) > 0:
            aa2_bank = data_FX[
                (data_FX['债券分类'].isin(['商业银行债', '商业银行次级债券'])) &
                ((data_FX['隐含评级'].isin(['AA-', 'A+'])) |
                 (data_FX['隐含评级'].isin(['AA']) &
                  data_FX['STMIRS'].astype(str).isin(['45690', '2-/2', '2+/2'])))
            ]['净值占比'].sum()

        indicator2 = aa2_short + aa_below_corp + aa2_bank

        # Indicator 3: AA(2) and below bond ratio
        indicator3 = 0
        if len(data_FX) > 0:
            indicator3 = data_FX[
                (data_FX['隐含评级'].isin(['AA-', 'A+'])) |
                ((data_FX['隐含评级'].isin(['AA(2)'])) &
                 (data_FX['STMIRS'].astype(str).isin(['45782', '5-/5', '5+/5'])))
            ]['净值占比'].sum()

        # Indicator 4: Max single low-rated issuer holding
        indicator4 = 0
        if len(data_FX) > 0:
            low_rated = data_FX[data_FX['隐含评级'].isin(['AA-', 'A+'])]
            if len(low_rated) > 0 and '发行主体' in low_rated.columns:
                issuer_holdings = low_rated.groupby('发行主体')['净值占比'].sum()
                if len(issuer_holdings) > 0:
                    indicator4 = issuer_holdings.max()

        # Indicator 5: Real estate industry ratio
        indicator5 = 0
        if len(data_FX) > 0:
            indicator5 = data_FX[
                (data_FX['行业分类'].isin(['房地产(2021)'])) &
                (data_FX['隐含评级'].isin(['AA-', 'A+', 'AA+', 'AA']))
            ]['净值占比'].sum()

        # Indicator 6: Leverage ratio
        leverage = (df['P_TOTAL_ASSET'].iloc[0] / df['P_TOTALNAV'].iloc[0]
                    if len(df) > 0 and df['P_TOTALNAV'].iloc[0] > 0 else 0)

        # Indicator 7: Equity securities ratio = stock + convertible/2
        indicator7 = basic_info['stock_ratio'] + basic_info['convertible_bond_ratio'] / 2

        warning_indicators = {
            'fund_name': fund_name,
            'query_date': date,
            'indicator1_high_liquidity': round(indicator1, 4),
            'indicator2_aa_below_ratio': round(indicator2, 4),
            'indicator3_aa2_below_ratio': round(indicator3, 4),
            'indicator4_low_rating_max_ratio': round(indicator4, 4),
            'indicator5_real_estate_ratio': round(indicator5, 4),
            'indicator6_leverage': round(leverage, 4),
            'indicator7_equity_securities_ratio': round(indicator7, 4),
        }

        logger.info(f'Calculation complete: {fund_name} - {date}')
        return basic_info, warning_indicators

    # ── Save results ────────────────────────────────────────────────────────

    def save_to_database(self, fund_name, date, basic_info, warning_indicators):
        """Persist calculation results to the database."""
        try:
            if basic_info:
                existing = self.BasicResult.query.filter_by(
                    fund_name=fund_name, query_date=date).first()

                vals = {k: v for k, v in basic_info.items()
                        if k not in ('fund_name', 'query_date')}

                if existing:
                    for k, v in vals.items():
                        setattr(existing, k, v)
                else:
                    self.db.add(self.BasicResult(
                        fund_name=fund_name, query_date=date, **vals))

            if warning_indicators:
                from app.models import WarningThreshold
                thresholds = {t.indicator_name: t.threshold_value
                              for t in WarningThreshold.query.all()}

                t1 = thresholds.get('fip_indicator1_high_liquidity', 0.10)
                t2 = thresholds.get('fip_indicator2_aa_below', 0.30)
                t3 = thresholds.get('fip_indicator3_aa2_below', 0.10)
                t4 = thresholds.get('fip_indicator4_single_issuer', 0.05)
                t5 = thresholds.get('fip_indicator5_real_estate', 0.10)
                t6 = thresholds.get('fip_indicator6_leverage', 1.40)
                t7 = thresholds.get('fip_indicator7_equity_securities', 0.30)

                w = warning_indicators
                statuses = {
                    'indicator1_status': 'Warning' if w['indicator1_high_liquidity'] < t1 else 'Normal',
                    'indicator2_status': 'Warning' if w['indicator2_aa_below_ratio'] >= t2 else 'Normal',
                    'indicator3_status': 'Warning' if w['indicator3_aa2_below_ratio'] >= t3 else 'Normal',
                    'indicator4_status': 'Warning' if w['indicator4_low_rating_max_ratio'] >= t4 else 'Normal',
                    'indicator5_status': 'Warning' if w['indicator5_real_estate_ratio'] >= t5 else 'Normal',
                    'indicator6_status': 'Warning' if w['indicator6_leverage'] >= t6 else 'Normal',
                    'indicator7_status': 'Warning' if w['indicator7_equity_securities_ratio'] >= t7 else 'Normal',
                }

                existing = self.WarningResult.query.filter_by(
                    fund_name=fund_name, query_date=date).first()

                vals = {k: v for k, v in w.items()
                        if k not in ('fund_name', 'query_date')}
                vals.update(statuses)

                if existing:
                    for k, v in vals.items():
                        setattr(existing, k, v)
                else:
                    self.db.add(self.WarningResult(
                        fund_name=fund_name, query_date=date, **vals))

            self.db.commit()
            logger.info(f'Saved results: {fund_name} - {date}')
            return True

        except Exception as e:
            logger.error(f'Failed to save: {e}')
            self.db.rollback()
            return False
