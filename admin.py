from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app, send_from_directory, send_file, make_response
from flask_login import login_required, current_user
from sqlalchemy import func
from flask_mail import Message
from functools import wraps
from werkzeug.utils import secure_filename
from models import db, User, Campaign, KYC, News, PaymentMethod, Location, Donation, UserActivity, Notification, AuditLog, Comment, SystemSettings
from forms import NewsForm, PaymentMethodForm, LocationForm, AppreciationForm
from security_utils import security_manager, ActivityLogger, NotificationManager
from datetime import datetime
import os
import io
import json
import shutil
import zipfile
import datetime as _dt
import requests

bp = Blueprint('admin', __name__, url_prefix='/admin')

# ------------------------------------------
# Safe Coinbase Check (non-blocking)
# ------------------------------------------
try:
    response = requests.get("https://api.commerce.coinbase.com", timeout=5)
    print(f"✅ Coinbase API reachable: {response.status_code}")
except requests.exceptions.RequestException:
    print("⚠️ Coinbase API not reachable right now — continuing without it.")


# ------------------------------------------
# ADMIN ACCESS DECORATOR
# ------------------------------------------
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


# ------------------------------------------
# ADMIN DASHBOARD
# ------------------------------------------
@bp.route('/')
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    total_campaigns = Campaign.query.count()
    pending_kyc = KYC.query.filter_by(status='pending').count()
    pending_campaigns = Campaign.query.filter_by(published=False).count()
    total_donations = Donation.query.filter_by(status='completed').count()
    total_raised = db.session.query(db.func.sum(Donation.amount)).filter_by(status='completed').scalar() or 0

    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_donations = Donation.query.order_by(Donation.created_at.desc()).limit(10).all()

    return render_template('admin/dashboard.html',
                           total_users=total_users,
                           total_campaigns=total_campaigns,
                           pending_kyc=pending_kyc,
                           pending_campaigns=pending_campaigns,
                           total_donations=total_donations,
                           total_raised=total_raised,
                           recent_users=recent_users,
                           recent_donations=recent_donations)


# ------------------------------------------
# USERS MANAGEMENT
# ------------------------------------------
@bp.route('/users')
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/users.html', users=users)


