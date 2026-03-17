from datetime import datetime
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.analysis import bp
from app import db
from app.models import (
    InvestorPosition, FundStructureAnalysis,
    FundRedemptionAnalysis, FundRedemptionConfig,
    UserPermission,
)


def _get_user_fund_filter():
    """Return list of fund names the current user can access, or None for admins."""
    if current_user.is_admin:
        return None
    perms = UserPermission.query.filter_by(user_id=current_user.id).all()
    return [p.fund_name for p in perms]


def _check_fund_access(fund_name):
    """Return True if current user may access *fund_name*."""
    allowed = _get_user_fund_filter()
    return allowed is None or fund_name in allowed


# ── Holder-structure classification keywords ──────────────────────────────
# The original system classifies investors by Chinese keywords in their names.
# For the open-source demo we also accept English equivalents so that sample
# data works out of the box.

HIGH_AMOUNT_THRESHOLD = 200_000  # individual high/low split


def _classify_investor(inv_type, inv_name):
    """Return a category bucket name based on investor type and name.

    Supports both Chinese (original) and English (demo) investor types.
    Returns one of the bucket prefixes used in the analysis dict.
    """
    t = (inv_type or '').lower()
    n = (inv_name or '').lower()

    # Individual investors
    if t in ('individual', '个人'):
        return 'individual'  # caller splits high/low by amount

    # Product types — either the type field says "product" or specific subtypes
    if 'insurance' in t or '保险' in t or 'annuity' in t or '年金' in t:
        return 'insurance_product'
    if 'trust' in t or '信托' in t:
        return 'trust_product'
    if 'bank product' in t or 'bank wealth' in t or '理财' in t:
        return 'bank_product'
    if t in ('product', '产品') or 'product' in t:
        # Generic product — try to sub-classify by name
        if any(kw in n for kw in ('insurance', 'annuity', '保险', '年金')):
            return 'insurance_product'
        if any(kw in n for kw in ('trust', '信托')):
            return 'trust_product'
        if any(kw in n for kw in ('wealth', 'bank', '理财')):
            return 'bank_product'
        return 'other_product'

    # Institution types
    if t in ('institution', '机构') or 'institution' in t:
        if any(kw in n for kw in ('bank', '银行')):
            return 'bank_institution'
        if any(kw in n for kw in ('insurance', '保险')):
            return 'insurance_institution'
        if any(kw in n for kw in ('finance', '财务')):
            return 'finance_institution'
        return 'other_institution'

    # Fallback: try name-based classification
    return 'other_institution'


def _calculate_structure(fund_name, analysis_date):
    """Compute holder-structure analysis from investor positions."""
    positions = InvestorPosition.query.filter(
        InvestorPosition.fund_name == fund_name,
        InvestorPosition.position_date == analysis_date,
    ).all()

    if not positions:
        return None

    total_amount = sum(float(p.position_amount) for p in positions)
    total_count = len(positions)

    a = {
        'fund_name': fund_name,
        'analysis_date': analysis_date,
        'total_amount': total_amount,
        'total_count': total_count,
    }
    for prefix in (
        'high_amount_individual', 'low_amount_individual',
        'insurance_product', 'trust_product', 'bank_product', 'other_product',
        'bank_institution', 'insurance_institution', 'finance_institution', 'other_institution',
    ):
        a[f'{prefix}_count'] = 0
        a[f'{prefix}_amount'] = 0.0
        a[f'{prefix}_ratio'] = 0.0

    for pos in positions:
        inv_type = pos.investor_type or ''
        inv_name = pos.investor_name or ''
        amt = float(pos.position_amount)

        category = _classify_investor(inv_type, inv_name)

        if category == 'individual':
            bucket = 'high_amount_individual' if amt >= HIGH_AMOUNT_THRESHOLD else 'low_amount_individual'
        else:
            bucket = category

        a[f'{bucket}_count'] += 1
        a[f'{bucket}_amount'] += amt

    if total_amount > 0:
        for prefix in (
            'high_amount_individual', 'low_amount_individual',
            'insurance_product', 'trust_product', 'bank_product', 'other_product',
            'bank_institution', 'insurance_institution', 'finance_institution', 'other_institution',
        ):
            a[f'{prefix}_ratio'] = a[f'{prefix}_amount'] / total_amount

    return a


def _save_structure(data):
    """Persist a structure analysis dict, replacing any existing record."""
    existing = FundStructureAnalysis.query.filter_by(
        fund_name=data['fund_name'], analysis_date=data['analysis_date'],
    ).first()
    if existing:
        db.session.delete(existing)

    rec = FundStructureAnalysis(**{k: v for k, v in data.items()})
    db.session.add(rec)
    db.session.commit()
    return rec


