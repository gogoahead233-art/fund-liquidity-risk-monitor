from datetime import datetime
from flask_login import UserMixin
from app import db


# ── Authentication & Authorization ──────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserPermission(db.Model):
    __tablename__ = 'user_permissions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    fund_name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('permissions', lazy=True))


# ── System Configuration ────────────────────────────────────────────────────

class SmtpConfig(db.Model):
    __tablename__ = 'smtp_config'

    id = db.Column(db.Integer, primary_key=True)
    smtp_server = db.Column(db.String(200), nullable=False)
    smtp_port = db.Column(db.Integer, nullable=False, default=465)
    sender_email = db.Column(db.String(200), nullable=False)
    auth_token = db.Column(db.LargeBinary, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FundEmailConfig(db.Model):
    __tablename__ = 'fund_email_configs'

    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(200), nullable=False, unique=True)
    email_address = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WarningThreshold(db.Model):
    __tablename__ = 'warning_thresholds'

    id = db.Column(db.Integer, primary_key=True)
    indicator_name = db.Column(db.String(100), nullable=False, unique=True)
    threshold_value = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Operation Logs ──────────────────────────────────────────────────────────

class OperationLog(db.Model):
    __tablename__ = 'operation_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    operation_type = db.Column(db.String(50), nullable=False)
    operation_detail = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('logs', lazy=True))


# ── Investor Data ───────────────────────────────────────────────────────────

class InvestorPosition(db.Model):
    __tablename__ = 'investor_positions'

    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(50), nullable=False)
    investor_name = db.Column(db.String(100), nullable=False)
    investor_type = db.Column(db.String(50), nullable=False)
    channel = db.Column(db.String(50), nullable=False)
    fund_name = db.Column(db.String(200), nullable=False)
    position_shares = db.Column(db.Float, nullable=False)
    position_amount = db.Column(db.Float, nullable=False)
    position_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class InvestorTransaction(db.Model):
    __tablename__ = 'investor_transactions'

    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(50), nullable=False)
    investor_name = db.Column(db.String(100), nullable=False)
    investor_type = db.Column(db.String(50), nullable=False)
    channel = db.Column(db.String(50), nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)
    fund_name = db.Column(db.String(200), nullable=False)
    transaction_shares = db.Column(db.Float, nullable=False)
    transaction_amount = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ── Fund Portfolio Positions ────────────────────────────────────────────────