@bp.route('/user/<int:id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(id):
    user = User.query.get_or_404(id)
    user.is_admin = not user.is_admin
    db.session.commit()
    flash(f'User {user.name} admin status updated', 'success')
    return redirect(url_for('admin.users'))


# ------------------------------------------
# KYC VERIFICATION
# ------------------------------------------
@bp.route('/kyc-verification')
@login_required
@admin_required
def kyc_verification():
    pending = KYC.query.filter_by(status='pending').all()
    verified = KYC.query.filter_by(status='verified').order_by(KYC.verified_at.desc()).limit(20).all()
    rejected = KYC.query.filter_by(status='rejected').order_by(KYC.submitted_at.desc()).limit(20).all()
    return render_template('admin/kyc_verification.html',
                           pending=pending,
                           verified=verified,
                           rejected=rejected)


@bp.route('/kyc/<int:id>/verify', methods=['POST'])
@login_required
@admin_required
def verify_kyc(id):
    kyc = KYC.query.get_or_404(id)
    action = request.form.get('action')

    if action == 'approve':
        kyc.status = 'verified'
        kyc.verified_at = datetime.utcnow()
        flash(f'KYC for {kyc.user.name} approved', 'success')
    elif action == 'reject':
        kyc.status = 'rejected'
        flash(f'KYC for {kyc.user.name} rejected', 'warning')

    db.session.commit()
    return redirect(url_for('admin.kyc_verification'))


# ------------------------------------------
# CAMPAIGN MANAGEMENT
# ------------------------------------------
@bp.route('/campaigns')
@login_required
@admin_required
def campaigns():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')

    query = Campaign.query
    if status == 'pending':
        query = query.filter_by(published=False)
    elif status == 'published':
        query = query.filter_by(published=True)

    campaigns = query.order_by(Campaign.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/campaigns.html', campaigns=campaigns, status=status)


@bp.route('/campaign/<int:id>/toggle-publish', methods=['POST'])
@login_required
@admin_required
def toggle_campaign_publish(id):
    campaign = Campaign.query.get_or_404(id)
    campaign.published = not campaign.published
    db.session.commit()
    flash(f'Campaign "{campaign.title}" {"published" if campaign.published else "unpublished"}', 'success')
    return redirect(url_for('admin.campaigns'))


@bp.route('/campaign/<int:id>/update-raised', methods=['POST'])
@login_required
@admin_required
def update_raised_amount(id):
    campaign = Campaign.query.get_or_404(id)
    try:
        new_amount = float(request.form.get('raised_amount'))
        if new_amount < 0:
            raise ValueError("Amount cannot be negative")
        campaign.raised_amount = new_amount
        db.session.commit()
        flash(f'Updated raised amount for "{campaign.title}" to ${new_amount:.2f}', 'success')
    except ValueError:
        flash('Invalid amount entered. Please enter a valid number.', 'danger')
    return redirect(url_for('admin.campaigns'))


@bp.route('/campaign/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_campaign(id):
    campaign = Campaign.query.get_or_404(id)
    db.session.delete(campaign)
    db.session.commit()
    flash(f'Campaign "{campaign.title}" deleted', 'success')
    return redirect(url_for('admin.campaigns'))


# ------------------------------------------
# NEWS MANAGEMENT
# ------------------------------------------
@bp.route('/news', methods=['GET', 'POST'])
@login_required
@admin_required
def news():
    form = NewsForm()
    if form.validate_on_submit():
        news = News(title=form.title.data, content=form.content.data, author_id=current_user.id)

        if form.image.data:
            file = form.image.data
            filename = secure_filename(f"news_{datetime.utcnow().timestamp()}_{file.filename}")
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'news', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)
            news.image_path = f'/static/uploads/news/{filename}'

        db.session.add(news)
        db.session.commit()
        flash('News published successfully!', 'success')
        return redirect(url_for('admin.news'))

    all_news = News.query.order_by(News.created_at.desc()).all()
    return render_template('admin/news.html', form=form, news=all_news)


@bp.route('/news/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_news(id):
    news = News.query.get_or_404(id)
    db.session.delete(news)
    db.session.commit()
    flash('News deleted successfully', 'success')
    return redirect(url_for('admin.news'))


# ------------------------------------------
# PAYMENT METHODS MANAGEMENT
# ------------------------------------------
@bp.route('/payment-methods', methods=['GET', 'POST'])
@login_required
@admin_required
def payment_methods():
    form = PaymentMethodForm()
    if form.validate_on_submit():
        pm = PaymentMethod(
            name=form.name.data,
            type=form.type.data,
            details=form.details.data
        )

        # Handle specific fields based on type
        if form.type.data == 'crypto':
            pm.crypto_wallet_address = form.crypto_wallet_address.data
            pm.crypto_currency = form.crypto_currency.data
        elif form.type.data == 'bank':
            pm.bank_name = form.bank_name.data
            pm.account_name = form.account_name.data
            pm.account_number = form.account_number.data
        elif form.type.data == 'paypal':
            pm.paypal_client_id = form.paypal_client_id.data
            pm.paypal_secret = form.paypal_secret.data
        elif form.type.data == 'paystack':
            pm.paystack_public_key = form.paystack_public_key.data
            pm.paystack_secret_key = form.paystack_secret_key.data

        db.session.add(pm)
        db.session.commit()
        flash('Payment method added successfully!', 'success')
        return redirect(url_for('admin.payment_methods'))

    methods = PaymentMethod.query.order_by(PaymentMethod.created_at.desc()).all()
    return render_template('admin/payment_methods.html', form=form, methods=methods)


@bp.route('/payment-method/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_payment_method(id):
    pm = PaymentMethod.query.get_or_404(id)
    pm.active = not pm.active
    db.session.commit()
    flash('Payment method status updated', 'success')
    return redirect(url_for('admin.payment_methods'))


@bp.route('/payment-method/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_payment_method(id):
    pm = PaymentMethod.query.get_or_404(id)
    db.session.delete(pm)
    db.session.commit()
    flash('Payment method deleted', 'success')
    return redirect(url_for('admin.payment_methods'))


# ------------------------------------------
# LOCATIONS MANAGEMENT
# ------------------------------------------
@bp.route('/locations', methods=['GET', 'POST'])
@login_required
@admin_required
def locations():
    form = LocationForm()
    if form.validate_on_submit():
        location = Location(name=form.name.data, country=form.country.data)
        db.session.add(location)
        db.session.commit()
        flash('Location added successfully', 'success')
        return redirect(url_for('admin.locations'))
    all_locations = Location.query.all()
    return render_template('admin/locations.html', form=form, locations=all_locations)


@bp.route('/location/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_location(id):
    location = Location.query.get_or_404(id)
    db.session.delete(location)
    db.session.commit()
    flash('Location deleted', 'success')
    return redirect(url_for('admin.locations'))


# ------------------------------------------
# APPRECIATION EMAIL
# ------------------------------------------
@bp.route('/appreciate/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def appreciate_user(user_id):
    user = User.query.get_or_404(user_id)
    form = AppreciationForm()
    if form.validate_on_submit():
        mail = current_app.extensions['mail']
        default_sender = current_app.config.get('MAIL_DEFAULT_SENDER')
        platform_name = current_app.config.get('PLATFORM_NAME', 'Helping Hand Together')

        # Build sender override
        from_name = form.from_name.data.strip() if getattr(form, 'from_name', None) and form.from_name.data else platform_name
        from_email = form.from_email.data.strip() if getattr(form, 'from_email', None) and form.from_email.data else None

        # Prefer custom sender if provided; otherwise fall back to default sender
        sender_value = (from_name, from_email) if from_email else default_sender

        msg = Message(subject=f'Appreciation from {from_name or platform_name}',
                      recipients=[user.email],
                      body=form.message.data,
                      sender=sender_value)
        # Always set Reply-To to from_email if provided
        if from_email:
            msg.reply_to = from_email
        try:
            mail.send(msg)
            flash(f'Appreciation email sent to {user.name}', 'success')
        except Exception as e:
            # Retry with default sender if custom sender rejected by SMTP
            try:
                msg.sender = default_sender
                mail.send(msg)
                flash(f'Email sent to {user.name} (Reply-To set to {from_email})', 'warning')
            except Exception as e2:
                flash(f'Failed to send email: {str(e2)}', 'danger')
        return redirect(url_for('admin.users'))
    return render_template('admin/appreciate.html', user=user, form=form)


# ------------------------------------------
# DONATIONS MANAGEMENT
# ------------------------------------------
@bp.route('/donations')
@login_required
@admin_required
def donations():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')

    query = Donation.query
    if status != 'all':
        query = query.filter_by(status=status)

    donations = query.order_by(Donation.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/donations.html', donations=donations, status=status)


@bp.route('/donation/<int:id>/confirm', methods=['POST'])
@login_required
@admin_required
def confirm_donation(id):
    donation = Donation.query.get_or_404(id)
    if donation.status in ['pending','awaiting_verification']:
        donation.status = 'completed'
        donation.campaign.raised_amount += donation.amount
        db.session.commit()
        flash('Donation confirmed and campaign total updated', 'success')
    else:
        flash('Donation already confirmed', 'warning')
    return redirect(url_for('admin.donations'))

@bp.route('/donation/<int:id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_donation(id):
    donation = Donation.query.get_or_404(id)
    if donation.status != 'completed':
        donation.status = 'rejected'
        db.session.commit()
        flash('Donation rejected', 'info')
    else:
        flash('Cannot reject a completed donation', 'warning')
    return redirect(url_for('admin.donations'))


# ------------------------------------------
# ENHANCED KYC MANAGEMENT
# ------------------------------------------
@bp.route('/kyc-management')
@login_required
@admin_required
def kyc_management():
    """Enhanced KYC management with image viewing"""
    kyc_documents = KYC.query.order_by(KYC.submitted_at.desc()).all()
    return render_template('admin/kyc_management.html', kyc_documents=kyc_documents)


@bp.route('/kyc/<int:kyc_id>/update-status', methods=['POST'])
@login_required
@admin_required
def update_kyc_status(kyc_id):
    """Update KYC document status"""
    kyc = KYC.query.get_or_404(kyc_id)
    new_status = request.form.get('status')
    
    old_status = kyc.status
    kyc.status = new_status
    
    if new_status == 'verified':
        kyc.verified_at = datetime.utcnow()
    
    db.session.commit()
    
    # Log the action
    ActivityLogger.log_audit_action(
        current_user.id,
        f'kyc_status_updated',
        'kyc',
        kyc.id,
        {'status': old_status},
        {'status': new_status}
    )
    
    # Notify user
    if new_status == 'verified':
        NotificationManager.create_notification(
            kyc.user.id,
            'KYC Verified',
            'Your identity verification has been approved!',
            'success'
        )
    elif new_status == 'rejected':
        NotificationManager.create_notification(
            kyc.user.id,
            'KYC Rejected',
            'Your identity verification was rejected. Please resubmit with valid documents.',
            'warning'
        )
    
    flash(f'KYC status updated to {new_status}', 'success')
    return redirect(url_for('admin.kyc_management'))


# ------------------------------------------
# USER DETAILS API
# ------------------------------------------
@bp.route('/api/user-details/<int:user_id>')
@login_required
@admin_required
def get_user_details(user_id):
    """Get detailed user information for admin"""
    user = User.query.get_or_404(user_id)
    
    # Get user statistics
    campaigns_count = Campaign.query.filter_by(owner_id=user.id).count()
    donations_made = Donation.query.filter_by(donor_email=user.email).all()
    donations_count = len(donations_made)
    total_donated = sum(d.amount for d in donations_made if d.status == 'completed')
    
    # Get recent activities
    activities = UserActivity.query.filter_by(user_id=user.id)\
                                  .order_by(UserActivity.created_at.desc())\
                                  .limit(10).all()
    
    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'phone_number': user.phone_number,
        'location': user.location,
        'latitude': user.latitude,
        'longitude': user.longitude,
        'created_at': user.created_at.isoformat(),
        'last_seen': user.last_seen.isoformat(),
        'is_active': user.is_active,
        'login_count': user.login_count,
        'campaigns_count': campaigns_count,
        'donations_count': donations_count,
        'total_donated': total_donated,
        'activities': [{
            'activity_type': a.activity_type,
            'description': a.description,
            'ip_address': a.ip_address,
            'created_at': a.created_at.isoformat()
        } for a in activities]
    })


# ------------------------------------------
# ENHANCED USER MANAGEMENT
# ------------------------------------------
@bp.route('/users-advanced')
@login_required
@admin_required
def users_advanced():
    """Advanced user management with location and activity data"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    location_filter = request.args.get('location', '')
    
    query = User.query
    
    if search:
        query = query.filter(
            User.name.contains(search) |
            User.email.contains(search)
        )
    
    if location_filter:
        query = query.filter(User.location.contains(location_filter))
    
    users = query.order_by(User.last_seen.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get location statistics
    location_stats = db.session.query(
        User.location, func.count(User.id)
    ).group_by(User.location).filter(User.location.isnot(None)).all()
    
    return render_template('admin/users_advanced.html', 
                         users=users, 
                         location_stats=location_stats,
                         search=search,
                         location_filter=location_filter)


# ------------------------------------------
# ANALYTICS DASHBOARD
# ------------------------------------------
@bp.route('/analytics')
@login_required
@admin_required
def analytics():
    """Advanced analytics dashboard"""
    # Time-based statistics
    from datetime import timedelta
    
    now = datetime.utcnow()
    last_30_days = now - timedelta(days=30)
    last_7_days = now - timedelta(days=7)
    
    # User growth
    new_users_30d = User.query.filter(User.created_at >= last_30_days).count()
    new_users_7d = User.query.filter(User.created_at >= last_7_days).count()
    
    # Campaign stats
    campaigns_30d = Campaign.query.filter(Campaign.created_at >= last_30_days).count()
    published_campaigns = Campaign.query.filter_by(published=True).count()
    
    # Donation stats
    donations_30d = Donation.query.filter(
        Donation.created_at >= last_30_days,
        Donation.status == 'completed'
    ).count()
    
    amount_30d = db.session.query(func.sum(Donation.amount)).filter(
        Donation.created_at >= last_30_days,
        Donation.status == 'completed'
    ).scalar() or 0
    
    # Top campaigns by donations
    top_campaigns = db.session.query(
        Campaign.title,
        func.count(Donation.id).label('donation_count'),
        func.sum(Donation.amount).label('total_amount')
    ).join(Donation).filter(Donation.status == 'completed')\
     .group_by(Campaign.id).order_by(func.sum(Donation.amount).desc()).limit(10).all()
    
    # Payment method usage
    payment_stats = db.session.query(
        Donation.payment_method,
        func.count(Donation.id).label('count')
    ).filter(Donation.status == 'completed')\
     .group_by(Donation.payment_method).all()
    
    return render_template('admin/analytics.html',
                         new_users_30d=new_users_30d,
                         new_users_7d=new_users_7d,
                         campaigns_30d=campaigns_30d,
                         published_campaigns=published_campaigns,
                         donations_30d=donations_30d,
                         amount_30d=amount_30d,
                         top_campaigns=top_campaigns,
                         payment_stats=payment_stats)


# ------------------------------------------
# SYSTEM SETTINGS
# ------------------------------------------
@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def system_settings():
    """System configuration and settings"""
    from models import SystemSettings

    if request.method == 'POST':
        settings_data = request.form.to_dict()

        # Normalize checkboxes (set to false if missing)
        if 'setting_smtp_use_tls' not in settings_data:
            settings_data['setting_smtp_use_tls'] = 'false'

        # Stash platform name for email subject prefix
        platform_name = settings_data.get('setting_platform_name', 'Helping Hand Together')

        for key, value in settings_data.items():
            if not key.startswith('setting_'):
                continue
            setting_key = key.replace('setting_', '')
            setting = SystemSettings.query.filter_by(key=setting_key).first()

            # Preserve existing SMTP password if left blank
            if setting_key == 'smtp_password' and (value is None or value.strip() == ''):
                continue

            if setting:
                # Encrypt sensitive settings
                if setting.is_encrypted:
                    setting.value = security_manager.encrypt_data(value)
                else:
                    setting.value = value
                setting.updated_at = datetime.utcnow()
            else:
                # Create new setting
                is_encrypted = setting_key in ['smtp_password', 'api_keys', 'secrets']
                setting_value = security_manager.encrypt_data(value) if is_encrypted else value
                new_setting = SystemSettings(
                    key=setting_key,
                    value=setting_value,
                    is_encrypted=is_encrypted
                )
                db.session.add(new_setting)

        db.session.commit()

        # Apply runtime config for email immediately
        try:
            smtp_server = SystemSettings.query.filter_by(key='smtp_server').first()
            smtp_port = SystemSettings.query.filter_by(key='smtp_port').first()
            smtp_username = SystemSettings.query.filter_by(key='smtp_username').first()
            smtp_password = SystemSettings.query.filter_by(key='smtp_password').first()
            smtp_use_tls = SystemSettings.query.filter_by(key='smtp_use_tls').first()
            sender_name = SystemSettings.query.filter_by(key='mail_default_sender_name').first()
            sender_email = SystemSettings.query.filter_by(key='mail_default_sender_email').first()

            current_app.config['MAIL_SERVER'] = smtp_server.value if smtp_server else current_app.config.get('MAIL_SERVER')
            current_app.config['MAIL_PORT'] = int(smtp_port.value) if smtp_port and smtp_port.value else current_app.config.get('MAIL_PORT', 587)
            current_app.config['MAIL_USERNAME'] = smtp_username.value if smtp_username else current_app.config.get('MAIL_USERNAME')
            current_app.config['MAIL_PASSWORD'] = (
                security_manager.decrypt_data(smtp_password.value)
                if (smtp_password and smtp_password.value and smtp_password.is_encrypted)
                else (smtp_password.value if smtp_password else current_app.config.get('MAIL_PASSWORD'))
            )
            current_app.config['MAIL_USE_TLS'] = (str(smtp_use_tls.value).lower() in ['1','true','on','yes']) if smtp_use_tls else current_app.config.get('MAIL_USE_TLS', True)
            # Default sender and platform name
            if sender_email and sender_email.value:
                default_name = sender_name.value if sender_name and sender_name.value else platform_name
                current_app.config['MAIL_DEFAULT_SENDER'] = (default_name, sender_email.value)
            current_app.config['PLATFORM_NAME'] = platform_name
        except Exception as e:
            current_app.logger.warning(f"Failed to apply email settings: {e}")

        flash('Settings updated successfully', 'success')
        return redirect(url_for('admin.system_settings'))

    settings = SystemSettings.query.order_by(SystemSettings.category, SystemSettings.key).all()
    settings_map = {s.key: s.value for s in settings}

    return render_template('admin/system_settings.html', settings=settings, settings_map=settings_map)


# ------------------------------------------
# BACKUPS, EXPORTS, RESTORE/IMPORT
# ------------------------------------------

def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def _abs_db_path():
    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if uri.startswith('sqlite:///'):
        rel = uri.replace('sqlite:///', '', 1)
        return rel if os.path.isabs(rel) else os.path.join(current_app.root_path, rel)
    return None


def _row_to_dict(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def _serialize_queryset(rows):
    out = []
    for r in rows:
        d = _row_to_dict(r)
        # Convert datetimes
        for k, v in list(d.items()):
            if isinstance(v, (_dt.datetime,)):
                d[k] = v.isoformat()
        out.append(d)
    return out


@bp.route('/backup/create', methods=['POST'])
@login_required
@admin_required
def create_backup():
    backups_dir = _ensure_dir(os.path.join(current_app.instance_path, 'backups'))
    ts = _dt.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    zip_name = f"backup-{ts}.zip"
    zip_path = os.path.join(backups_dir, zip_name)

    # Gather content
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        # DB file (if sqlite)
        db_path = _abs_db_path()
        if db_path and os.path.exists(db_path):
            zf.write(db_path, arcname='database.sqlite')
        else:
            # Fallback: dump data tables to JSON if not sqlite
            data_json = {
                'users': _serialize_queryset(User.query.all()),
                'campaigns': _serialize_queryset(Campaign.query.all()),
                'donations': _serialize_queryset(Donation.query.all()),
                'kyc': _serialize_queryset(KYC.query.all()),
                'payment_methods': _serialize_queryset(PaymentMethod.query.all()),
                'locations': _serialize_queryset(Location.query.all()),
                'news': _serialize_queryset(News.query.all()),
                'comments': _serialize_queryset([]),
            }
            zf.writestr('data.json', json.dumps(data_json, indent=2))

        # System settings always included
        settings = _serialize_queryset(SystemSettings.query.all())
        zf.writestr('system_settings.json', json.dumps(settings, indent=2))

    # Persist zip
    with open(zip_path, 'wb') as f:
        f.write(mem.getvalue())

    flash('Backup created successfully', 'success')
    return redirect(url_for('admin.list_backups'))


@bp.route('/backups')
@login_required
@admin_required
def list_backups():
    backups_dir = _ensure_dir(os.path.join(current_app.instance_path, 'backups'))
    files = []
    for name in sorted(os.listdir(backups_dir)):
        path = os.path.join(backups_dir, name)
        if os.path.isfile(path) and name.lower().endswith('.zip'):
            stat = os.stat(path)
            files.append({
                'name': name,
                'size': stat.st_size,
                'modified': _dt.datetime.utcfromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S UTC')
            })
    return render_template('admin/backups.html', files=files)


@bp.route('/backups/download/<path:filename>')
@login_required
@admin_required
def download_backup(filename):
    backups_dir = os.path.join(current_app.instance_path, 'backups')
    return send_from_directory(backups_dir, filename, as_attachment=True)


@bp.route('/backups/delete/<path:filename>', methods=['POST'])
@login_required
@admin_required
def delete_backup(filename):
    backups_dir = os.path.join(current_app.instance_path, 'backups')
    path = os.path.join(backups_dir, filename)
    if os.path.isfile(path):
        os.remove(path)
        flash('Backup deleted', 'info')
    else:
        flash('File not found', 'warning')
    return redirect(url_for('admin.list_backups'))


@bp.route('/export/config')
@login_required
@admin_required
def export_config():
    settings = _serialize_queryset(SystemSettings.query.all())
    buf = io.BytesIO(json.dumps(settings, indent=2).encode('utf-8'))
    ts = _dt.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    return send_file(buf, as_attachment=True, download_name=f'system_settings-{ts}.json', mimetype='application/json')


@bp.route('/export/data/create', methods=['POST'])
@login_required
@admin_required
def create_data_export():
    exports_dir = _ensure_dir(os.path.join(current_app.instance_path, 'exports'))
    ts = _dt.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    zip_name = f"export-{ts}.zip"
    zip_path = os.path.join(exports_dir, zip_name)

    mem = io.BytesIO()
    with zipfile.ZipFile(mem, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('users.json', json.dumps(_serialize_queryset(User.query.all()), indent=2))
        zf.writestr('campaigns.json', json.dumps(_serialize_queryset(Campaign.query.all()), indent=2))
        zf.writestr('donations.json', json.dumps(_serialize_queryset(Donation.query.all()), indent=2))
        zf.writestr('kyc.json', json.dumps(_serialize_queryset(KYC.query.all()), indent=2))
        zf.writestr('payment_methods.json', json.dumps(_serialize_queryset(PaymentMethod.query.all()), indent=2))
        zf.writestr('locations.json', json.dumps(_serialize_queryset(Location.query.all()), indent=2))
        zf.writestr('news.json', json.dumps(_serialize_queryset(News.query.all()), indent=2))
        zf.writestr('comments.json', json.dumps(_serialize_queryset(Comment.query.all()), indent=2))
        zf.writestr('notifications.json', json.dumps(_serialize_queryset(Notification.query.all()), indent=2))
        zf.writestr('user_activities.json', json.dumps(_serialize_queryset(UserActivity.query.all()), indent=2))
        zf.writestr('audit_logs.json', json.dumps(_serialize_queryset(AuditLog.query.all()), indent=2))

    with open(zip_path, 'wb') as f:
        f.write(mem.getvalue())

    flash('Data export created', 'success')
    return redirect(url_for('admin.list_exports'))


@bp.route('/exports')
@login_required
@admin_required
def list_exports():
    exports_dir = _ensure_dir(os.path.join(current_app.instance_path, 'exports'))
    files = []
    for name in sorted(os.listdir(exports_dir)):
        path = os.path.join(exports_dir, name)
        if os.path.isfile(path) and name.lower().endswith('.zip'):
            stat = os.stat(path)
            files.append({
                'name': name,
                'size': stat.st_size,
                'modified': _dt.datetime.utcfromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S UTC')
            })
    return render_template('admin/exports.html', files=files)


@bp.route('/exports/download/<path:filename>')
@login_required
@admin_required
def download_export(filename):
    exports_dir = os.path.join(current_app.instance_path, 'exports')
    return send_from_directory(exports_dir, filename, as_attachment=True)


@bp.route('/exports/delete/<path:filename>', methods=['POST'])
@login_required
@admin_required
def delete_export(filename):
    exports_dir = os.path.join(current_app.instance_path, 'exports')
    path = os.path.join(exports_dir, filename)
    if os.path.isfile(path):
        os.remove(path)
        flash('Export deleted', 'info')
    else:
        flash('File not found', 'warning')
    return redirect(url_for('admin.list_exports'))


# ------------------------------------------
# RESTORE / IMPORT PAGES & HANDLERS
# ------------------------------------------
@bp.route('/restore')
@login_required
@admin_required
def restore():
    return render_template('admin/restore.html')


def _parse_dt(val):
    if isinstance(val, str):
        try:
            return _dt.datetime.fromisoformat(val)
        except Exception:
            return val
    return val


def _filter_model_columns(Model, data: dict):
    cols = {c.name for c in Model.__table__.columns}
    out = {}
    for k, v in data.items():
        if k in cols:
            out[k] = _parse_dt(v)
    return out


def _import_rows(Model, rows: list, replace: bool = False):
    if replace:
        Model.query.delete()
    for item in rows:
        payload = _filter_model_columns(Model, item)
        obj = None
        if 'id' in payload:
            obj = Model.query.get(payload['id'])
        if obj:
            for k, v in payload.items():
                setattr(obj, k, v)
        else:
            obj = Model(**payload)
            db.session.add(obj)


def _import_from_json_mapping(files_map: dict, replace: bool = True):
    # Order matters due to FK constraints
    mapping = [
        ('users.json', User),
        ('locations.json', Location),
        ('payment_methods.json', PaymentMethod),
        ('kyc.json', KYC),
        ('campaigns.json', Campaign),
        ('donations.json', Donation),
        ('news.json', News),
        ('comments.json', Comment),
        ('notifications.json', Notification),
        ('user_activities.json', UserActivity),
        ('audit_logs.json', AuditLog),
    ]
    for fname, Model in mapping:
        if fname in files_map:
            rows = json.loads(files_map[fname])
            _import_rows(Model, rows, replace=replace)
    # System settings
    if 'system_settings.json' in files_map:
        rows = json.loads(files_map['system_settings.json'])
        for item in rows:
            key = item.get('key')
            if not key:
                continue
            setting = SystemSettings.query.filter_by(key=key).first()
            if setting:
                setting.value = item.get('value')
                setting.is_encrypted = bool(item.get('is_encrypted', False))
            else:
                db.session.add(SystemSettings(
                    key=key,
                    value=item.get('value'),
                    is_encrypted=bool(item.get('is_encrypted', False))
                ))


@bp.route('/restore/backup', methods=['POST'])
@login_required
@admin_required
def restore_backup():
    file = request.files.get('file')
    if not file:
        flash('No file selected', 'warning')
        return redirect(url_for('admin.restore'))
    filename = secure_filename(file.filename)
    if not filename.lower().endswith('.zip'):
        flash('Please upload a .zip backup', 'danger')
        return redirect(url_for('admin.restore'))

    imports_dir = _ensure_dir(os.path.join(current_app.instance_path, 'imports'))
    save_path = os.path.join(imports_dir, filename)
    file.save(save_path)

    with zipfile.ZipFile(save_path, 'r') as zf:
        names = zf.namelist()
        # Prefer DB replacement if possible
        if 'database.sqlite' in names:
            db_path = _abs_db_path()
            if not db_path:
                flash('Cannot restore DB file on non-SQLite configuration. Use data JSON import instead.', 'danger')
                return redirect(url_for('admin.restore'))
            # Backup current DB
            bdir = _ensure_dir(os.path.join(current_app.instance_path, 'backups'))
            ts = _dt.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
            shutil.copyfile(db_path, os.path.join(bdir, f'pre-restore-{ts}.sqlite')) if os.path.exists(db_path) else None
            # Replace DB
            data = zf.read('database.sqlite')
            with open(db_path, 'wb') as out:
                out.write(data)
            try:
                db.session.remove()
                db.engine.dispose()
            except Exception:
                pass
            flash('Database restored from backup. Consider restarting the app.', 'success')
            return redirect(url_for('admin.dashboard'))
        # JSON-based
        files_map = {}
        for name in names:
            if name.endswith('.json'):
                files_map[name] = zf.read(name).decode('utf-8')
        if not files_map:
            flash('Backup zip did not contain database.sqlite or JSON files', 'danger')
            return redirect(url_for('admin.restore'))
        _import_from_json_mapping(files_map, replace=True)
        db.session.commit()
        flash('Backup imported successfully (JSON mode)', 'success')
        return redirect(url_for('admin.dashboard'))


@bp.route('/restore/export', methods=['POST'])
@login_required
@admin_required
def restore_export():
    file = request.files.get('file')
    if not file:
        flash('No file selected', 'warning')
        return redirect(url_for('admin.restore'))
    filename = secure_filename(file.filename)
    if not filename.lower().endswith('.zip'):
        flash('Please upload a .zip export', 'danger')
        return redirect(url_for('admin.restore'))

    imports_dir = _ensure_dir(os.path.join(current_app.instance_path, 'imports'))
    save_path = os.path.join(imports_dir, filename)
    file.save(save_path)

    with zipfile.ZipFile(save_path, 'r') as zf:
        files_map = {}
        for name in zf.namelist():
            if name.endswith('.json'):
                files_map[name] = zf.read(name).decode('utf-8')
    if not files_map:
        flash('Export zip did not contain JSON files', 'danger')
        return redirect(url_for('admin.restore'))
    _import_from_json_mapping(files_map, replace=True)
    db.session.commit()
    flash('Data export imported successfully', 'success')
    return redirect(url_for('admin.dashboard'))


@bp.route('/restore/settings', methods=['POST'])
@login_required
@admin_required
def restore_settings():
    file = request.files.get('file')
    if not file:
        flash('No file selected', 'warning')
        return redirect(url_for('admin.restore'))
    filename = secure_filename(file.filename)
    if not filename.lower().endswith('.json'):
        flash('Please upload a JSON settings file', 'danger')
        return redirect(url_for('admin.restore'))

    data = file.read().decode('utf-8')
    try:
        rows = json.loads(data)
        for item in rows:
            key = item.get('key')
            if not key:
                continue
            setting = SystemSettings.query.filter_by(key=key).first()
            if setting:
                setting.value = item.get('value')
                setting.is_encrypted = bool(item.get('is_encrypted', False))
            else:
                db.session.add(SystemSettings(
                    key=key,
                    value=item.get('value'),
                    is_encrypted=bool(item.get('is_encrypted', False))
                ))
        db.session.commit()
        flash('Settings imported successfully', 'success')
    except Exception as e:
        flash(f'Failed to import settings: {e}', 'danger')
    return redirect(url_for('admin.system_settings'))


# ------------------------------------------
# NOTIFICATION MANAGEMENT
# ------------------------------------------
@bp.route('/notifications')
@login_required
@admin_required
def manage_notifications():
    """Manage system notifications"""
    page = request.args.get('page', 1, type=int)
    notifications = Notification.query.order_by(Notification.created_at.desc())\
                                    .paginate(page=page, per_page=50, error_out=False)
    
    return render_template('admin/notifications.html', notifications=notifications)


@bp.route('/send-notification', methods=['POST'])
@login_required
@admin_required
def send_notification():
    """Send notification to users"""
    user_ids = request.form.getlist('user_ids')
    title = request.form.get('title')
    message = request.form.get('message')
    notification_type = request.form.get('type', 'info')
    send_email = request.form.get('send_email') in ['on','true','1']
    from_name = request.form.get('from_name') or current_app.config.get('PLATFORM_NAME', 'Helping Hand Together')
    from_email = request.form.get('from_email') or None
    
    if 'all_users' in user_ids:
        users = User.query.all()
    else:
        ids = [int(uid) for uid in user_ids if uid.isdigit()]
        users = User.query.filter(User.id.in_(ids)).all() if ids else []
    
    for user in users:
        NotificationManager.create_notification(
            user.id, title, message, notification_type
        )
    
    if send_email and users:
        mail = current_app.extensions['mail']
        default_sender = current_app.config.get('MAIL_DEFAULT_SENDER')
        for user in users:
            try:
                msg = Message(subject=f"[{from_name}] {title}",
                              recipients=[user.email],
                              body=message,
                              sender=((from_name, from_email) if from_email else default_sender))
                if from_email:
                    msg.reply_to = from_email
                mail.send(msg)
            except Exception as e:
                # Fallback to default sender
                try:
                    msg.sender = default_sender
                    mail.send(msg)
                except Exception as e2:
                    current_app.logger.warning(f"Failed to email {user.email}: {e2}")
    
    flash(f'Notification sent to {len(users)} users{" and emailed" if send_email else ""}', 'success')
    return redirect(url_for('admin.manage_notifications'))
