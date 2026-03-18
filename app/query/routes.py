from datetime import datetime
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.query import bp
from app import db
from app.models import InvestorPosition, InvestorTransaction, UserPermission


def _get_user_fund_filter():
    """Return list of fund names the current user can access, or None for admins."""
    if current_user.is_admin:
        return None
    perms = UserPermission.query.filter_by(user_id=current_user.id).all()
    return [p.fund_name for p in perms]


@bp.route('/position')
@login_required
def position_query():
    return render_template('query/position_query.html')


@bp.route('/transaction')
@login_required
def transaction_query():
    return render_template('query/transaction_query.html')


@bp.route('/position_change')
@login_required
def position_change():
    return render_template('query/position_change.html')


@bp.route('/api/query_position', methods=['POST'])
@login_required
def api_query_position():
    try:
        data = request.get_json()
        fund_names = data.get('fund_name', [])
        if isinstance(fund_names, str):
            fund_names = [fund_names] if fund_names else []
        investor_name = data.get('investor_name', '').strip()
        investor_types = data.get('investor_type', [])
        if isinstance(investor_types, str):
            investor_types = [investor_types] if investor_types else []
        channels = data.get('channel', [])
        if isinstance(channels, str):
            channels = [channels] if channels else []
        date_start = data.get('position_date_start')
        date_end = data.get('position_date_end')

        query = InvestorPosition.query

        # Apply user permission filter
        allowed = _get_user_fund_filter()
        if allowed is not None:
            query = query.filter(InvestorPosition.fund_name.in_(allowed))

        if fund_names:
            query = query.filter(InvestorPosition.fund_name.in_(fund_names))
        if investor_name:
            query = query.filter(InvestorPosition.investor_name.contains(investor_name))
        if investor_types:
            query = query.filter(InvestorPosition.investor_type.in_(investor_types))
        if channels:
            query = query.filter(InvestorPosition.channel.in_(channels))
        if date_start:
            query = query.filter(InvestorPosition.position_date >= date_start)
        if date_end:
            query = query.filter(InvestorPosition.position_date <= date_end)

        total = query.count()
        records = query.order_by(InvestorPosition.position_date.desc()).limit(1000).all()

        result = [{
            'account': r.account,
            'investor_name': r.investor_name,
            'investor_type': r.investor_type,
            'channel': r.channel,
            'fund_name': r.fund_name,
            'position_shares': r.position_shares,
            'position_amount': r.position_amount,
            'position_date': r.position_date.strftime('%Y-%m-%d') if r.position_date else '',
        } for r in records]

        return jsonify({'success': True, 'data': result, 'total': total, 'returned': len(result)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/api/query_transaction', methods=['POST'])
@login_required
def api_query_transaction():
    try:
        data = request.get_json()
        fund_names = data.get('fund_name', [])
        if isinstance(fund_names, str):
            fund_names = [fund_names] if fund_names else []
        investor_types = data.get('investor_type', [])
        if isinstance(investor_types, str):
            investor_types = [investor_types] if investor_types else []
        tx_types = data.get('transaction_type', [])
        if isinstance(tx_types, str):
            tx_types = [tx_types] if tx_types else []
        channels = data.get('channel', [])
        if isinstance(channels, str):
            channels = [channels] if channels else []
        date_start = data.get('transaction_date_start')
        date_end = data.get('transaction_date_end')

        query = InvestorTransaction.query

        allowed = _get_user_fund_filter()
        if allowed is not None:
            query = query.filter(InvestorTransaction.fund_name.in_(allowed))

        if fund_names:
            query = query.filter(InvestorTransaction.fund_name.in_(fund_names))
        if investor_types:
            query = query.filter(InvestorTransaction.investor_type.in_(investor_types))
        if tx_types:
            query = query.filter(InvestorTransaction.transaction_type.in_(tx_types))
        if channels:
            query = query.filter(InvestorTransaction.channel.in_(channels))
        if date_start:
            query = query.filter(InvestorTransaction.transaction_date >= date_start)
        if date_end:
            query = query.filter(InvestorTransaction.transaction_date <= date_end)

        total = query.count()
        records = query.order_by(InvestorTransaction.transaction_date.desc()).limit(1000).all()

        result = [{
            'account': r.account,
            'investor_name': r.investor_name,
            'investor_type': r.investor_type,
            'channel': r.channel,
            'transaction_type': r.transaction_type,
            'fund_name': r.fund_name,
            'transaction_shares': r.transaction_shares,
            'transaction_amount': r.transaction_amount,
            'transaction_date': r.transaction_date.strftime('%Y-%m-%d') if r.transaction_date else '',
        } for r in records]

        return jsonify({'success': True, 'data': result, 'total': total, 'returned': len(result)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/api/query_position_change', methods=['POST'])
@login_required
def api_query_position_change():
    try:
        data = request.get_json()
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if not start_date or not end_date:
            return jsonify({'success': False, 'message': 'Start date and end date are required'}), 400

        fund_names = data.get('fund_name', [])
        if isinstance(fund_names, str):
            fund_names = [fund_names] if fund_names else []

        # Build base queries
        q_start = InvestorPosition.query.filter(InvestorPosition.position_date == start_date)
        q_end = InvestorPosition.query.filter(InvestorPosition.position_date == end_date)

        allowed = _get_user_fund_filter()
        if allowed is not None:
            q_start = q_start.filter(InvestorPosition.fund_name.in_(allowed))
            q_end = q_end.filter(InvestorPosition.fund_name.in_(allowed))

        if fund_names:
            q_start = q_start.filter(InvestorPosition.fund_name.in_(fund_names))
            q_end = q_end.filter(InvestorPosition.fund_name.in_(fund_names))

        # Build position maps keyed by (account, fund_name)
        start_map = {}
        for r in q_start.all():
            key = (r.account, r.fund_name)
            start_map[key] = {
                'account': r.account, 'investor_name': r.investor_name,
                'investor_type': r.investor_type, 'channel': r.channel,
                'fund_name': r.fund_name, 'amount': r.position_amount,
            }

        end_map = {}
        for r in q_end.all():
            key = (r.account, r.fund_name)
            end_map[key] = {
                'account': r.account, 'investor_name': r.investor_name,
                'investor_type': r.investor_type, 'channel': r.channel,
                'fund_name': r.fund_name, 'amount': r.position_amount,
            }

        # Compare
        all_keys = set(start_map.keys()) | set(end_map.keys())
        changes = []
        for key in all_keys:
            s = start_map.get(key)
            e = end_map.get(key)
            initial = s['amount'] if s else 0
            final = e['amount'] if e else 0
            change = final - initial

            if change == 0:
                continue

            info = e or s
            change_type = 'New' if not s else ('Liquidation' if not e else 'Change')

            changes.append({
                'account': info['account'],
                'investor_name': info['investor_name'],
                'investor_type': info['investor_type'],
                'channel': info['channel'],
                'fund_name': info['fund_name'],
                'initial_amount': initial,
                'final_amount': final,
                'amount_change': change,
                'change_type': change_type,
            })

        changes.sort(key=lambda x: abs(x['amount_change']), reverse=True)

        return jsonify({'success': True, 'data': changes[:500], 'total': len(changes)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
