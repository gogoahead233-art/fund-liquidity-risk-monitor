import logging
from datetime import datetime

import pandas as pd
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.warning import bp
from app import db, data_provider
from app.models import (
    BondFundPosition, MoneyMarketFundPosition, FixedIncomePlusFundPosition,
    BondBasicInfoResult, BondWarningIndicatorResult,
    MoneyMarketBasicInfoResult, MoneyMarketWarningIndicatorResult,
    FixedIncomePlusBasicInfoResult, FixedIncomePlusWarningIndicatorResult,
    BondLiquidityWarning, MoneyMarketLiquidityWarning,
    FixedIncomePlusLiquidityWarning, WarningThreshold,
    UserPermission,
)

logger = logging.getLogger(__name__)


def _get_fund_names_by_type(fund_type):
    """Get distinct fund names for a given fund type."""
    if fund_type == 'bond':
        return sorted({r[0] for r in db.session.query(BondFundPosition.fund_name).distinct().all()})
    elif fund_type == 'money_market':
        return sorted({r[0] for r in db.session.query(MoneyMarketFundPosition.fund_name).distinct().all()})
    elif fund_type == 'fixed_income_plus':
        return sorted({r[0] for r in db.session.query(FixedIncomePlusFundPosition.fund_name).distinct().all()})
    return []


def _get_dates_by_type(fund_type, fund_name=None):
    """Get distinct available dates for a given fund type, optionally filtered by fund name."""
    if fund_type == 'bond':
        q = db.session.query(BondFundPosition.pos_date)
        if fund_name:
            q = q.filter(BondFundPosition.fund_name == fund_name)
        rows = q.distinct().order_by(BondFundPosition.pos_date.desc()).all()
    elif fund_type == 'money_market':
        q = db.session.query(MoneyMarketFundPosition.position_date)
        if fund_name:
            q = q.filter(MoneyMarketFundPosition.fund_name == fund_name)
        rows = q.distinct().order_by(MoneyMarketFundPosition.position_date.desc()).all()
    elif fund_type == 'fixed_income_plus':
        q = db.session.query(FixedIncomePlusFundPosition.position_date)
        if fund_name:
            q = q.filter(FixedIncomePlusFundPosition.fund_name == fund_name)
        rows = q.distinct().order_by(FixedIncomePlusFundPosition.position_date.desc()).all()
    else:
        return []
    return [r[0].strftime('%Y-%m-%d') for r in rows if r[0]]


# ── Page routes ─────────────────────────────────────────────────────────────

@bp.route('/bond')
@login_required
def bond_basic_info():
    return render_template('warning/bond_basic_info.html')


@bp.route('/bond/indicators')
@login_required
def bond_warning_indicators():
    return render_template('warning/bond_warning_indicators.html')


@bp.route('/money_market')
@login_required
def money_market_basic_info():
    return render_template('warning/money_market_basic_info.html')


@bp.route('/money_market/indicators')
@login_required
def money_market_warning_indicators():
    return render_template('warning/money_market_warning_indicators.html')


@bp.route('/fixed_income_plus')
@login_required
def fixed_income_plus_basic_info():
    return render_template('warning/fixed_income_plus_basic_info.html')


@bp.route('/fixed_income_plus/indicators')
@login_required
def fixed_income_plus_warning_indicators():
    return render_template('warning/fixed_income_plus_warning_indicators.html')


@bp.route('/liquidity_risk')
@login_required
def liquidity_risk_warning():
    return render_template('warning/liquidity_risk_warning.html')


# ── Common API routes ───────────────────────────────────────────────────────

@bp.route('/api/fund_names')
@login_required
def api_fund_names():
    fund_type = request.args.get('type') or request.args.get('fund_type', 'bond')
    return jsonify({'success': True, 'data': _get_fund_names_by_type(fund_type)})


@bp.route('/api/dates')
@login_required
def api_dates():
    fund_type = request.args.get('type') or request.args.get('fund_type', 'bond')
    fund_name = request.args.get('fund_name')
    dates = _get_dates_by_type(fund_type, fund_name)
    return jsonify({'success': True, 'data': dates})


