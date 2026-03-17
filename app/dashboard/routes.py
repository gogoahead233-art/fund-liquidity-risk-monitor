from flask import render_template, jsonify
from flask_login import login_required, current_user
from app.dashboard import bp
from app import db


@bp.route('/')
@login_required
def index():
    return render_template('dashboard/index.html')


@bp.route('/health')
def health():
    from datetime import datetime
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat(), 'version': '1.0.0'})


@bp.route('/api/check_admin')
@login_required
def check_admin():
    return jsonify({'success': True, 'is_admin': current_user.is_admin})


@bp.route('/api/data_stats')
@login_required
def data_stats():
    from app.models import InvestorPosition, InvestorTransaction, User
    try:
        return jsonify({
            'success': True,
            'holding_count': InvestorPosition.query.count(),
            'transaction_count': InvestorTransaction.query.count(),
            'user_count': User.query.count(),
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/api/get_fund_names')
@login_required
def get_fund_names():
    from app.models import InvestorPosition, InvestorTransaction
    try:
        pos_names = {r[0] for r in db.session.query(InvestorPosition.fund_name).distinct().all()}
        txn_names = {r[0] for r in db.session.query(InvestorTransaction.fund_name).distinct().all()}
        all_names = sorted(pos_names | txn_names)
        return jsonify({'success': True, 'data': all_names})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/api/dropdown_options')
@login_required
def dropdown_options():
    from app.models import InvestorPosition, InvestorTransaction, UserPermission
    query_type = __import__('flask').request.args.get('type', 'position')
    try:
        # Fund names filtered by user permissions
        if current_user.is_admin:
            pos_names = {r[0] for r in db.session.query(InvestorPosition.fund_name).distinct().all()}
            txn_names = {r[0] for r in db.session.query(InvestorTransaction.fund_name).distinct().all()}
            fund_names = sorted(pos_names | txn_names)
        else:
            perms = UserPermission.query.filter_by(user_id=current_user.id).all()
            fund_names = sorted([p.fund_name for p in perms])

        if query_type == 'transaction':
            types = [r[0] for r in db.session.query(InvestorTransaction.investor_type).distinct().all() if r[0]]
            channels = [r[0] for r in db.session.query(InvestorTransaction.channel).distinct().all() if r[0]]
            tx_types = [r[0] for r in db.session.query(InvestorTransaction.transaction_type).distinct().all() if r[0]]
            return jsonify({
                'success': True,
                'fund_names': fund_names,
                'investor_types': sorted(types),
                'channels': sorted(channels),
                'transaction_types': sorted(tx_types),
            })
        else:
            types = [r[0] for r in db.session.query(InvestorPosition.investor_type).distinct().all() if r[0]]
            channels = [r[0] for r in db.session.query(InvestorPosition.channel).distinct().all() if r[0]]
            return jsonify({
                'success': True,
                'fund_names': fund_names,
                'investor_types': sorted(types),
                'channels': sorted(channels),
            })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


INDICATOR_NAMES = {
    'bond': ['High Liquidity Ratio', 'AA- & Below Ratio', 'AA(2)- & Below',
             'Single Issuer Max', 'Leverage Ratio', 'Real Estate Ratio'],
    'money_market': ['14-Day Maturity Ratio', 'Valuation Volatility',
                     'Shadow Price Deviation', 'Leverage Ratio'],
    'fixed_income_plus': ['High Liquidity Ratio', 'AA- & Below Ratio', 'AA(2)- & Below',
                          'Single Issuer Max', 'Real Estate Ratio', 'Leverage Ratio',
                          'Equity Securities Ratio'],
}


@bp.route('/api/smoke_index_cockpit')
@login_required
def smoke_index_cockpit():
    from app.models import (
        BondLiquidityWarning, MoneyMarketLiquidityWarning,
        FixedIncomePlusLiquidityWarning,
    )
    try:
        all_funds = []

        for Model, fund_type, indicator_count in [
            (BondLiquidityWarning, 'bond', 6),
            (MoneyMarketLiquidityWarning, 'money_market', 4),
            (FixedIncomePlusLiquidityWarning, 'fixed_income_plus', 7),
        ]:
            names = INDICATOR_NAMES[fund_type]
            records = Model.query.order_by(Model.monitor_date.desc()).all()
            seen = set()
            for r in records:
                if r.fund_name in seen:
                    continue
                seen.add(r.fund_name)

                has_warning = False
                indicators = []
                for i in range(1, indicator_count + 1):
                    status = getattr(r, f'indicator{i}_status', 'Normal') or 'Normal'
                    value = getattr(r, f'indicator{i}_value', None)
                    threshold = getattr(r, f'indicator{i}_threshold', None)
                    if status == 'Warning':
                        has_warning = True
                    indicators.append({
                        'index': i, 'name': names[i - 1] if i <= len(names) else f'Indicator {i}',
                        'value': value, 'threshold': threshold, 'status': status,
                    })

                all_funds.append({
                    'fund_name': r.fund_name,
                    'fund_type': fund_type,
                    'monitor_date': r.monitor_date.strftime('%Y-%m-%d') if r.monitor_date else '',
                    'has_warning': has_warning,
                    'indicators': indicators,
                })

        total = len(all_funds)
        warning_count = sum(1 for f in all_funds if f['has_warning'])

        return jsonify({
            'success': True,
            'total_funds': total,
            'warning_funds': warning_count,
            'normal_funds': total - warning_count,
            'all_funds': all_funds,
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/api/fund_detail')
@login_required
def fund_detail():
    from flask import request
    from app.models import (
        BondLiquidityWarning, MoneyMarketLiquidityWarning,
        FixedIncomePlusLiquidityWarning,
    )
    fund_name = request.args.get('fund_name', '')
    monitor_date = request.args.get('monitor_date', '')

    try:
        record = None
        fund_type = None
        for Model, ft, count in [
            (BondLiquidityWarning, 'bond', 6),
            (MoneyMarketLiquidityWarning, 'money_market', 4),
            (FixedIncomePlusLiquidityWarning, 'fixed_income_plus', 7),
        ]:
            q = Model.query.filter_by(fund_name=fund_name)
            if monitor_date:
                q = q.filter(Model.monitor_date == monitor_date)
            r = q.order_by(Model.monitor_date.desc()).first()
            if r:
                record = r
                fund_type = ft
                break

        if not record:
            return jsonify({'success': False, 'error': 'Fund not found'})

        names = INDICATOR_NAMES[fund_type]
        indicator_count = len(names)
        indicators = []
        for i in range(1, indicator_count + 1):
            indicators.append({
                'name': names[i - 1],
                'value': getattr(record, f'indicator{i}_value', None),
                'threshold': getattr(record, f'indicator{i}_threshold', None),
                'status': getattr(record, f'indicator{i}_status', 'Normal') or 'Normal',
            })

        return jsonify({
            'success': True,
            'data': {
                'fund_name': record.fund_name,
                'fund_type': fund_type,
                'monitor_date': record.monitor_date.strftime('%Y-%m-%d') if record.monitor_date else '',
                'indicators': indicators,
            },
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