class BondFundPosition(db.Model):
    __tablename__ = 'bond_fund_positions'

    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(200), nullable=False)
    pos_date = db.Column(db.Date, nullable=False)
    security_name = db.Column(db.String(200), nullable=True)
    security_code = db.Column(db.String(50), nullable=True)
    asset_type = db.Column(db.String(50), nullable=True)
    market_type = db.Column(db.String(50), nullable=True)
    market_value = db.Column(db.Float, nullable=True)
    security_quantity = db.Column(db.Float, nullable=True)
    accrued_interest = db.Column(db.Float, nullable=True)
    fund_nav = db.Column(db.Float, nullable=True)
    fund_total_asset = db.Column(db.Float, nullable=True)
    lqi_indicator = db.Column(db.Float, nullable=True)
    mirs_indicator = db.Column(db.Float, nullable=True)
    implied_rating = db.Column(db.String(50), nullable=True)
    stmirs_text = db.Column(db.String(20), nullable=True)
    bond_type = db.Column(db.String(100), nullable=True)
    valuation_yield = db.Column(db.Float, nullable=True)
    bond_duration = db.Column(db.Float, nullable=True)
    wind_implied_rating = db.Column(db.String(50), nullable=True)
    industry_classification = db.Column(db.String(100), nullable=True)
    issuer = db.Column(db.String(200), nullable=True)
    bond_convexity = db.Column(db.Float, nullable=True)
    remaining_maturity = db.Column(db.Float, nullable=True)
    city_investment_bond = db.Column(db.String(10), nullable=True)
    province = db.Column(db.String(50), nullable=True)
    bond_rating = db.Column(db.String(50), nullable=True)
    basis_point_value = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MoneyMarketFundPosition(db.Model):
    __tablename__ = 'money_market_fund_positions'

    id = db.Column(db.Integer, primary_key=True)
    product_code = db.Column(db.String(50), nullable=False)
    fund_name = db.Column(db.String(200), nullable=False)
    position_date = db.Column(db.Date, nullable=False)
    security_short_code = db.Column(db.String(50), nullable=True)
    security_name = db.Column(db.String(200), nullable=True)
    asset_type = db.Column(db.String(50), nullable=True)
    market_type = db.Column(db.String(50), nullable=True)
    security_full_code = db.Column(db.String(50), nullable=True)
    market_value = db.Column(db.Float, nullable=True)
    quantity = db.Column(db.Float, nullable=True)
    cost = db.Column(db.Float, nullable=True)
    accrued_interest = db.Column(db.Float, nullable=True)
    yield_7d = db.Column(db.Float, nullable=True)
    portfolio_maturity = db.Column(db.Float, nullable=True)
    shadow_price_deviation = db.Column(db.Float, nullable=True)
    shadow_price_deviation_amount = db.Column(db.Float, nullable=True)
    fund_nav = db.Column(db.Float, nullable=True)
    fund_total_asset = db.Column(db.Float, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FixedIncomePlusFundPosition(db.Model):
    __tablename__ = 'fixed_income_plus_fund_positions'

    id = db.Column(db.Integer, primary_key=True)
    product_code = db.Column(db.String(50), nullable=False)
    fund_name = db.Column(db.String(200), nullable=False)
    position_date = db.Column(db.Date, nullable=False)
    security_short_code = db.Column(db.String(50), nullable=True)
    security_name = db.Column(db.String(200), nullable=True)
    asset_type = db.Column(db.String(50), nullable=True)
    market_type = db.Column(db.String(50), nullable=True)
    security_full_code = db.Column(db.String(50), nullable=True)
    market_value = db.Column(db.Float, nullable=True)
    security_quantity = db.Column(db.Float, nullable=True)
    cost = db.Column(db.Float, nullable=True)
    accrued_interest = db.Column(db.Float, nullable=True)
    fund_nav = db.Column(db.Float, nullable=True)
    fund_total_asset = db.Column(db.Float, nullable=True)
    mirs_indicator = db.Column(db.Float, nullable=True)
    implied_rating = db.Column(db.String(50), nullable=True)
    stmirs_text = db.Column(db.String(20), nullable=True)
    bond_duration = db.Column(db.Float, nullable=True)
    pure_bond_premium = db.Column(db.Float, nullable=True)
    conversion_premium = db.Column(db.Float, nullable=True)
    stock_beta = db.Column(db.Float, nullable=True)
    stock_volatility = db.Column(db.Float, nullable=True)
    bond_type = db.Column(db.String(50), nullable=True)
    bond_classification = db.Column(db.String(50), nullable=True)
    industry_classification = db.Column(db.String(100), nullable=True)
    issuer = db.Column(db.String(200), nullable=True)
    remaining_maturity = db.Column(db.Float, nullable=True)
    municipal_bond_flag = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ── Liquidity Risk Warning Records ─────────────────────────────────────────

class BondLiquidityWarning(db.Model):
    __tablename__ = 'bond_liquidity_warnings'

    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(200), nullable=False)
    monitor_date = db.Column(db.Date, nullable=False)
    indicator1_value = db.Column(db.Float, nullable=True)
    indicator1_threshold = db.Column(db.Float, nullable=True)
    indicator1_status = db.Column(db.String(20), nullable=True)
    indicator2_value = db.Column(db.Float, nullable=True)
    indicator2_threshold = db.Column(db.Float, nullable=True)
    indicator2_status = db.Column(db.String(20), nullable=True)
    indicator3_value = db.Column(db.Float, nullable=True)
    indicator3_threshold = db.Column(db.Float, nullable=True)
    indicator3_status = db.Column(db.String(20), nullable=True)
    indicator4_value = db.Column(db.Float, nullable=True)
    indicator4_threshold = db.Column(db.Float, nullable=True)
    indicator4_status = db.Column(db.String(20), nullable=True)
    indicator5_value = db.Column(db.Float, nullable=True)
    indicator5_threshold = db.Column(db.Float, nullable=True)
    indicator5_status = db.Column(db.String(20), nullable=True)
    indicator6_value = db.Column(db.Float, nullable=True)
    indicator6_threshold = db.Column(db.Float, nullable=True)
    indicator6_status = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MoneyMarketLiquidityWarning(db.Model):
    __tablename__ = 'money_market_liquidity_warnings'

    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(200), nullable=False)
    monitor_date = db.Column(db.Date, nullable=False)
    indicator1_value = db.Column(db.Float, nullable=True)
    indicator1_threshold = db.Column(db.Float, nullable=True)
    indicator1_status = db.Column(db.String(20), nullable=True)
    indicator2_value = db.Column(db.Float, nullable=True)
    indicator2_threshold = db.Column(db.Float, nullable=True)
    indicator2_status = db.Column(db.String(20), nullable=True)
    indicator3_value = db.Column(db.Float, nullable=True)
    indicator3_threshold = db.Column(db.Float, nullable=True)
    indicator3_status = db.Column(db.String(20), nullable=True)
    indicator4_value = db.Column(db.Float, nullable=True)
    indicator4_threshold = db.Column(db.Float, nullable=True)
    indicator4_status = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FixedIncomePlusLiquidityWarning(db.Model):
    __tablename__ = 'fixed_income_plus_liquidity_warnings'

    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(200), nullable=False)
    monitor_date = db.Column(db.Date, nullable=False)
    indicator1_value = db.Column(db.Float, nullable=True)
    indicator1_threshold = db.Column(db.Float, nullable=True)
    indicator1_status = db.Column(db.String(20), nullable=True)
    indicator2_value = db.Column(db.Float, nullable=True)
    indicator2_threshold = db.Column(db.Float, nullable=True)
    indicator2_status = db.Column(db.String(20), nullable=True)
    indicator3_value = db.Column(db.Float, nullable=True)
    indicator3_threshold = db.Column(db.Float, nullable=True)
    indicator3_status = db.Column(db.String(20), nullable=True)
    indicator4_value = db.Column(db.Float, nullable=True)
    indicator4_threshold = db.Column(db.Float, nullable=True)
    indicator4_status = db.Column(db.String(20), nullable=True)
    indicator5_value = db.Column(db.Float, nullable=True)
    indicator5_threshold = db.Column(db.Float, nullable=True)
    indicator5_status = db.Column(db.String(20), nullable=True)
    indicator6_value = db.Column(db.Float, nullable=True)
    indicator6_threshold = db.Column(db.Float, nullable=True)
    indicator6_status = db.Column(db.String(20), nullable=True)
    indicator7_value = db.Column(db.Float, nullable=True)
    indicator7_threshold = db.Column(db.Float, nullable=True)
    indicator7_status = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ── Calculation Result Cache ────────────────────────────────────────────────