@bp.route('/api/query_smoke_index', methods=['POST'])
@login_required
def api_query_smoke_index():
    """Query liquidity risk warning data for one or more funds on a given date."""
    try:
        data = request.get_json()
        fund_type = data.get('fund_type', 'bond')
        fund_names = data.get('fund_name', [])
        if isinstance(fund_names, str):
            fund_names = [fund_names] if fund_names else []
        query_date = data.get('query_date')

        if not query_date:
            return jsonify({'success': False, 'message': 'query_date is required'}), 400

        # Choose model and indicator count
        model_map = {
            'bond': (BondLiquidityWarning, 6),
            'money_market': (MoneyMarketLiquidityWarning, 4),
            'fixed_income_plus': (FixedIncomePlusLiquidityWarning, 7),
        }
        Model, n_indicators = model_map.get(fund_type, (BondLiquidityWarning, 6))

        query = Model.query.filter(Model.monitor_date == query_date)
        if fund_names:
            query = query.filter(Model.fund_name.in_(fund_names))

        records = query.all()
        result = []
        for r in records:
            item = {
                'fund_name': r.fund_name,
                'monitor_date': r.monitor_date.strftime('%Y-%m-%d') if r.monitor_date else '',
                'indicator_count': n_indicators,
            }
            for i in range(1, n_indicators + 1):
                item[f'indicator{i}_value'] = getattr(r, f'indicator{i}_value', None)
                item[f'indicator{i}_threshold'] = getattr(r, f'indicator{i}_threshold', None)
                item[f'indicator{i}_status'] = getattr(r, f'indicator{i}_status', 'Normal')
            result.append(item)

        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ── Bond fund calculation APIs ──────────────────────────────────────────────

