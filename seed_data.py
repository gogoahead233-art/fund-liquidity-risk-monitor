"""Seed the database with initial data for demo purposes."""

from datetime import date
from werkzeug.security import generate_password_hash
from app import create_app, db
from app.models import (
    User, UserPermission, WarningThreshold,
    InvestorPosition, InvestorTransaction,
    BondFundPosition, MoneyMarketFundPosition, FixedIncomePlusFundPosition,
    BondLiquidityWarning, MoneyMarketLiquidityWarning,
    FixedIncomePlusLiquidityWarning,
    BondBasicInfoResult, BondWarningIndicatorResult,
    MoneyMarketBasicInfoResult, MoneyMarketWarningIndicatorResult,
    FixedIncomePlusBasicInfoResult, FixedIncomePlusWarningIndicatorResult,
    FundStructureAnalysis,
)

DEMO_DATE = date(2025, 3, 14)

FUND_NAMES = [
    'Alpha Bond Fund A',
    'Beta Money Market Fund',
    'Gamma Fixed Income Plus Fund',
]


def seed():
    app = create_app()
    with app.app_context():
        db.create_all()

        _seed_users()
        _seed_thresholds()
        _seed_bond_positions()
        _seed_money_market_positions()
        _seed_fixed_income_plus_positions()
        _seed_investor_data()
        _seed_warning_records()
        _seed_result_cache()
        _seed_structure_analysis()

        db.session.commit()
        print('Database seeded successfully.')


def _seed_users():
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            is_admin=True,
        )
        db.session.add(admin)
        print('Created admin user (admin / admin123)')

    if not User.query.filter_by(username='demo').first():
        demo = User(
            username='demo',
            password=generate_password_hash('demo123'),
            is_admin=False,
        )
        db.session.add(demo)
        db.session.flush()
        for fund in FUND_NAMES[:1]:
            db.session.add(UserPermission(user_id=demo.id, fund_name=fund))
        print('Created demo user (demo / demo123) with bond fund permissions')


def _seed_thresholds():
    if WarningThreshold.query.first():
        return
    thresholds = [
        ('bond_indicator1_high_liquidity', 0.10, 'Bond: liquid asset ratio after leverage'),
        ('bond_indicator2_aa_below', 0.30, 'Bond: implied rating AA and below ratio'),
        ('bond_indicator3_aa2_below', 0.10, 'Bond: AA(2) and below ratio'),
        ('bond_indicator4_single_issuer', 0.05, 'Bond: single low-rated issuer max ratio'),
        ('bond_indicator5_leverage', 1.40, 'Bond: leverage ratio'),
        ('bond_indicator6_real_estate', 0.10, 'Bond: real estate industry ratio'),
        ('mm_indicator1_14day_maturity', 0.10, 'Money Market: 14-day maturing asset ratio'),
        ('mm_indicator2_valuation_volatility', 0.0025, 'Money Market: valuation volatility asset'),
        ('mm_indicator3_shadow_deviation', 0.0025, 'Money Market: shadow price deviation'),
        ('mm_indicator4_leverage', 1.20, 'Money Market: leverage ratio'),
        ('fip_indicator1_high_liquidity', 0.10, 'Fixed Income Plus: high liquidity asset ratio'),
        ('fip_indicator2_aa_below', 0.30, 'Fixed Income Plus: AA and below ratio'),
        ('fip_indicator3_aa2_below', 0.10, 'Fixed Income Plus: AA(2) and below ratio'),
        ('fip_indicator4_single_issuer', 0.05, 'Fixed Income Plus: single low-rated issuer max'),
        ('fip_indicator5_real_estate', 0.10, 'Fixed Income Plus: real estate ratio'),
        ('fip_indicator6_leverage', 1.40, 'Fixed Income Plus: leverage ratio'),
        ('fip_indicator7_equity_securities', 0.30, 'Fixed Income Plus: equity securities ratio'),
    ]
    for name, value, desc in thresholds:
        db.session.add(WarningThreshold(
            indicator_name=name, threshold_value=value, description=desc,
        ))
    print(f'Created {len(thresholds)} warning thresholds')