_STRUCTURE_FIELDS = [
    'fund_name', 'total_amount', 'total_count',
    'high_amount_individual_count', 'high_amount_individual_amount', 'high_amount_individual_ratio',
    'low_amount_individual_count', 'low_amount_individual_amount', 'low_amount_individual_ratio',
    'insurance_product_count', 'insurance_product_amount', 'insurance_product_ratio',
    'trust_product_count', 'trust_product_amount', 'trust_product_ratio',
    'bank_product_count', 'bank_product_amount', 'bank_product_ratio',
    'other_product_count', 'other_product_amount', 'other_product_ratio',
    'bank_institution_count', 'bank_institution_amount', 'bank_institution_ratio',
    'insurance_institution_count', 'insurance_institution_amount', 'insurance_institution_ratio',
    'finance_institution_count', 'finance_institution_amount', 'finance_institution_ratio',
    'other_institution_count', 'other_institution_amount', 'other_institution_ratio',
]

_RATIO_FIELDS = [
    'high_amount_individual_ratio', 'low_amount_individual_ratio',
    'insurance_product_ratio', 'trust_product_ratio',
    'bank_product_ratio', 'other_product_ratio',
    'bank_institution_ratio', 'insurance_institution_ratio',
    'finance_institution_ratio', 'other_institution_ratio',
]

_REDEMPTION_RATIO_FIELDS = [
    'high_amount_individual_redemption_ratio', 'low_amount_individual_redemption_ratio',
    'insurance_product_redemption_ratio', 'trust_product_redemption_ratio',
    'bank_product_redemption_ratio', 'other_product_redemption_ratio',
    'bank_institution_redemption_ratio', 'insurance_institution_redemption_ratio',
    'finance_institution_redemption_ratio', 'other_institution_redemption_ratio',
]


def _get_attr(obj, key):
    return getattr(obj, key) if not isinstance(obj, dict) else obj.get(key, 0.0)


# ── Page routes ────────────────────────────────────────────────────────────

@bp.route('/holder_structure')
@login_required
def holder_structure():
    return render_template('analysis/holder_structure.html')


@bp.route('/redemption_scenario')
@login_required
def redemption_scenario():
    return render_template('analysis/redemption_scenario.html')


# ── API: Holder Structure ──────────────────────────────────────────────────

@bp.route('/api/structure_funds')
@login_required
def api_structure_funds():
    try:
        allowed = _get_user_fund_filter()
        query = db.session.query(InvestorPosition.fund_name).distinct()
        if allowed is not None:
            query = query.filter(InvestorPosition.fund_name.in_(allowed))
        fund_list = sorted(r[0] for r in query.all())
        return jsonify({'success': True, 'data': fund_list})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/api/structure_dates')
@login_required
def api_structure_dates():
    try:
        fund_name = request.args.get('fund_name')
        if not fund_name:
            return jsonify({'success': False, 'message': 'fund_name required'}), 400
        if not _check_fund_access(fund_name):
            return jsonify({'success': False, 'message': 'Access denied'}), 403

        dates = db.session.query(InvestorPosition.position_date).filter(
            InvestorPosition.fund_name == fund_name,
        ).distinct().order_by(InvestorPosition.position_date.desc()).all()
        return jsonify({'success': True, 'data': [d[0].strftime('%Y-%m-%d') for d in dates]})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/api/fund_structure_analysis', methods=['POST'])
@login_required
def api_fund_structure_analysis():
    try:
        data = request.get_json()
        fund_name = data.get('fund_name')
        analysis_date = data.get('analysis_date')
        if not fund_name or not analysis_date:
            return jsonify({'success': False, 'message': 'fund_name and analysis_date required'}), 400
        if not _check_fund_access(fund_name):
            return jsonify({'success': False, 'message': 'Access denied'}), 403

        analysis_date_obj = datetime.strptime(analysis_date, '%Y-%m-%d').date()

        existing = FundStructureAnalysis.query.filter_by(
            fund_name=fund_name, analysis_date=analysis_date_obj,
        ).first()

        if existing:
            result = {f: getattr(existing, f) for f in _STRUCTURE_FIELDS}
            result['analysis_date'] = existing.analysis_date.strftime('%Y-%m-%d')
        else:
            calc = _calculate_structure(fund_name, analysis_date_obj)
            if not calc:
                return jsonify({'success': False, 'message': 'No position data found'}), 404
            _save_structure(calc)
            result = {k: v for k, v in calc.items()}
            result['analysis_date'] = analysis_date

        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ── API: Redemption Scenario ──────────────────────────────────────────────

@bp.route('/api/redemption_dates')
@login_required
def api_redemption_dates():
    try:
        allowed = _get_user_fund_filter()
        q = db.session.query(InvestorPosition.fund_name).distinct()
        if allowed is not None:
            q = q.filter(InvestorPosition.fund_name.in_(allowed))
        funds = [r[0] for r in q.all()]

        result = {}
        for fn in funds:
            dates = db.session.query(InvestorPosition.position_date).filter(
                InvestorPosition.fund_name == fn,
            ).distinct().order_by(InvestorPosition.position_date.desc()).all()
            if dates:
                result[fn] = [d[0].strftime('%Y-%m-%d') for d in dates]

        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/api/fund_redemption_analysis', methods=['POST'])