@bp.route('/api/bond/calculate', methods=['POST'])
@login_required
def api_bond_calculate():
    """Calculate bond fund basic info and warning indicators."""
    try:
        req = request.get_json()
        fund_name = req.get('fund_name')
        date_str = req.get('date')

        if not fund_name or not date_str:
            return jsonify({'success': False, 'message': 'fund_name and date are required'}), 400

        query_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Check for cached results first
        cached_basic = BondBasicInfoResult.query.filter_by(
            fund_name=fund_name, query_date=query_date).first()
        cached_warning = BondWarningIndicatorResult.query.filter_by(
            fund_name=fund_name, query_date=query_date).first()

        if cached_basic and cached_warning:
            basic = _serialize_bond_basic(cached_basic)
            warning = _serialize_bond_warning(cached_warning)
            return jsonify({'success': True, 'basic_info': basic, 'warning_indicators': warning, 'source': 'cache'})

        # Calculate fresh
        from app.calculators import BondCalculator
        calc = BondCalculator(db.session, data_provider)
        basic_df, metrics_df, index_df, tiers_df, lqi_df = calc.process_and_calculate(fund_name, query_date)

        if basic_df is None:
            return jsonify({'success': False, 'message': f'No position data found for {fund_name} on {date_str}'})

        # Save to DB
        calc.save_to_database(fund_name, query_date, basic_df, metrics_df, index_df, tiers_df, lqi_df)

        # Re-read from DB for consistent serialization
        cached_basic = BondBasicInfoResult.query.filter_by(fund_name=fund_name, query_date=query_date).first()
        cached_warning = BondWarningIndicatorResult.query.filter_by(fund_name=fund_name, query_date=query_date).first()

        basic = _serialize_bond_basic(cached_basic) if cached_basic else None
        warning = _serialize_bond_warning(cached_warning) if cached_warning else None

        return jsonify({'success': True, 'basic_info': basic, 'warning_indicators': warning, 'source': 'calculated'})

    except Exception as e:
        logger.error(f'Bond calculation error: {e}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)})


def _serialize_bond_basic(r):
    return {
        'fund_name': r.fund_name,
        'query_date': r.query_date.strftime('%Y-%m-%d') if r.query_date else '',
        'net_asset_billion': r.net_asset_billion,
        'leverage_ratio': r.leverage_ratio,
        'static_yield': r.static_yield,
        'duration_before_leverage': r.duration_before_leverage,
        'duration_after_leverage': r.duration_after_leverage,
        'portfolio_convexity': r.portfolio_convexity,
        'bpv_10000': r.bpv_10000,
        'maturity_under_1yr_ratio': r.maturity_under_1yr_ratio,
        'maturity_1to3yr_ratio': r.maturity_1to3yr_ratio,
        'maturity_3to5yr_ratio': r.maturity_3to5yr_ratio,
        'maturity_over_5yr_ratio': r.maturity_over_5yr_ratio,
        'lqi_score': r.lqi_score,
        'liquidity_s_ratio': r.liquidity_s_ratio,
        'liquidity_a_ratio': r.liquidity_a_ratio,
        'liquidity_b_ratio': r.liquidity_b_ratio,
        'liquidity_c_ratio': r.liquidity_c_ratio,
        'liquidity_d_ratio': r.liquidity_d_ratio,
    }


def _serialize_bond_warning(r):
    return {
        'fund_name': r.fund_name,
        'query_date': r.query_date.strftime('%Y-%m-%d') if r.query_date else '',
        'indicator1_high_liquidity': r.indicator1_high_liquidity,
        'indicator2_aa_below_ratio': r.indicator2_aa_below_ratio,
        'indicator3_aa2_below_ratio': r.indicator3_aa2_below_ratio,
        'indicator4_low_rating_max_ratio': r.indicator4_low_rating_max_ratio,
        'indicator5_leverage': r.indicator5_leverage,
        'indicator6_real_estate_ratio': r.indicator6_real_estate_ratio,
        'indicator1_status': r.indicator1_status,
        'indicator2_status': r.indicator2_status,
        'indicator3_status': r.indicator3_status,
        'indicator4_status': r.indicator4_status,
        'indicator5_status': r.indicator5_status,
        'indicator6_status': r.indicator6_status,
    }


# ── Money Market fund calculation APIs ──────────────────────────────────────

@bp.route('/api/money_market/calculate', methods=['POST'])
@login_required
def api_money_market_calculate():
    """Calculate money market fund basic info and warning indicators."""
    try:
        req = request.get_json()
        fund_name = req.get('fund_name')
        date_str = req.get('date')

        if not fund_name or not date_str:
            return jsonify({'success': False, 'message': 'fund_name and date are required'}), 400

        query_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Check cache
        cached_basic = MoneyMarketBasicInfoResult.query.filter_by(
            fund_name=fund_name, query_date=query_date).first()
        cached_warning = MoneyMarketWarningIndicatorResult.query.filter_by(
            fund_name=fund_name, query_date=query_date).first()

        if cached_basic and cached_warning:
            return jsonify({
                'success': True,
                'basic_info': _serialize_mm_basic(cached_basic),
                'warning_indicators': _serialize_mm_warning(cached_warning),
                'source': 'cache',
            })

        # Load positions into DataFrame
        positions = MoneyMarketFundPosition.query.filter_by(
            fund_name=fund_name, position_date=query_date).all()
        if not positions:
            return jsonify({'success': False, 'message': f'No position data found for {fund_name} on {date_str}'})

        data = [{c.name: getattr(p, c.name) for c in MoneyMarketFundPosition.__table__.columns} for p in positions]
        df = pd.DataFrame(data)

        from app.calculators import MoneyMarketCalculator
        calc = MoneyMarketCalculator(data_provider)
        basic = calc.calculate_basic_info(df, query_date)
        warning = calc.calculate_warning_indicators(df, query_date)

        if basic is None:
            return jsonify({'success': False, 'message': 'Calculation failed'})

        # Get thresholds and judge warning status
        thresholds = {t.indicator_name: t.threshold_value for t in WarningThreshold.query.all()}
        statuses = calc.judge_warning_status(warning, thresholds) if warning else {}

        # Save basic info
        existing = MoneyMarketBasicInfoResult.query.filter_by(
            fund_name=fund_name, query_date=query_date).first()
        vals = dict(net_asset_billion=basic['net_asset_billion'],
                    portfolio_days=basic['portfolio_days'],
                    yield_7d=basic['yield_7d'],
                    asset_14days_billion=basic['asset_14days_billion'])
        if existing:
            for k, v in vals.items():
                setattr(existing, k, v)
        else:
            db.session.add(MoneyMarketBasicInfoResult(
                fund_name=fund_name, query_date=query_date, **vals))

        # Save warning indicators
        if warning:
            existing_w = MoneyMarketWarningIndicatorResult.query.filter_by(
                fund_name=fund_name, query_date=query_date).first()
            w_vals = dict(
                indicator1_value=warning['indicator1_14day_maturity_ratio'],
                indicator2_value=warning['indicator2_valuation_volatility'],
                indicator3_value=warning['indicator3_shadow_deviation'],
                indicator4_value=warning['indicator4_leverage'],
                **statuses,
            )
            if existing_w:
                for k, v in w_vals.items():
                    setattr(existing_w, k, v)
            else:
                db.session.add(MoneyMarketWarningIndicatorResult(
                    fund_name=fund_name, query_date=query_date, **w_vals))

        db.session.commit()

        # Re-read for consistent response
        cached_basic = MoneyMarketBasicInfoResult.query.filter_by(
            fund_name=fund_name, query_date=query_date).first()
        cached_warning = MoneyMarketWarningIndicatorResult.query.filter_by(
            fund_name=fund_name, query_date=query_date).first()

        return jsonify({
            'success': True,
            'basic_info': _serialize_mm_basic(cached_basic),
            'warning_indicators': _serialize_mm_warning(cached_warning),
            'source': 'calculated',
        })

    except Exception as e:
        logger.error(f'Money market calculation error: {e}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)})


def _serialize_mm_basic(r):
    return {
        'fund_name': r.fund_name,
        'query_date': r.query_date.strftime('%Y-%m-%d') if r.query_date else '',
        'net_asset_billion': r.net_asset_billion,
        'portfolio_days': r.portfolio_days,
        'yield_7d': r.yield_7d,
        'asset_14days_billion': r.asset_14days_billion,
    }


def _serialize_mm_warning(r):
    return {
        'fund_name': r.fund_name,
        'query_date': r.query_date.strftime('%Y-%m-%d') if r.query_date else '',
        'indicator1_value': r.indicator1_value,
        'indicator2_value': r.indicator2_value,
        'indicator3_value': r.indicator3_value,
        'indicator4_value': r.indicator4_value,
        'indicator1_status': r.indicator1_status,
        'indicator2_status': r.indicator2_status,
        'indicator3_status': r.indicator3_status,
        'indicator4_status': r.indicator4_status,
    }


# ── Fixed Income Plus fund calculation APIs ─────────────────────────────────

@bp.route('/api/fixed_income_plus/calculate', methods=['POST'])
@login_required
def api_fip_calculate():
    """Calculate fixed income plus fund basic info and 7 warning indicators."""
    try:
        req = request.get_json()
        fund_name = req.get('fund_name')
        date_str = req.get('date')

        if not fund_name or not date_str:
            return jsonify({'success': False, 'message': 'fund_name and date are required'}), 400

        query_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Check cache
        cached_basic = FixedIncomePlusBasicInfoResult.query.filter_by(
            fund_name=fund_name, query_date=query_date).first()
        cached_warning = FixedIncomePlusWarningIndicatorResult.query.filter_by(
            fund_name=fund_name, query_date=query_date).first()

        if cached_basic and cached_warning:
            return jsonify({
                'success': True,
                'basic_info': _serialize_fip_basic(cached_basic),
                'warning_indicators': _serialize_fip_warning(cached_warning),
                'source': 'cache',
            })

        from app.calculators import FixedIncomePlusCalculator
        calc = FixedIncomePlusCalculator(db.session, data_provider)
        basic, warning = calc.process_and_calculate(fund_name, query_date)

        if basic is None:
            return jsonify({'success': False, 'message': f'No position data found for {fund_name} on {date_str}'})

        calc.save_to_database(fund_name, query_date, basic, warning)

        cached_basic = FixedIncomePlusBasicInfoResult.query.filter_by(
            fund_name=fund_name, query_date=query_date).first()
        cached_warning = FixedIncomePlusWarningIndicatorResult.query.filter_by(
            fund_name=fund_name, query_date=query_date).first()

        return jsonify({
            'success': True,
            'basic_info': _serialize_fip_basic(cached_basic) if cached_basic else basic,
            'warning_indicators': _serialize_fip_warning(cached_warning) if cached_warning else warning,
            'source': 'calculated',
        })

    except Exception as e:
        logger.error(f'Fixed income plus calculation error: {e}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)})


def _serialize_fip_basic(r):
    return {
        'fund_name': r.fund_name,
        'query_date': r.query_date.strftime('%Y-%m-%d') if r.query_date else '',
        'net_asset_billion': r.net_asset_billion,
        'bond_ratio': r.bond_ratio,
        'convertible_bond_ratio': r.convertible_bond_ratio,
        'stock_ratio': r.stock_ratio,
        'demand_deposit_ratio': r.demand_deposit_ratio,
        'repo_ratio': r.repo_ratio,
        'stock_volatility': r.stock_volatility,
        'stock_beta': r.stock_beta,
        'pure_bond_premium_avg': r.pure_bond_premium_avg,
        'equity_premium_avg': r.equity_premium_avg,
        'portfolio_duration': r.portfolio_duration,
    }


def _serialize_fip_warning(r):
    return {
        'fund_name': r.fund_name,
        'query_date': r.query_date.strftime('%Y-%m-%d') if r.query_date else '',
        'indicator1_high_liquidity': r.indicator1_high_liquidity,
        'indicator2_aa_below_ratio': r.indicator2_aa_below_ratio,
        'indicator3_aa2_below_ratio': r.indicator3_aa2_below_ratio,
        'indicator4_low_rating_max_ratio': r.indicator4_low_rating_max_ratio,
        'indicator5_real_estate_ratio': r.indicator5_real_estate_ratio,
        'indicator6_leverage': r.indicator6_leverage,
        'indicator7_equity_securities_ratio': r.indicator7_equity_securities_ratio,
        'indicator1_status': r.indicator1_status,
        'indicator2_status': r.indicator2_status,
        'indicator3_status': r.indicator3_status,
        'indicator4_status': r.indicator4_status,
        'indicator5_status': r.indicator5_status,
        'indicator6_status': r.indicator6_status,
        'indicator7_status': r.indicator7_status,
    }