def _seed_bond_positions():
    if BondFundPosition.query.first():
        return
    positions = [
        dict(fund_name='Alpha Bond Fund A', security_name='CDB Bond 2024-01',
             security_code='240001.IB', asset_type='SPT_BD', market_type='Interbank',
             market_value=52000000, security_quantity=500000, accrued_interest=180000,
             fund_nav=520000000, fund_total_asset=680000000, lqi_indicator=1.0,
             mirs_indicator=5, implied_rating='AAA', stmirs_text='5/5',
             bond_type='政策银行债', valuation_yield=2.45, bond_duration=2.85,
             wind_implied_rating='AAA', industry_classification='Finance',
             issuer='Sample Development Bank', bond_convexity=9.12,
             remaining_maturity=2.5, city_investment_bond='否', province=None,
             bond_rating='AAA', basis_point_value=0.0285),
        dict(fund_name='Alpha Bond Fund A', security_name='Sample Infra Bond',
             security_code='240002.IB', asset_type='SPT_BD', market_type='Interbank',
             market_value=35000000, security_quantity=350000, accrued_interest=120000,
             fund_nav=520000000, fund_total_asset=680000000, lqi_indicator=0.6,
             mirs_indicator=3, implied_rating='AA+', stmirs_text='3/5',
             bond_type='企业债', valuation_yield=3.15, bond_duration=4.12,
             wind_implied_rating='AA+', industry_classification='Infrastructure',
             issuer='Sample Infra Corp.', bond_convexity=19.5,
             remaining_maturity=4.3, city_investment_bond='是', province='Jiangsu',
             bond_rating='AA+', basis_point_value=0.0412),
        dict(fund_name='Alpha Bond Fund A', security_name='Treasury 2024-03',
             security_code='240003.IB', asset_type='SPT_BD', market_type='Interbank',
             market_value=80000000, security_quantity=800000, accrued_interest=250000,
             fund_nav=520000000, fund_total_asset=680000000, lqi_indicator=1.0,
             mirs_indicator=5, implied_rating='AAA', stmirs_text='5/5',
             bond_type='国债', valuation_yield=2.15, bond_duration=1.65,
             wind_implied_rating='AAA', industry_classification='Government',
             issuer='Treasury', bond_convexity=3.45,
             remaining_maturity=1.7, city_investment_bond='否', province=None,
             bond_rating='AAA', basis_point_value=0.0165),
    ]
    for p in positions:
        db.session.add(BondFundPosition(pos_date=DEMO_DATE, **p))
    print(f'Created {len(positions)} bond fund positions')


def _seed_money_market_positions():
    if MoneyMarketFundPosition.query.first():
        return
    positions = [
        dict(product_code='MMF001', fund_name='Beta Money Market Fund',
             security_short_code='DR001', security_name='Interbank Deposit 1D',
             asset_type='SPT_NGD', market_type='Interbank',
             security_full_code='DR001.IB',
             market_value=150000000, quantity=150000000, cost=150000000,
             accrued_interest=12500, yield_7d=0.0185, portfolio_maturity=45.2,
             shadow_price_deviation=0.0012, shadow_price_deviation_amount=180000,
             fund_nav=800000000, fund_total_asset=850000000,
             end_date=date(2025, 3, 15)),
        dict(product_code='MMF001', fund_name='Beta Money Market Fund',
             security_short_code='240003', security_name='Treasury 2024-03',
             asset_type='SPT_BD', market_type='Exchange',
             security_full_code='240003.IB',
             market_value=200000000, quantity=2000000, cost=199500000,
             accrued_interest=85000, yield_7d=0.0185, portfolio_maturity=45.2,
             shadow_price_deviation=0.0012, shadow_price_deviation_amount=180000,
             fund_nav=800000000, fund_total_asset=850000000,
             end_date=date(2026, 12, 1)),
        dict(product_code='MMF001', fund_name='Beta Money Market Fund',
             security_short_code='CD001', security_name='Sample Bank CD 90D',
             asset_type='SPT_BD', market_type='Interbank',
             security_full_code='CD001.IB',
             market_value=300000000, quantity=300000000, cost=298500000,
             accrued_interest=450000, yield_7d=0.0185, portfolio_maturity=45.2,
             shadow_price_deviation=0.0012, shadow_price_deviation_amount=180000,
             fund_nav=800000000, fund_total_asset=850000000,
             end_date=date(2025, 6, 15)),
    ]
    for p in positions:
        db.session.add(MoneyMarketFundPosition(position_date=DEMO_DATE, **p))
    print(f'Created {len(positions)} money market positions')


