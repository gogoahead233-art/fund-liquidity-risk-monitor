"""Bond fund calculation engine.

Computes basic info metrics (NAV, leverage, duration, convexity, BPV, maturity
distribution, LQI score, liquidity tiers) and 6 warning indicators for bond funds.

Ported from the original notebook-based calculator with full calculation logic
preserved. Wind API calls are replaced by the DataProvider abstraction.
"""

import logging
import re

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class BondCalculator:
    """Bond fund indicator calculator."""

    def __init__(self, db_session, data_provider=None):
        from app.models import (
            BondFundPosition, BondBasicInfoResult, BondWarningIndicatorResult,
        )
        self.db = db_session
        self.BondFundPosition = BondFundPosition
        self.BondBasicInfoResult = BondBasicInfoResult
        self.BondWarningIndicatorResult = BondWarningIndicatorResult
        self.data_provider = data_provider

    # ── Step 1: Load bond positions ─────────────────────────────────────────

    def load_bond_data(self, fund_name, date):
        """Load bond positions (asset_type containing 'BD') from the database.

        Returns a DataFrame with columns used by downstream calculations,
        including Wind-snapshot fields stored at import time.
        """
        positions = self.BondFundPosition.query.filter(
            self.BondFundPosition.fund_name == fund_name,
            self.BondFundPosition.pos_date == date,
            self.BondFundPosition.asset_type.like('%BD%'),
        ).all()

        # Fallback: fuzzy match on fund name
        if not positions:
            positions = self.BondFundPosition.query.filter(
                self.BondFundPosition.fund_name.contains(fund_name),
                self.BondFundPosition.pos_date == date,
                self.BondFundPosition.asset_type.like('%BD%'),
            ).all()

        if not positions:
            return None

        data = []
        for pos in positions:
            row = {
                '产品名称': fund_name,
                '交易日期': date,
                'I_NAME': pos.security_name or '',
                'A_TYPE': pos.asset_type or '',
                '证券代码': pos.security_code or '',
                'H_EVAL': pos.market_value or 0,
                'H_AI': pos.accrued_interest or 0,
                'H_COUNT': pos.security_quantity or 0,
                'P_TOTALNAV': pos.fund_nav or 0,
                'P_TOTAL_ASSET': pos.fund_total_asset or 0,
                'LIQUITOR': pos.lqi_indicator or 0,
                'IMPRATING': pos.implied_rating or '',
                'STMIRS': pos.mirs_indicator,
                'STMIRS_STR': pos.stmirs_text or '',
            }

            # Use Wind-snapshot fields from DB when available
            if pos.wind_implied_rating:
                row.update({
                    '债券类型': pos.bond_type or '',
                    '估值收益率': pos.valuation_yield or 0,
                    '债券久期': pos.bond_duration or 0,
                    '隐含评级': pos.wind_implied_rating or '',
                    '行业分类': pos.industry_classification or '',
                    '发行主体': pos.issuer or '',
                    '债券凸性': pos.bond_convexity or 0,
                    '剩余期限': pos.remaining_maturity or 0,
                    '城投债标识': pos.city_investment_bond or '',
                    '省份': pos.province or '',
                    '债项评级': pos.bond_rating or '',
                    '基点价值': pos.basis_point_value or 0,
                })

            data.append(row)

        df = pd.DataFrame(data)

        # Nav ratio = (market_value + accrued_interest) / fund_nav
        df['净值占比'] = (df['H_EVAL'] + df['H_AI']) / df['P_TOTALNAV']
        df['净值占比1'] = (df['H_EVAL'] + df['H_AI']) / df['P_TOTAL_ASSET']

        return df

    # ── Step 2: Fetch market data via DataProvider ──────────────────────────

    def get_market_data(self, codes):
        """Fetch bond market data via DataProvider for codes missing DB snapshots."""
        if self.data_provider is None or not self.data_provider.is_available():
            logger.warning('DataProvider not available, using DB snapshots only')
            return None

        rows = []
        for code in codes:
            rows.append({
                '证券代码': code,
                '债券类型': self.data_provider.get_bond_type(code) or '',
                '估值收益率': self.data_provider.get_bond_ytm(code) or 0,
                '债券久期': self.data_provider.get_bond_duration(code) or 0,
                '隐含评级': self.data_provider.get_bond_implied_rating(code) or '',
                '行业分类': self.data_provider.get_bond_industry(code) or '',
                '发行主体': self.data_provider.get_bond_issuer(code) or '',
                '债券凸性': self.data_provider.get_bond_convexity(code) or 0,
                '剩余期限': self.data_provider.get_bond_remaining_maturity(code) or 0,
                '城投债标识': 'Y' if self.data_provider.is_lgfv_bond(code) else 'N',
                '省份': self.data_provider.get_bond_province(code) or '',
                '债项评级': self.data_provider.get_bond_rating(code) or '',
                '基点价值': self.data_provider.get_bond_bpv(code) or 0,
            })

        return pd.DataFrame(rows) if rows else None

    # ── Step 3: Bond classification ─────────────────────────────────────────

    def classify_bonds(self, df):
        """Classify bonds into categories: rate bonds, short-term CP, bank bonds, corporate bonds."""
        src = '债券类型'
        tgt = '债券分类'

        conditions = [
            df[src].isin(['国债', '政策银行债']),
            df[src].isin(['超短期融资债券', '证券公司短期融资券', '一般短期融资券']),
            df[src].isin(['同业存单', '商业银行债', '地方政府债', '商业银行次级债券']),
        ]
        choices = ['利率债', '短期融资券', df[src]]
        df[tgt] = np.select(conditions, choices, default='企业债')
        return df

    # ── Step 4: Liquidity tier assignment ───────────────────────────────────

    def calculate_bond_liquidity_ratings(self, df):
        """Assign S/A/B/C/D liquidity tiers based on LIQUITOR score and bond type."""
        def get_rating_and_score(score, bond_type):
            if score == 0:
                if bond_type in ['可转债', '可交换债', '国债']:
                    return 'A', 0.75
                elif bond_type in ['地方政府债', '金融总局主管ABS']:
                    return 'C', 0.3
                elif bond_type == '同业存单':
                    return 'A', 0.7
                else:
                    return 'D', 0.5
            elif 0 < score <= 0.2:
                return 'D', score
            elif 0.2 < score <= 0.5:
                return 'C', score
            elif 0.5 < score <= 0.65:
                return 'B', score
            elif 0.65 < score <= 0.8:
                return 'A', score
            else:
                return 'S', score

        df[['流动性分档', 'LIQUITOR']] = df.apply(
            lambda row: pd.Series(get_rating_and_score(row['LIQUITOR'], row['债券类型'])),
            axis=1,
        )
        return df

    # ── Step 5: LQI score ───────────────────────────────────────────────────

    def calculate_liquidity_ratings(self, df):
        """Calculate weighted LQI score per fund per date."""
        df['总净值'] = df.groupby(['产品名称', '交易日期'])['净值占比'].transform('sum')
        df['LQI评分'] = (df['LIQUITOR'] / df['总净值']) * df['净值占比']
        result = df.groupby(['产品名称', '交易日期'])['LQI评分'].sum().reset_index()
        return result[['产品名称', '交易日期', 'LQI评分']]

    # ── Step 6: Liquidity tier summary ──────────────────────────────────────

    def calculate_liquidity_ratings_1(self, df):
        """Summarize nav ratio by liquidity tier."""
        return df.groupby(['产品名称', '交易日期', '流动性分档'])['净值占比'].sum().reset_index()

    # ── Step 7: Basic info metrics ──────────────────────────────────────────

    def calculate_bond_basic(self, df):
        """Calculate basic info: static yield, duration, convexity, BPV, maturity distribution."""
        grouped = df.groupby(['产品名称', '交易日期'])

        metrics = pd.DataFrame({
            '静态收益率': grouped.apply(lambda x: (x['净值占比'] * x['估值收益率']).sum() / 100),
            '杠杆后久期': grouped.apply(lambda x: (x['净值占比'] * x['债券久期']).sum()),
            '组合凸性': grouped.apply(lambda x: (x['净值占比'] * x['债券凸性']).sum()),
            '基点价值(万元)': grouped.apply(lambda x: (x['H_COUNT'] * x['基点价值']).sum()),
            '剩余期限1年以内债券占净值比': grouped.apply(lambda x: x[x['剩余期限'] <= 1]['净值占比'].sum()),
            '剩余期限1年-3年债券占净值比': grouped.apply(lambda x: x[(x['剩余期限'] > 1) & (x['剩余期限'] <= 3)]['净值占比'].sum()),
            '剩余期限3年-5年债券占净值比': grouped.apply(lambda x: x[(x['剩余期限'] > 3) & (x['剩余期限'] <= 5)]['净值占比'].sum()),
            '剩余期限5年以上债券占净值比': grouped.apply(lambda x: x[x['剩余期限'] > 5]['净值占比'].sum()),
            '杠杆率': grouped.apply(lambda x: x['P_TOTAL_ASSET'].sum() / x['P_TOTALNAV'].sum()),
        }).reset_index()

        result = pd.merge(df, metrics, on=['产品名称', '交易日期'], how='left')
        result['杠杆前久期'] = result['杠杆后久期'] / result['杠杆率']
        result['P_TOTALNAV'] = result['P_TOTALNAV'] / 1e8
        result['基点价值(万元)'] = result['基点价值(万元)'] / 1e4
        result = result.rename(columns={'P_TOTALNAV': '净资产(亿)'})
        result = result.drop_duplicates(keep='first')

        cols = ['产品名称', '交易日期', '净资产(亿)', '杠杆率', '静态收益率',
                '杠杆前久期', '杠杆后久期', '组合凸性', '基点价值(万元)',
                '剩余期限1年以内债券占净值比', '剩余期限1年-3年债券占净值比',
                '剩余期限3年-5年债券占净值比', '剩余期限5年以上债券占净值比']

        decimal_cols = ['净资产(亿)', '杠杆率', '静态收益率', '杠杆前久期',
                        '杠杆后久期', '组合凸性', '基点价值(万元)']
        result[decimal_cols] = result[decimal_cols].round(2)

        return result[cols]

    # ── Step 8: Warning indicator calculation ───────────────────────────────

    def _normalize_stmirs(self, df):
        """Normalize STMIRS string values for consistent matching."""
        base = df['STMIRS_STR'] if 'STMIRS_STR' in df.columns else df.get('STMIRS', '')
        df['STMIRS_STR'] = (
            base.astype(str).str.strip()
            .str.replace('－', '-', regex=False)
            .str.replace('—', '-', regex=False)
            .str.replace('–', '-', regex=False)
            .str.replace('−', '-', regex=False)
            .str.replace('／', '/', regex=False)
            .str.replace('\\', '/', regex=False)
            .str.replace(' ', '', regex=False)
        )

        def to_stmirs_str(row):
            if 'STMIRS_STR' in row.index and pd.notna(row['STMIRS_STR']) and str(row['STMIRS_STR']).strip():
                return str(row['STMIRS_STR']).strip()
            x = row['STMIRS']
            try:
                if pd.isna(x):
                    return 'nan'
            except (TypeError, ValueError):
                pass
            if isinstance(x, (int, float)) and x != 0:
                return str(int(x))
            s = str(x).strip()
            if s == '' or s.lower() == 'nan':
                return 'nan'
            s = re.sub(r'^\d{4}/', '', s)
            try:
                fv = float(s)
                return str(int(fv)) if fv == int(fv) else s
            except ValueError:
                return s

        df['STMIRS_STR'] = df.apply(to_stmirs_str, axis=1)
        return df

    def calculate_bond_metrics(self, df):
        """Calculate 5 warning indicators (indicators 2-6)."""
        grouped = df.groupby(['产品名称', '交易日期'])

        # Normalize text columns
        df['行业分类'] = (df['行业分类'].fillna('').astype(str).str.strip()
                       .str.replace('（', '(', regex=False)
                       .str.replace('）', ')', regex=False))
        df['城投债标识'] = df['城投债标识'].fillna('').astype(str).str.strip()
        df['隐含评级'] = df['隐含评级'].fillna('').astype(str).str.strip()
        df = self._normalize_stmirs(df)

        metrics = pd.DataFrame({
            # Indicator 6: Real estate industry ratio
            '地产行业占比': grouped.apply(lambda x: x[
                (x['行业分类'].isin(['房地产(2021)'])) &
                (x['隐含评级'].isin(['AA-', 'A+', 'AA+', 'AA']))
            ]['净值占比'].sum()),

            # Indicator 5: Leverage ratio
            '杠杆率': grouped.apply(lambda x: x['P_TOTAL_ASSET'].sum() / x['P_TOTALNAV'].sum()),

            # AA(2) 4/5 and below short-term bond ratio
            '隐含评级AA(2)4/5及以下短债占比': grouped.apply(lambda x: x[
                (x['债券分类'].isin(['短期融资券', '同业存单'])) &
                ((x['隐含评级'].isin(['AA-', 'A+'])) |
                 (x['隐含评级'].isin(['AA(2)']) &
                  x['STMIRS_STR'].isin(['45721', '45693', '45752', '45782',
                                        '4-/5', '4+/5', '5-/5', '5+/5'])))
            ]['净值占比'].sum()),

            # AA and below corporate bond ratio
            'AA及以下企业债券': grouped.apply(lambda x: x[
                (x['债券分类'].isin(['企业债'])) &
                ((x['隐含评级'].isin(['AA']) & x['城投债标识'].isin(['否']) &
                  x['STMIRS_STR'].isin(['45690', '45659', '2-/2', '2+/2'])) |
                 (x['隐含评级'].isin(['AA-', 'A+', 'AA(2)'])) |
                 (x['隐含评级'].isin(['AA+']) & x['行业分类'].isin(['房地产(2021)'])) |
                 (x['隐含评级'].isin(['AA']) & x['行业分类'].isin(['房地产(2021)']) &
                  x['STMIRS_STR'].isin(['45662', '1+/5', '1-/5'])) |
                 (x['隐含评级'].isin(['AA']) &
                  x['STMIRS_STR'].isin(['45721', '45693', '45752', '45782',
                                        '4-/5', '4+/5', '5-/5', '5+/5'])))
            ]['净值占比'].sum()),

            # AA 2/2 and below bank bond ratio
            '隐含评级AA2/2及以下银行债券占比': grouped.apply(lambda x: x[
                (x['债券分类'].isin(['商业银行债', '商业银行次级债券'])) &
                ((x['隐含评级'].isin(['AA-', 'A+'])) |
                 (x['隐含评级'].isin(['AA']) &
                  x['STMIRS_STR'].isin(['45690', '2-/2', '2+/2'])))
            ]['净值占比'].sum()),

            # Indicator 3: AA(2) 5/5 and below bond ratio
            '隐含评级AA(2)5/5及以下债券占比': grouped.apply(lambda x: x[
                (x['隐含评级'].isin(['AA-', 'A+'])) |
                (x['隐含评级'].isin(['AA(2)']) &
                 x['STMIRS_STR'].isin(['45782', '5-/5', '5+/5']))
            ]['净值占比'].sum()),

            # Indicator 4: Max single low-rated issuer holding ratio
            '低评级主体最大持仓占比': grouped.apply(lambda x:
                x[x['隐含评级'].isin(['AA-', 'A+'])]
                .groupby('发行主体')['净值占比'].sum().max()),
        }).reset_index()

        result = pd.merge(df, metrics, on=['产品名称', '交易日期'], how='left')
        result['P_TOTALNAV'] = result['P_TOTALNAV'] / 1e8

        # Indicator 2: Combined AA and below ratio
        result['指标2:隐含评级AA及以下债券合计占比'] = (
            result['隐含评级AA(2)4/5及以下短债占比'] +
            result['AA及以下企业债券'] +
            result['隐含评级AA2/2及以下银行债券占比']
        )

        result = result.rename(columns={
            'P_TOTALNAV': '净资产(亿)',
            '杠杆率': '指标5:杠杆率',
            '隐含评级AA(2)5/5及以下债券占比': '指标3:AA(2)及以下债券合计占比',
            '低评级主体最大持仓占比': '指标4:隐含评级AA-及以下的单个信用主体持仓占比',
            '地产行业占比': '指标6:地产行业占比',
        })

        result = result.drop_duplicates(keep='first')
        cols = ['产品名称', '交易日期', '指标2:隐含评级AA及以下债券合计占比',
                '指标3:AA(2)及以下债券合计占比',
                '指标4:隐含评级AA-及以下的单个信用主体持仓占比',
                '指标5:杠杆率', '指标6:地产行业占比']
        result['指标5:杠杆率'] = result['指标5:杠杆率'].round(2)
        return result[cols]

    def calculate_bond_index(self, df):
        """Calculate indicator 1: high-liquidity asset ratio after leverage."""
        grouped = df.groupby(['产品名称', '交易日期'])

        metrics = pd.DataFrame({
            '利率债': grouped.apply(lambda x: x[x['债券分类'].isin(['利率债'])]['净值占比'].sum()),
            '杠杆率': grouped.apply(lambda x: x['P_TOTAL_ASSET'].sum() / x['P_TOTALNAV'].sum()),
            'AA+及以上短融银行债': grouped.apply(lambda x: x[
                (x['债券分类'].isin(['短期融资券', '同业存单', '商业银行债', '商业银行次级债券'])) &
                (x['隐含评级'].isin(['AA+', 'AAA-', 'AAA']))
            ]['净值占比'].sum()),
            'AA+及以上企业债券': grouped.apply(lambda x: x[
                (x['债券分类'].isin(['企业债'])) &
                ((x['隐含评级'].isin(['AAA-', 'AAA'])) |
                 (x['隐含评级'].isin(['AA+']) &
                  (~x['行业分类'].isin(['房地产(2021)'])) &
                  (x['剩余期限'] < 1)))
            ]['净值占比'].sum()),
        }).reset_index()

        result = pd.merge(df, metrics, on=['产品名称', '交易日期'], how='left')

        result['指标1:考虑融资杠杆后的流动性资产'] = (
            result['利率债'] +
            result['AA+及以上短融银行债'] +
            result['AA+及以上企业债券'] +
            result['杠杆率'].apply(lambda x: max(1.3 - x, 0))
        ) - 0.05

        result = result.drop_duplicates(keep='first')
        result = result.sort_values(['产品名称', '交易日期']).reset_index(drop=True)
        return result[['产品名称', '交易日期', '指标1:考虑融资杠杆后的流动性资产']]

    # ── Main entry point ────────────────────────────────────────────────────

    def process_and_calculate(self, fund_name, date):
        """Run full calculation pipeline.

        Returns: (basic_df, metrics_df, index_df, liquidity_tiers_df, lqi_df)
        """
        logger.info(f'Calculating bond fund: {fund_name} - {date}')

        # Step 1: Load positions
        df = self.load_bond_data(fund_name, date)
        if df is None or len(df) == 0:
            logger.warning(f'No data found: {fund_name} - {date}')
            return None, None, None, None, None

        # Step 2: Enrich with market data if DB snapshots are missing
        if '隐含评级' not in df.columns:
            codes = df['证券代码'].dropna().unique().tolist()
            market_df = self.get_market_data(codes)
            if market_df is not None:
                df = pd.merge(df, market_df, on='证券代码', how='left')
                df['隐含评级'] = df['隐含评级'].fillna(df.get('IMPRATING', ''))
            else:
                df['隐含评级'] = df['IMPRATING'].fillna('')
                for col in ['债券类型', '行业分类', '发行主体', '城投债标识', '省份', '债项评级']:
                    if col not in df.columns:
                        df[col] = ''
                for col in ['估值收益率', '债券久期', '债券凸性', '基点价值']:
                    if col not in df.columns:
                        df[col] = 0
                if '剩余期限' not in df.columns:
                    df['剩余期限'] = np.nan

        # Step 3: Classify bonds
        df = self.classify_bonds(df)

        # Step 4: Liquidity tiers
        df = self.calculate_bond_liquidity_ratings(df)

        # Step 5: LQI score
        lqi_df = self.calculate_liquidity_ratings(df.copy())

        # Step 6: Warning indicators (2-6)
        metrics_df = self.calculate_bond_metrics(df.copy())

        # Step 7: High-liquidity asset (indicator 1)
        index_df = self.calculate_bond_index(df.copy())

        # Step 8: Liquidity tier summary
        liquidity_tiers_df = self.calculate_liquidity_ratings_1(df.copy())

        # Step 9: Basic info
        basic_df = self.calculate_bond_basic(df.copy())

        logger.info(f'Calculation complete: {fund_name} - {date}')
        return basic_df, metrics_df, index_df, liquidity_tiers_df, lqi_df

    # ── Save results to database ────────────────────────────────────────────

    def save_to_database(self, fund_name, date, basic_df, metrics_df, index_df,
                         liquidity_tiers_df, lqi_df):
        """Persist calculation results to the database."""
        try:
            # Save basic info
            if basic_df is not None and len(basic_df) > 0:
                row = basic_df.iloc[0]

                liquidity_ratios = {}
                if liquidity_tiers_df is not None and len(liquidity_tiers_df) > 0:
                    tier_map = {'S': 'liquidity_s_ratio', 'A': 'liquidity_a_ratio',
                                'B': 'liquidity_b_ratio', 'C': 'liquidity_c_ratio',
                                'D': 'liquidity_d_ratio'}
                    for _, tr in liquidity_tiers_df.iterrows():
                        key = tier_map.get(tr['流动性分档'])
                        if key:
                            liquidity_ratios[key] = tr['净值占比']

                lqi_score = float(lqi_df.iloc[0]['LQI评分']) if lqi_df is not None and len(lqi_df) > 0 else 0

                existing = self.BondBasicInfoResult.query.filter_by(
                    fund_name=fund_name, query_date=date).first()

                vals = dict(
                    net_asset_billion=float(row['净资产(亿)']),
                    leverage_ratio=float(row['杠杆率']),
                    static_yield=float(row['静态收益率']),
                    duration_before_leverage=float(row['杠杆前久期']),
                    duration_after_leverage=float(row['杠杆后久期']),
                    portfolio_convexity=float(row['组合凸性']),
                    bpv_10000=float(row['基点价值(万元)']),
                    maturity_under_1yr_ratio=float(row['剩余期限1年以内债券占净值比']),
                    maturity_1to3yr_ratio=float(row['剩余期限1年-3年债券占净值比']),
                    maturity_3to5yr_ratio=float(row['剩余期限3年-5年债券占净值比']),
                    maturity_over_5yr_ratio=float(row['剩余期限5年以上债券占净值比']),
                    lqi_score=lqi_score,
                    **{k: float(v) for k, v in liquidity_ratios.items()},
                )

                if existing:
                    for k, v in vals.items():
                        setattr(existing, k, v)
                else:
                    self.db.add(self.BondBasicInfoResult(
                        fund_name=fund_name, query_date=date, **vals))

            # Save warning indicators
            if (metrics_df is not None and len(metrics_df) > 0
                    and index_df is not None and len(index_df) > 0):
                mrow = metrics_df.iloc[0]
                irow = index_df.iloc[0]

                from app.models import WarningThreshold
                thresholds = {t.indicator_name: t.threshold_value
                              for t in WarningThreshold.query.all()}

                t1 = thresholds.get('bond_indicator1_high_liquidity', 0.35)
                t2 = thresholds.get('bond_indicator2_aa_below', 0.80)
                t3 = thresholds.get('bond_indicator3_aa2_below', 0.40)
                t4 = thresholds.get('bond_indicator4_single_issuer', 0.08)
                t5 = thresholds.get('bond_indicator5_leverage', 1.30)
                t6 = thresholds.get('bond_indicator6_real_estate', 0.40)

                v1 = float(irow['指标1:考虑融资杠杆后的流动性资产'])
                v2 = float(mrow['指标2:隐含评级AA及以下债券合计占比'])
                v3 = float(mrow['指标3:AA(2)及以下债券合计占比'])
                v4 = float(mrow['指标4:隐含评级AA-及以下的单个信用主体持仓占比'])
                v5 = float(mrow['指标5:杠杆率'])
                v6 = float(mrow['指标6:地产行业占比'])

                s1 = 'Warning' if v1 < t1 else 'Normal'
                s2 = 'Warning' if v2 >= t2 else 'Normal'
                s3 = 'Warning' if v3 >= t3 else 'Normal'
                s4 = 'Warning' if v4 >= t4 else 'Normal'
                s5 = 'Warning' if v5 >= t5 else 'Normal'
                s6 = 'Warning' if v6 >= t6 else 'Normal'

                existing = self.BondWarningIndicatorResult.query.filter_by(
                    fund_name=fund_name, query_date=date).first()

                indicator_vals = dict(
                    indicator1_high_liquidity=v1, indicator2_aa_below_ratio=v2,
                    indicator3_aa2_below_ratio=v3, indicator4_low_rating_max_ratio=v4,
                    indicator5_leverage=v5, indicator6_real_estate_ratio=v6,
                    indicator1_status=s1, indicator2_status=s2,
                    indicator3_status=s3, indicator4_status=s4,
                    indicator5_status=s5, indicator6_status=s6,
                )

                if existing:
                    for k, v in indicator_vals.items():
                        setattr(existing, k, v)
                else:
                    self.db.add(self.BondWarningIndicatorResult(
                        fund_name=fund_name, query_date=date, **indicator_vals))

            self.db.commit()
            logger.info(f'Saved results: {fund_name} - {date}')
            return True

        except Exception as e:
            logger.error(f'Failed to save: {e}')
            self.db.rollback()
            return False
