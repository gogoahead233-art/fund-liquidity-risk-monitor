from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.auth import bp
from app.models import User, UserPermission


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))

        flash('Invalid username or password', 'danger')

    return render_template('auth/login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@bp.route('/admin/users')
@login_required
def user_management():
    if not current_user.is_admin:
        flash('Permission denied', 'danger')
        return redirect(url_for('dashboard.index'))
    return render_template('auth/user_management.html')


@bp.route('/api/users', methods=['GET'])
@login_required
def api_get_users():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    users = User.query.all()
    result = []
    for user in users:
        permissions = UserPermission.query.filter_by(user_id=user.id).all()
        result.append({
            'id': user.id,
            'username': user.username,
            'is_admin': user.is_admin,
            'fund_names': [p.fund_name for p in permissions],
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else '',
        })
    return jsonify({'success': True, 'data': result})


@bp.route('/api/create_user', methods=['POST'])
@login_required
def api_create_user():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data = request.get_json()
    username = data.get('username', '').strip()
    fund_names = data.get('fund_names', [])

    if not username:
        return jsonify({'success': False, 'message': 'Username is required'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Username already exists'}), 400

    user = User(
        username=username,
        password=generate_password_hash('risk_123'),
        is_admin=False,
    )
    db.session.add(user)
    db.session.flush()

    for fund_name in fund_names:
        db.session.add(UserPermission(user_id=user.id, fund_name=fund_name))

    db.session.commit()
    return jsonify({'success': True, 'message': f'User {username} created successfully'})


@bp.route('/api/update_user_permissions', methods=['POST'])
@login_required
def api_update_user_permissions():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data = request.get_json()
    user_id = data.get('user_id')
    fund_names = data.get('fund_names', [])
    is_admin = data.get('is_admin', False)

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    user.is_admin = is_admin
    UserPermission.query.filter_by(user_id=user_id).delete()

    if not is_admin:
        for fund_name in fund_names:
            db.session.add(UserPermission(user_id=user_id, fund_name=fund_name))

    db.session.commit()
    return jsonify({'success': True, 'message': 'Permissions updated'})


@bp.route('/api/reset_password', methods=['POST'])
@login_required
def api_reset_password():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data = request.get_json()
    user_id = data.get('user_id')
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    user.password = generate_password_hash('risk_123')
    db.session.commit()
    return jsonify({'success': True, 'message': 'Password reset successful'})


@bp.route('/api/delete_user', methods=['POST'])
@login_required
def api_delete_user():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data = request.get_json()
    user_id = data.get('user_id')
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    if user.is_admin:
        return jsonify({'success': False, 'message': 'Cannot delete admin user'}), 400

    UserPermission.query.filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True, 'message': 'User deleted'})