def _seed_fixed_income_plus_positions():
    if FixedIncomePlusFundPosition.query.first():
        return
    positions = [
        dict(product_code='FIP001', fund_name='Gamma Fixed Income Plus Fund',
             security_short_code='240001', security_name='CDB Bond 2024-01',
             asset_type='SPT_BD', market_type='Interbank',
             security_full_code='240001.IB',
             market_value=45000000, security_quantity=450000, cost=44800000,
             accrued_interest=150000, fund_nav=420000000, fund_total_asset=550000000,
             mirs_indicator=5, implied_rating='AAA', stmirs_text='5/5',
             bond_duration=2.85, bond_type='政策银行债',
             bond_classification='利率债',
             industry_classification='Finance', issuer='Sample Development Bank',
             remaining_maturity=2.5, municipal_bond_flag='否'),
        dict(product_code='FIP001', fund_name='Gamma Fixed Income Plus Fund',
             security_short_code='113050', security_name='Sample Tech CB',
             asset_type='SPT_CB', market_type='Exchange',
             security_full_code='113050.SH',
             market_value=18000000, security_quantity=180000, cost=17200000,
             accrued_interest=35000, fund_nav=420000000, fund_total_asset=550000000,
             mirs_indicator=4, implied_rating='AA', stmirs_text='4/5',
             bond_duration=3.2, pure_bond_premium=15.2, conversion_premium=28.5,
             bond_type='可转债', bond_classification='可转债',
             industry_classification='Technology', issuer='Sample Tech Inc.',
             remaining_maturity=3.5, municipal_bond_flag='否'),
        dict(product_code='FIP001', fund_name='Gamma Fixed Income Plus Fund',
             security_short_code='600001', security_name='Sample Bank Stock',
             asset_type='SPT_S', market_type='Exchange',
             security_full_code='600001.SH',
             market_value=25000000, security_quantity=500000, cost=23000000,
             accrued_interest=0, fund_nav=420000000, fund_total_asset=550000000,
             mirs_indicator=None, implied_rating=None, stmirs_text=None,
             bond_duration=None, stock_beta=1.05, stock_volatility=22.5,
             bond_type=None, bond_classification=None,
             industry_classification='Banking', issuer=None,
             remaining_maturity=None, municipal_bond_flag=None),
    ]
    for p in positions:
        db.session.add(FixedIncomePlusFundPosition(position_date=DEMO_DATE, **p))
    print(f'Created {len(positions)} fixed income plus positions')