class BondBasicInfoResult(db.Model):
    __tablename__ = 'bond_basic_info_results'

    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(200), nullable=False, index=True)
    query_date = db.Column(db.Date, nullable=False, index=True)
    net_asset_billion = db.Column(db.Float, nullable=True)
    leverage_ratio = db.Column(db.Float, nullable=True)
    static_yield = db.Column(db.Float, nullable=True)
    duration_before_leverage = db.Column(db.Float, nullable=True)
    duration_after_leverage = db.Column(db.Float, nullable=True)
    portfolio_convexity = db.Column(db.Float, nullable=True)
    bpv_10000 = db.Column(db.Float, nullable=True)
    maturity_under_1yr_ratio = db.Column(db.Float, nullable=True)
    maturity_1to3yr_ratio = db.Column(db.Float, nullable=True)
    maturity_3to5yr_ratio = db.Column(db.Float, nullable=True)
    maturity_over_5yr_ratio = db.Column(db.Float, nullable=True)
    lqi_score = db.Column(db.Float, nullable=True)
    liquidity_s_ratio = db.Column(db.Float, nullable=True)
    liquidity_a_ratio = db.Column(db.Float, nullable=True)
    liquidity_b_ratio = db.Column(db.Float, nullable=True)
    liquidity_c_ratio = db.Column(db.Float, nullable=True)
    liquidity_d_ratio = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BondWarningIndicatorResult(db.Model):
    __tablename__ = 'bond_warning_indicator_results'

    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(200), nullable=False, index=True)
    query_date = db.Column(db.Date, nullable=False, index=True)
    indicator1_high_liquidity = db.Column(db.Float, nullable=True)
    indicator2_aa_below_ratio = db.Column(db.Float, nullable=True)
    indicator3_aa2_below_ratio = db.Column(db.Float, nullable=True)
    indicator4_low_rating_max_ratio = db.Column(db.Float, nullable=True)
    indicator5_leverage = db.Column(db.Float, nullable=True)
    indicator6_real_estate_ratio = db.Column(db.Float, nullable=True)
    indicator1_status = db.Column(db.String(20), nullable=True)
    indicator2_status = db.Column(db.String(20), nullable=True)
    indicator3_status = db.Column(db.String(20), nullable=True)
    indicator4_status = db.Column(db.String(20), nullable=True)
    indicator5_status = db.Column(db.String(20), nullable=True)
    indicator6_status = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MoneyMarketBasicInfoResult(db.Model):
    __tablename__ = 'money_market_basic_info_results'

    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(200), nullable=False, index=True)
    query_date = db.Column(db.Date, nullable=False, index=True)
    net_asset_billion = db.Column(db.Float, nullable=True)
    portfolio_days = db.Column(db.Float, nullable=True)
    yield_7d = db.Column(db.String(20), nullable=True)
    asset_14days_billion = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MoneyMarketWarningIndicatorResult(db.Model):
    __tablename__ = 'money_market_warning_indicator_results'

    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(200), nullable=False, index=True)
    query_date = db.Column(db.Date, nullable=False, index=True)
    indicator1_value = db.Column(db.Float, nullable=True)
    indicator2_value = db.Column(db.Float, nullable=True)
    indicator3_value = db.Column(db.Float, nullable=True)
    indicator4_value = db.Column(db.Float, nullable=True)
    indicator1_status = db.Column(db.String(20), nullable=True)
    indicator2_status = db.Column(db.String(20), nullable=True)
    indicator3_status = db.Column(db.String(20), nullable=True)
    indicator4_status = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FixedIncomePlusBasicInfoResult(db.Model):
    __tablename__ = 'fixed_income_plus_basic_info_results'

    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(200), nullable=False, index=True)
    query_date = db.Column(db.Date, nullable=False, index=True)
    net_asset_billion = db.Column(db.Float, nullable=True)
    bond_ratio = db.Column(db.Float, nullable=True)
    convertible_bond_ratio = db.Column(db.Float, nullable=True)
    stock_ratio = db.Column(db.Float, nullable=True)
    demand_deposit_ratio = db.Column(db.Float, nullable=True)
    repo_ratio = db.Column(db.Float, nullable=True)
    stock_volatility = db.Column(db.Float, nullable=True)
    stock_beta = db.Column(db.Float, nullable=True)
    pure_bond_premium_avg = db.Column(db.Float, nullable=True)
    equity_premium_avg = db.Column(db.Float, nullable=True)
    portfolio_duration = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FixedIncomePlusWarningIndicatorResult(db.Model):
    __tablename__ = 'fixed_income_plus_warning_indicator_results'

    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(200), nullable=False, index=True)
    query_date = db.Column(db.Date, nullable=False, index=True)
    indicator1_high_liquidity = db.Column(db.Float, nullable=True)
    indicator2_aa_below_ratio = db.Column(db.Float, nullable=True)
    indicator3_aa2_below_ratio = db.Column(db.Float, nullable=True)
    indicator4_low_rating_max_ratio = db.Column(db.Float, nullable=True)
    indicator5_real_estate_ratio = db.Column(db.Float, nullable=True)
    indicator6_leverage = db.Column(db.Float, nullable=True)
    indicator7_equity_securities_ratio = db.Column(db.Float, nullable=True)
    indicator1_status = db.Column(db.String(20), nullable=True)
    indicator2_status = db.Column(db.String(20), nullable=True)
    indicator3_status = db.Column(db.String(20), nullable=True)
    indicator4_status = db.Column(db.String(20), nullable=True)
    indicator5_status = db.Column(db.String(20), nullable=True)
    indicator6_status = db.Column(db.String(20), nullable=True)
    indicator7_status = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Holder Structure & Redemption Analysis ──────────────────────────────────