@login_required
def api_fund_redemption_analysis():
    try:
        data = request.get_json()
        fund_name = data.get('fund_name')
        analysis_date = data.get('analysis_date')
        if not fund_name or not analysis_date:
            return jsonify({'success': False, 'message': 'fund_name and analysis_date required'}), 400
        if not _check_fund_access(fund_name):
            return jsonify({'success': False, 'message': 'Access denied'}), 403

        date_obj = datetime.strptime(analysis_date, '%Y-%m-%d').date()

        # Ensure structure analysis exists
        structure = FundStructureAnalysis.query.filter_by(
            fund_name=fund_name, analysis_date=date_obj,
        ).first()
        if not structure:
            calc = _calculate_structure(fund_name, date_obj)
            if not calc:
                return jsonify({'success': False, 'message': 'No position data found'}), 404
            structure = _save_structure(calc)

        # Get or create redemption config
        config = FundRedemptionConfig.query.filter_by(fund_name=fund_name).first()
        if not config:
            config = FundRedemptionConfig(fund_name=fund_name)
            db.session.add(config)
            db.session.commit()

        # Compute expected redemption ratio
        expected = sum(
            _get_attr(structure, rf) * getattr(config, rrf)
            for rf, rrf in zip(_RATIO_FIELDS, _REDEMPTION_RATIO_FIELDS)
        )

        structure_data = {rf: _get_attr(structure, rf) for rf in _RATIO_FIELDS}
        redemption_ratios = {rrf: getattr(config, rrf) for rrf in _REDEMPTION_RATIO_FIELDS}

        result = {
            'fund_name': fund_name,
            'analysis_date': analysis_date,
            'expected_redemption_ratio': expected,
            'structure_data': structure_data,
            'redemption_ratios': redemption_ratios,
        }
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/api/get_redemption_config')
@login_required
def api_get_redemption_config():
    try:
        fund_name = request.args.get('fund_name')
        if not fund_name:
            return jsonify({'success': False, 'message': 'fund_name required'}), 400
        if not _check_fund_access(fund_name):
            return jsonify({'success': False, 'message': 'Access denied'}), 403

        config = FundRedemptionConfig.query.filter_by(fund_name=fund_name).first()
        if not config:
            config = FundRedemptionConfig(fund_name=fund_name)
            db.session.add(config)
            db.session.commit()

        result = {'fund_name': config.fund_name}
        for f in _REDEMPTION_RATIO_FIELDS:
            result[f] = getattr(config, f)
        result['created_at'] = config.created_at.isoformat() if config.created_at else None
        result['updated_at'] = config.updated_at.isoformat() if config.updated_at else None
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/api/save_redemption_config', methods=['POST'])
@login_required
def api_save_redemption_config():
    try:
        if not current_user.is_admin:
            return jsonify({'success': False, 'message': 'Admin only'}), 403

        data = request.get_json()
        fund_name = data.get('fund_name')
        if not fund_name:
            return jsonify({'success': False, 'message': 'fund_name required'}), 400

        config = FundRedemptionConfig.query.filter_by(fund_name=fund_name).first()
        if not config:
            config = FundRedemptionConfig(fund_name=fund_name)
            db.session.add(config)

        for f in _REDEMPTION_RATIO_FIELDS:
            if f in data:
                setattr(config, f, float(data[f]))

        config.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Config saved'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/api/update_redemption_ratios', methods=['POST'])
@login_required
def api_update_redemption_ratios():
    try:
        if not current_user.is_admin:
            return jsonify({'success': False, 'message': 'Admin only'}), 403

        data = request.get_json()
        fund_name = data.get('fund_name')
        analysis_date = data.get('analysis_date')
        ratios = data.get('redemption_ratios', {})
        if not fund_name or not analysis_date:
            return jsonify({'success': False, 'message': 'fund_name and analysis_date required'}), 400

        date_obj = datetime.strptime(analysis_date, '%Y-%m-%d').date()

        rec = FundRedemptionAnalysis.query.filter_by(
            fund_name=fund_name, analysis_date=date_obj,
        ).first()
        if not rec:
            rec = FundRedemptionAnalysis(fund_name=fund_name, analysis_date=date_obj)
            db.session.add(rec)

        for key, value in ratios.items():
            if hasattr(rec, key):
                setattr(rec, key, float(value))

        # Recalculate expected ratio
        structure = FundStructureAnalysis.query.filter_by(
            fund_name=fund_name, analysis_date=date_obj,
        ).first()
        if structure:
            expected = sum(
                getattr(structure, rf) * getattr(rec, rrf)
                for rf, rrf in zip(_RATIO_FIELDS, _REDEMPTION_RATIO_FIELDS)
            )
            rec.expected_redemption_ratio = expected

        db.session.commit()
        return jsonify({'success': True, 'message': 'Ratios updated'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})