def _seed_investor_data():
    if InvestorPosition.query.first():
        return

    investors = [
        ('ACC001', 'Alpha Capital Management', 'Institution', 'Direct', 'Alpha Bond Fund A',
         50000000, 51250000),
        ('ACC002', 'Beta Insurance Co.', 'Insurance', 'Direct', 'Alpha Bond Fund A',
         120000000, 123600000),
        ('ACC003', 'Individual Investor A', 'Individual', 'Bank Channel', 'Alpha Bond Fund A',
         500000, 512500),
        ('ACC004', 'Gamma Trust Product #1', 'Trust Product', 'Direct', 'Alpha Bond Fund A',
         80000000, 82400000),
        ('ACC005', 'Delta Bank Wealth Mgmt', 'Bank Product', 'Direct', 'Alpha Bond Fund A',
         200000000, 206000000),
        ('ACC006', 'Individual Investor B', 'Individual', 'Bank Channel', 'Alpha Bond Fund A',
         150000, 153750),
        ('ACC007', 'Epsilon Finance Corp', 'Finance Company', 'Direct', 'Beta Money Market Fund',
         300000000, 300000000),
        ('ACC008', 'Alpha Capital Management', 'Institution', 'Direct', 'Beta Money Market Fund',
         100000000, 100000000),
        ('ACC009', 'Individual Investor C', 'Individual', 'Online', 'Gamma Fixed Income Plus Fund',
         250000, 257500),
        ('ACC010', 'Zeta Insurance Product', 'Insurance Product', 'Direct', 'Gamma Fixed Income Plus Fund',
         60000000, 61800000),
    ]

    for acc, name, itype, channel, fund, shares, amount in investors:
        db.session.add(InvestorPosition(
            account=acc, investor_name=name, investor_type=itype,
            channel=channel, fund_name=fund,
            position_shares=shares, position_amount=amount,
            position_date=DEMO_DATE,
        ))

    transactions = [
        ('ACC001', 'Alpha Capital Management', 'Institution', 'Direct', 'Subscription',
         'Alpha Bond Fund A', 10000000, 10000000, date(2025, 3, 10)),
        ('ACC003', 'Individual Investor A', 'Individual', 'Bank Channel', 'Redemption',
         'Alpha Bond Fund A', 100000, 102500, date(2025, 3, 12)),
        ('ACC005', 'Delta Bank Wealth Mgmt', 'Bank Product', 'Direct', 'Subscription',
         'Alpha Bond Fund A', 50000000, 50000000, date(2025, 3, 13)),
        ('ACC007', 'Epsilon Finance Corp', 'Finance Company', 'Direct', 'Redemption',
         'Beta Money Market Fund', 50000000, 50000000, date(2025, 3, 11)),
        ('ACC009', 'Individual Investor C', 'Individual', 'Online', 'Subscription',
         'Gamma Fixed Income Plus Fund', 50000, 50000, date(2025, 3, 14)),
    ]

    for acc, name, itype, channel, txtype, fund, shares, amount, txdate in transactions:
        db.session.add(InvestorTransaction(
            account=acc, investor_name=name, investor_type=itype,
            channel=channel, transaction_type=txtype, fund_name=fund,
            transaction_shares=shares, transaction_amount=amount,
            transaction_date=txdate,
        ))
    # Add earlier date positions for position change analysis
    date2 = date(2025, 3, 7)
    earlier_positions = [
        ('ACC001', 'Alpha Capital Management', 'Institution', 'Direct', 'Alpha Bond Fund A',
         40000000, 41000000),
        ('ACC002', 'Beta Insurance Co.', 'Insurance', 'Direct', 'Alpha Bond Fund A',
         120000000, 123600000),
        ('ACC004', 'Gamma Trust Product #1', 'Trust Product', 'Direct', 'Alpha Bond Fund A',
         80000000, 82400000),
        ('ACC005', 'Delta Bank Wealth Mgmt', 'Bank Product', 'Direct', 'Alpha Bond Fund A',
         150000000, 154500000),
        ('ACC007', 'Epsilon Finance Corp', 'Finance Company', 'Direct', 'Beta Money Market Fund',
         350000000, 350000000),
        ('ACC008', 'Alpha Capital Management', 'Institution', 'Direct', 'Beta Money Market Fund',
         100000000, 100000000),
        ('ACC010', 'Zeta Insurance Product', 'Insurance Product', 'Direct', 'Gamma Fixed Income Plus Fund',
         45000000, 46350000),
    ]
    for acc, name, itype, channel, fund, shares, amount in earlier_positions:
        db.session.add(InvestorPosition(
            account=acc, investor_name=name, investor_type=itype,
            channel=channel, fund_name=fund,
            position_shares=shares, position_amount=amount,
            position_date=date2,
        ))

    print(f'Created {len(investors) + len(earlier_positions)} investor positions, {len(transactions)} transactions')


