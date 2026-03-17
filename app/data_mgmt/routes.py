import os
from datetime import datetime
from flask import render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.data_mgmt import bp
from app import db
from app.models import (
    InvestorPosition, InvestorTransaction,
    BondLiquidityWarning, MoneyMarketLiquidityWarning,
    FixedIncomePlusLiquidityWarning,
    OperationLog, SmtpConfig, FundEmailConfig, User,
)


def _admin_required(f):
    """Lightweight admin check for JSON APIs (not a decorator — call inline)."""
    pass  # unused, we check inline


def _log_operation(op_type, detail):
    try:
        log = OperationLog(
            user_id=current_user.id,
            username=current_user.username,
            operation_type=op_type,
            operation_detail=detail,
            ip_address=request.remote_addr,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


# ── Page routes ────────────────────────────────────────────────────────────

@bp.route('/management')
@login_required
def data_management():
    if not current_user.is_admin:
        flash('Permission denied', 'danger')
        return redirect(url_for('dashboard.index'))
    return render_template('data_mgmt/data_management.html')


@bp.route('/import')
@login_required
def data_import():
    if not current_user.is_admin:
        flash('Permission denied', 'danger')
        return redirect(url_for('dashboard.index'))
    return render_template('data_mgmt/import_data.html')


@bp.route('/settings')
@login_required
def settings():
    if not current_user.is_admin:
        flash('Permission denied', 'danger')
        return redirect(url_for('dashboard.index'))
    return render_template('settings/smtp_settings.html')


@bp.route('/operation_logs')
@login_required
def operation_logs_page():
    return render_template('data_mgmt/operation_logs.html')


# ── API: File Import ──────────────────────────────────────────────────────

@bp.route('/api/import', methods=['POST'])
@login_required
def api_import_data():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin only'}), 403
    try:
        file_type = request.form.get('file_type')
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400

        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            return jsonify({'success': False, 'message': 'Only .xlsx/.xls files supported'}), 400

        import pandas as pd

        df = pd.read_excel(file)
        imported = 0

        if file_type == 'position':
            imported = _import_positions(df)
        elif file_type == 'transaction':
            imported = _import_transactions(df)
        else:
            return jsonify({'success': False, 'message': f'Unknown file_type: {file_type}'}), 400

        _log_operation('Data Import', f'Imported {imported} {file_type} records from {file.filename}')
        return jsonify({'success': True, 'message': f'Imported {imported} records', 'imported_count': imported})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


def _import_positions(df):
    """Import investor position data from a DataFrame."""
    import pandas as pd

    col_map = {
        'C_FUNDACCO': 'account', 'C_FUNDNME': 'fund_name',
        'C_CUSTNAME': 'investor_name', 'C_CUSTTYPE': 'investor_type',
        'C_AGENCYNAME': 'channel', 'N_SHARES': 'position_shares',
        'N_AMOUNT': 'position_amount', 'N_DATE': 'position_date',
    }
    # Also accept already-English column names
    english_cols = set(col_map.values())

    # Determine if columns are Chinese codes or English
    if any(c in df.columns for c in col_map):
        df = df.rename(columns=col_map)

    required = ['account', 'fund_name', 'investor_name', 'investor_type',
                'channel', 'position_shares', 'position_amount']
    for col in required:
        if col not in df.columns:
            raise ValueError(f'Missing required column: {col}')

    count = 0
    batch = []
    for _, row in df.iterrows():
        if any(pd.isna(row.get(c)) for c in required):
            continue

        pos_date = row.get('position_date')
        if pd.isna(pos_date):
            pos_date = datetime.now().date()
        elif isinstance(pos_date, (int, float)):
            ds = str(int(pos_date))
            pos_date = datetime.strptime(ds, '%Y%m%d').date() if len(ds) == 8 else datetime.now().date()
        elif isinstance(pos_date, str):
            pos_date = datetime.strptime(pos_date, '%Y%m%d').date() if len(pos_date) == 8 and pos_date.isdigit() else pd.to_datetime(pos_date).date()
        elif isinstance(pos_date, pd.Timestamp):
            pos_date = pos_date.date()

        batch.append({
            'account': str(row['account']),
            'investor_name': str(row['investor_name']),
            'investor_type': str(row['investor_type']),
            'channel': str(row['channel']),
            'fund_name': str(row['fund_name']),
            'position_shares': float(row['position_shares']),
            'position_amount': float(row['position_amount']),
            'position_date': pos_date,
        })
        count += 1

        if len(batch) >= 5000:
            db.session.bulk_insert_mappings(InvestorPosition, batch)
            db.session.commit()
            batch = []

    if batch:
        db.session.bulk_insert_mappings(InvestorPosition, batch)
        db.session.commit()

    return count


def _import_transactions(df):
    """Import investor transaction data from a DataFrame."""
    import pandas as pd

    col_map = {
        'C_FUNDACCO': 'account', 'C_FUNDNME': 'fund_name',
        'C_CUSTNAME': 'investor_name', 'C_CUSTTYPE': 'investor_type',
        'C_AGENCYNAME': 'channel', 'C_BUSFLAG': 'transaction_type',
        'N_CONFIRMSHARES': 'transaction_shares',
        'N_CONFIRMAMOUNT': 'transaction_amount', 'N_DATE': 'transaction_date',
    }

    if any(c in df.columns for c in col_map):
        df = df.rename(columns=col_map)

    required = ['account', 'fund_name', 'investor_name', 'investor_type',
                'channel', 'transaction_type', 'transaction_shares', 'transaction_amount']
    for col in required:
        if col not in df.columns:
            raise ValueError(f'Missing required column: {col}')

    count = 0
    batch = []
    for _, row in df.iterrows():
        if any(pd.isna(row.get(c)) for c in required):
            continue

        tx_date = row.get('transaction_date')
        if pd.isna(tx_date):
            tx_date = datetime.now().date()
        elif isinstance(tx_date, (int, float)):
            ds = str(int(tx_date))
            tx_date = datetime.strptime(ds, '%Y%m%d').date() if len(ds) == 8 else datetime.now().date()
        elif isinstance(tx_date, str):
            tx_date = datetime.strptime(tx_date, '%Y%m%d').date() if len(tx_date) == 8 and tx_date.isdigit() else pd.to_datetime(tx_date).date()
        elif isinstance(tx_date, pd.Timestamp):
            tx_date = tx_date.date()

        batch.append({
            'account': str(row['account']),
            'investor_name': str(row['investor_name']),
            'investor_type': str(row['investor_type']),
            'channel': str(row['channel']),
            'transaction_type': str(row['transaction_type']),
            'fund_name': str(row['fund_name']),
            'transaction_shares': float(row['transaction_shares']),
            'transaction_amount': float(row['transaction_amount']),
            'transaction_date': tx_date,
        })
        count += 1

        if len(batch) >= 5000:
            db.session.bulk_insert_mappings(InvestorTransaction, batch)
            db.session.commit()
            batch = []

    if batch:
        db.session.bulk_insert_mappings(InvestorTransaction, batch)
        db.session.commit()

    return count


# ── API: Data Preview / Delete ────────────────────────────────────────────

_TABLE_MAP = {
    'position': (InvestorPosition, 'position_date'),
    'transaction': (InvestorTransaction, 'transaction_date'),
    'bond_warning': (BondLiquidityWarning, 'monitor_date'),
    'money_market_warning': (MoneyMarketLiquidityWarning, 'monitor_date'),
    'fixed_income_plus_warning': (FixedIncomePlusLiquidityWarning, 'monitor_date'),
}


def _build_delete_query(table_type, fund_name, start_date, end_date):
    entry = _TABLE_MAP.get(table_type)
    if not entry:
        return None, 0
    Model, date_col = entry
    q = Model.query
    if fund_name:
        q = q.filter(Model.fund_name.contains(fund_name))
    if start_date:
        q = q.filter(getattr(Model, date_col) >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        q = q.filter(getattr(Model, date_col) <= datetime.strptime(end_date, '%Y-%m-%d').date())
    return q, q.count()


@bp.route('/api/preview_delete', methods=['POST'])
@login_required
def api_preview_delete():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin only'}), 403
    try:
        data = request.get_json()
        table_type = data.get('table_type', '')
        fund_name = data.get('fund_name', '')
        start_date = data.get('start_date', '')
        end_date = data.get('end_date', '')

        _, count = _build_delete_query(table_type, fund_name, start_date, end_date)
        return jsonify({
            'success': True,
            'data': {
                'count': count,
                'conditions': {
                    'table_type': table_type,
                    'fund_name': fund_name,
                    'start_date': start_date,
                    'end_date': end_date,
                },
            },
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/api/confirm_delete', methods=['POST'])
@login_required
def api_confirm_delete():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin only'}), 403
    try:
        data = request.get_json()
        table_type = data.get('table_type', '')
        fund_name = data.get('fund_name', '')
        start_date = data.get('start_date', '')
        end_date = data.get('end_date', '')

        q, count = _build_delete_query(table_type, fund_name, start_date, end_date)
        if q is None:
            return jsonify({'success': False, 'message': f'Unknown table_type: {table_type}'}), 400

        q.delete(synchronize_session=False)
        db.session.commit()

        _log_operation('Data Delete', f'Deleted {count} records from {table_type}, fund={fund_name}, range={start_date}~{end_date}')
        return jsonify({'success': True, 'message': f'Deleted {count} records', 'data': {'deleted_count': count}})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


# ── API: Data Stats ───────────────────────────────────────────────────────

@bp.route('/api/data_counts')
@login_required
def api_data_counts():
    try:
        return jsonify({
            'success': True,
            'data': {
                'position_count': InvestorPosition.query.count(),
                'transaction_count': InvestorTransaction.query.count(),
                'bond_warning_count': BondLiquidityWarning.query.count(),
                'money_market_warning_count': MoneyMarketLiquidityWarning.query.count(),
                'fixed_income_plus_warning_count': FixedIncomePlusLiquidityWarning.query.count(),
                'user_count': User.query.count(),
            },
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ── API: Operation Logs ───────────────────────────────────────────────────

@bp.route('/api/operation_logs')
@login_required
def api_operation_logs():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        logs = OperationLog.query.order_by(
            OperationLog.created_at.desc()
        ).limit(per_page).offset((page - 1) * per_page).all()

        result = [{
            'id': log.id,
            'username': log.username,
            'operation_type': log.operation_type,
            'operation_detail': log.operation_detail,
            'ip_address': log.ip_address,
            'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else '',
        } for log in logs]

        total = OperationLog.query.count()
        return jsonify({'success': True, 'data': result, 'total': total})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ── API: SMTP Settings ───────────────────────────────────────────────────

@bp.route('/api/smtp_config')
@login_required
def api_get_smtp_config():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin only'}), 403
    try:
        config = SmtpConfig.query.filter_by(is_active=True).first()
        if not config:
            return jsonify({'success': True, 'data': None})
        return jsonify({
            'success': True,
            'data': {
                'id': config.id,
                'smtp_server': config.smtp_server,
                'smtp_port': config.smtp_port,
                'sender_email': config.sender_email,
                'is_active': config.is_active,
                'updated_at': config.updated_at.strftime('%Y-%m-%d %H:%M:%S') if config.updated_at else '',
            },
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/api/smtp_config', methods=['POST'])
@login_required
def api_save_smtp_config():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin only'}), 403
    try:
        data = request.get_json()
        smtp_server = data.get('smtp_server')
        smtp_port = data.get('smtp_port', 465)
        sender_email = data.get('sender_email')
        auth_token = data.get('auth_token', '')

        if not smtp_server or not sender_email:
            return jsonify({'success': False, 'message': 'smtp_server and sender_email required'}), 400

        config = SmtpConfig.query.filter_by(is_active=True).first()
        if config:
            config.smtp_server = smtp_server
            config.smtp_port = int(smtp_port)
            config.sender_email = sender_email
            if auth_token:
                config.auth_token = auth_token.encode('utf-8')
            config.updated_at = datetime.utcnow()
        else:
            config = SmtpConfig(
                smtp_server=smtp_server,
                smtp_port=int(smtp_port),
                sender_email=sender_email,
                auth_token=auth_token.encode('utf-8') if auth_token else b'',
                is_active=True,
            )
            db.session.add(config)

        db.session.commit()
        _log_operation('Settings', f'Updated SMTP config: {smtp_server}:{smtp_port}')
        return jsonify({'success': True, 'message': 'SMTP config saved'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


# ── API: Fund Email Config ────────────────────────────────────────────────

@bp.route('/api/fund_email_configs')
@login_required
def api_get_fund_email_configs():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin only'}), 403
    try:
        configs = FundEmailConfig.query.all()
        return jsonify({
            'success': True,
            'data': [{
                'id': c.id,
                'fund_name': c.fund_name,
                'email_address': c.email_address,
            } for c in configs],
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/api/fund_email_configs', methods=['POST'])
@login_required
def api_save_fund_email_config():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin only'}), 403
    try:
        data = request.get_json()
        fund_name = data.get('fund_name')
        email_address = data.get('email_address')
        if not fund_name or not email_address:
            return jsonify({'success': False, 'message': 'fund_name and email_address required'}), 400

        existing = FundEmailConfig.query.filter_by(fund_name=fund_name).first()
        if existing:
            existing.email_address = email_address
        else:
            db.session.add(FundEmailConfig(fund_name=fund_name, email_address=email_address))

        db.session.commit()
        return jsonify({'success': True, 'message': 'Fund email config saved'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/api/fund_email_configs/<int:config_id>', methods=['DELETE'])
@login_required
def api_delete_fund_email_config(config_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin only'}), 403
    try:
        config = db.session.get(FundEmailConfig, config_id)
        if not config:
            return jsonify({'success': False, 'message': 'Config not found'}), 404
        db.session.delete(config)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Deleted'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})