class FundStructureAnalysis(db.Model):
    __tablename__ = 'fund_structure_analysis'

    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(200), nullable=False)
    analysis_date = db.Column(db.Date, nullable=False)

    high_amount_individual_count = db.Column(db.Integer, default=0)
    high_amount_individual_amount = db.Column(db.Float, default=0.0)
    high_amount_individual_ratio = db.Column(db.Float, default=0.0)

    low_amount_individual_count = db.Column(db.Integer, default=0)
    low_amount_individual_amount = db.Column(db.Float, default=0.0)
    low_amount_individual_ratio = db.Column(db.Float, default=0.0)

    insurance_product_count = db.Column(db.Integer, default=0)
    insurance_product_amount = db.Column(db.Float, default=0.0)
    insurance_product_ratio = db.Column(db.Float, default=0.0)

    trust_product_count = db.Column(db.Integer, default=0)
    trust_product_amount = db.Column(db.Float, default=0.0)
    trust_product_ratio = db.Column(db.Float, default=0.0)

    bank_product_count = db.Column(db.Integer, default=0)
    bank_product_amount = db.Column(db.Float, default=0.0)
    bank_product_ratio = db.Column(db.Float, default=0.0)

    other_product_count = db.Column(db.Integer, default=0)
    other_product_amount = db.Column(db.Float, default=0.0)
    other_product_ratio = db.Column(db.Float, default=0.0)

    bank_institution_count = db.Column(db.Integer, default=0)
    bank_institution_amount = db.Column(db.Float, default=0.0)
    bank_institution_ratio = db.Column(db.Float, default=0.0)

    insurance_institution_count = db.Column(db.Integer, default=0)
    insurance_institution_amount = db.Column(db.Float, default=0.0)
    insurance_institution_ratio = db.Column(db.Float, default=0.0)

    finance_institution_count = db.Column(db.Integer, default=0)
    finance_institution_amount = db.Column(db.Float, default=0.0)
    finance_institution_ratio = db.Column(db.Float, default=0.0)

    other_institution_count = db.Column(db.Integer, default=0)
    other_institution_amount = db.Column(db.Float, default=0.0)
    other_institution_ratio = db.Column(db.Float, default=0.0)

    total_amount = db.Column(db.Float, default=0.0)
    total_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FundRedemptionAnalysis(db.Model):
    __tablename__ = 'fund_redemption_analysis'

    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(200), nullable=False)
    analysis_date = db.Column(db.Date, nullable=False)
    expected_redemption_ratio = db.Column(db.Float, default=0.0)
    high_amount_individual_redemption_ratio = db.Column(db.Float, default=0.5)
    low_amount_individual_redemption_ratio = db.Column(db.Float, default=0.3)
    insurance_product_redemption_ratio = db.Column(db.Float, default=0.3)
    trust_product_redemption_ratio = db.Column(db.Float, default=0.7)
    bank_product_redemption_ratio = db.Column(db.Float, default=0.7)
    other_product_redemption_ratio = db.Column(db.Float, default=0.7)
    bank_institution_redemption_ratio = db.Column(db.Float, default=0.3)
    insurance_institution_redemption_ratio = db.Column(db.Float, default=0.3)
    finance_institution_redemption_ratio = db.Column(db.Float, default=0.3)
    other_institution_redemption_ratio = db.Column(db.Float, default=0.5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FundRedemptionConfig(db.Model):
    __tablename__ = 'fund_redemption_config'

    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(100), nullable=False, unique=True)
    high_amount_individual_redemption_ratio = db.Column(db.Float, default=0.5)
    low_amount_individual_redemption_ratio = db.Column(db.Float, default=0.3)
    insurance_product_redemption_ratio = db.Column(db.Float, default=0.3)
    trust_product_redemption_ratio = db.Column(db.Float, default=0.7)
    bank_product_redemption_ratio = db.Column(db.Float, default=0.7)
    other_product_redemption_ratio = db.Column(db.Float, default=0.7)
    bank_institution_redemption_ratio = db.Column(db.Float, default=0.3)
    insurance_institution_redemption_ratio = db.Column(db.Float, default=0.3)
    finance_institution_redemption_ratio = db.Column(db.Float, default=0.3)
    other_institution_redemption_ratio = db.Column(db.Float, default=0.5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