def _seed_warning_records():
    if BondLiquidityWarning.query.first():
        return

    # Alpha Bond Fund A — has 2 warnings (AA ratio exceeded, real estate exceeded)
    db.session.add(BondLiquidityWarning(
        fund_name='Alpha Bond Fund A', monitor_date=DEMO_DATE,
        indicator1_value=0.25, indicator1_threshold=0.10, indicator1_status='Normal',
        indicator2_value=0.35, indicator2_threshold=0.30, indicator2_status='Warning',
        indicator3_value=0.05, indicator3_threshold=0.10, indicator3_status='Normal',
        indicator4_value=0.03, indicator4_threshold=0.05, indicator4_status='Normal',
        indicator5_value=1.31, indicator5_threshold=1.40, indicator5_status='Normal',
        indicator6_value=0.12, indicator6_threshold=0.10, indicator6_status='Warning',
    ))

    # Beta Money Market Fund — has 1 warning (leverage exceeded)
    db.session.add(MoneyMarketLiquidityWarning(
        fund_name='Beta Money Market Fund', monitor_date=DEMO_DATE,
        indicator1_value=0.18, indicator1_threshold=0.10, indicator1_status='Normal',
        indicator2_value=0.0015, indicator2_threshold=0.0025, indicator2_status='Normal',
        indicator3_value=0.0012, indicator3_threshold=0.0025, indicator3_status='Normal',
        indicator4_value=1.25, indicator4_threshold=1.20, indicator4_status='Warning',
    ))

    # Gamma Fixed Income Plus Fund — has 1 warning (equity securities ratio exceeded)
    db.session.add(FixedIncomePlusLiquidityWarning(
        fund_name='Gamma Fixed Income Plus Fund', monitor_date=DEMO_DATE,
        indicator1_value=0.22, indicator1_threshold=0.10, indicator1_status='Normal',
        indicator2_value=0.08, indicator2_threshold=0.30, indicator2_status='Normal',
        indicator3_value=0.03, indicator3_threshold=0.10, indicator3_status='Normal',
        indicator4_value=0.02, indicator4_threshold=0.05, indicator4_status='Normal',
        indicator5_value=0.01, indicator5_threshold=0.10, indicator5_status='Normal',
        indicator6_value=1.28, indicator6_threshold=1.40, indicator6_status='Normal',
        indicator7_value=0.35, indicator7_threshold=0.30, indicator7_status='Warning',
    ))

    # Add a second date for historical depth
    date2 = date(2025, 3, 7)

    db.session.add(BondLiquidityWarning(
        fund_name='Alpha Bond Fund A', monitor_date=date2,
        indicator1_value=0.23, indicator1_threshold=0.10, indicator1_status='Normal',
        indicator2_value=0.28, indicator2_threshold=0.30, indicator2_status='Normal',
        indicator3_value=0.04, indicator3_threshold=0.10, indicator3_status='Normal',
        indicator4_value=0.03, indicator4_threshold=0.05, indicator4_status='Normal',
        indicator5_value=1.35, indicator5_threshold=1.40, indicator5_status='Normal',
        indicator6_value=0.09, indicator6_threshold=0.10, indicator6_status='Normal',
    ))

    print('Created liquidity warning records (3 funds, 2 dates, with warnings)')


def _seed_result_cache():
    if BondBasicInfoResult.query.first():
        return

    db.session.add(BondBasicInfoResult(
        fund_name='Alpha Bond Fund A', query_date=DEMO_DATE,
        net_asset_billion=5.20, leverage_ratio=1.31, static_yield=2.68,
        duration_before_leverage=2.45, duration_after_leverage=3.21,
        portfolio_convexity=12.35, bpv_10000=1.67,
        maturity_under_1yr_ratio=0.15, maturity_1to3yr_ratio=0.45,
        maturity_3to5yr_ratio=0.30, maturity_over_5yr_ratio=0.10,
        lqi_score=0.82,
        liquidity_s_ratio=0.25, liquidity_a_ratio=0.35,
        liquidity_b_ratio=0.20, liquidity_c_ratio=0.15, liquidity_d_ratio=0.05,
    ))

    db.session.add(BondWarningIndicatorResult(
        fund_name='Alpha Bond Fund A', query_date=DEMO_DATE,
        indicator1_high_liquidity=0.25, indicator2_aa_below_ratio=0.15,
        indicator3_aa2_below_ratio=0.05, indicator4_low_rating_max_ratio=0.03,
        indicator5_leverage=1.31, indicator6_real_estate_ratio=0.02,
        indicator1_status='Normal', indicator2_status='Normal',
        indicator3_status='Normal', indicator4_status='Normal',
        indicator5_status='Normal', indicator6_status='Normal',
    ))

    db.session.add(MoneyMarketBasicInfoResult(
        fund_name='Beta Money Market Fund', query_date=DEMO_DATE,
        net_asset_billion=8.0, portfolio_days=45.2,
        yield_7d='1.85%', asset_14days_billion=1.5,
    ))

    db.session.add(MoneyMarketWarningIndicatorResult(
        fund_name='Beta Money Market Fund', query_date=DEMO_DATE,
        indicator1_value=0.18, indicator2_value=0.0015,
        indicator3_value=0.0012, indicator4_value=1.06,
        indicator1_status='Normal', indicator2_status='Normal',
        indicator3_status='Normal', indicator4_status='Normal',
    ))

    db.session.add(FixedIncomePlusBasicInfoResult(
        fund_name='Gamma Fixed Income Plus Fund', query_date=DEMO_DATE,
        net_asset_billion=4.20, bond_ratio=0.55, convertible_bond_ratio=0.08,
        stock_ratio=0.12, demand_deposit_ratio=0.05, repo_ratio=0.10,
        stock_volatility=22.5, stock_beta=1.05,
        pure_bond_premium_avg=15.2, equity_premium_avg=28.5,
        portfolio_duration=2.65,
    ))

    db.session.add(FixedIncomePlusWarningIndicatorResult(
        fund_name='Gamma Fixed Income Plus Fund', query_date=DEMO_DATE,
        indicator1_high_liquidity=0.22, indicator2_aa_below_ratio=0.08,
        indicator3_aa2_below_ratio=0.03, indicator4_low_rating_max_ratio=0.02,
        indicator5_real_estate_ratio=0.01, indicator6_leverage=1.28,
        indicator7_equity_securities_ratio=0.18,
        indicator1_status='Normal', indicator2_status='Normal',
        indicator3_status='Normal', indicator4_status='Normal',
        indicator5_status='Normal', indicator6_status='Normal',
        indicator7_status='Normal',
    ))
    print('Created calculation result cache for all fund types')


def _seed_structure_analysis():
    if FundStructureAnalysis.query.first():
        return

    db.session.add(FundStructureAnalysis(
        fund_name='Alpha Bond Fund A', analysis_date=DEMO_DATE,
        high_amount_individual_count=3, high_amount_individual_amount=1500000,
        high_amount_individual_ratio=0.003,
        low_amount_individual_count=25, low_amount_individual_amount=650000,
        low_amount_individual_ratio=0.001,
        insurance_product_count=2, insurance_product_amount=120000000,
        insurance_product_ratio=0.231,
        trust_product_count=1, trust_product_amount=80000000,
        trust_product_ratio=0.154,
        bank_product_count=3, bank_product_amount=200000000,
        bank_product_ratio=0.385,
        other_product_count=1, other_product_amount=30000000,
        other_product_ratio=0.058,
        bank_institution_count=2, bank_institution_amount=50000000,
        bank_institution_ratio=0.096,
        insurance_institution_count=1, insurance_institution_amount=25000000,
        insurance_institution_ratio=0.048,
        finance_institution_count=0, finance_institution_amount=0,
        finance_institution_ratio=0,
        other_institution_count=1, other_institution_amount=12000000,
        other_institution_ratio=0.023,
        total_amount=519150000, total_count=39,
    ))
    print('Created holder structure analysis sample')


if __name__ == '__main__':
    seed()
