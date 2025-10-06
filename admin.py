
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from flask_mail import Message
from functools import wraps
from werkzeug.utils import secure_filename
from models import db, User, Campaign, KYC, News, PaymentMethod, Location, Donation
from forms import NewsForm, PaymentMethodForm, LocationForm, AppreciationForm
import os
from datetime import datetime

bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

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
    
    recent_donations = Donation.query.order_by(Donation.created_at.desc()).limit(10).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_campaigns=total_campaigns,
                         pending_kyc=pending_kyc,
                         pending_campaigns=pending_campaigns,
                         total_donations=total_donations,
                         total_raised=total_raised,
                         recent_donations=recent_donations,
                         recent_users=recent_users)

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
    
    status = 'published' if campaign.published else 'unpublished'
    flash(f'Campaign "{campaign.title}" {status}', 'success')
    return redirect(url_for('admin.campaigns'))

@bp.route('/campaign/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_campaign(id):
    campaign = Campaign.query.get_or_404(id)
    title = campaign.title
    db.session.delete(campaign)
    db.session.commit()
    flash(f'Campaign "{title}" deleted', 'success')
    return redirect(url_for('admin.campaigns'))

@bp.route('/news', methods=['GET', 'POST'])
@login_required
@admin_required
def news():
    form = NewsForm()
    
    if form.validate_on_submit():
        news = News(
            title=form.title.data,
            content=form.content.data,
            author_id=current_user.id
        )
        
        if form.image.data:
            file = form.image.data
            filename = secure_filename(f"news_{datetime.utcnow().timestamp()}_{file.filename}")
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'news', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)
            news.image = f'/static/uploads/news/{filename}'
        
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
    flash('News deleted', 'success')
    return redirect(url_for('admin.news'))

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
        
        # Store type-specific fields
        if form.type.data == 'crypto':
            pm.crypto_wallet_address = form.crypto_wallet_address.data
            pm.crypto_currency = form.crypto_currency.data
        elif form.type.data == 'bank':
            pm.bank_name = form.bank_name.data
            pm.account_name = form.account_name.data
            pm.account_number = form.account_number.data
            pm.routing_number = form.routing_number.data
            pm.bank_address = form.bank_address.data
        elif form.type.data == 'paypal':
            pm.paypal_client_id = form.paypal_client_id.data
            pm.paypal_secret = form.paypal_secret.data
            pm.paypal_mode = form.paypal_mode.data
        elif form.type.data == 'paystack':
            pm.paystack_public_key = form.paystack_public_key.data
            pm.paystack_secret_key = form.paystack_secret_key.data
        
        db.session.add(pm)
        db.session.commit()
        flash('Payment method added successfully!', 'success')
        return redirect(url_for('admin.payment_methods'))
    
    methods = PaymentMethod.query.all()
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

@bp.route('/locations', methods=['GET', 'POST'])
@login_required
@admin_required
def locations():
    form = LocationForm()
    
    if form.validate_on_submit():
        location = Location(
            name=form.name.data,
            country=form.country.data
        )
        db.session.add(location)
        db.session.commit()
        flash('Location added', 'success')
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

@bp.route('/appreciate/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def appreciate_user(user_id):
    user = User.query.get_or_404(user_id)
    form = AppreciationForm()
    
    if form.validate_on_submit():
        from flask_mail import Mail
        mail = Mail(current_app)
        
        msg = Message(
            subject='Appreciation from Helping Hand Together',
            recipients=[user.email],
            body=form.message.data
        )
        
        try:
            mail.send(msg)
            flash(f'Appreciation email sent to {user.name}', 'success')
        except Exception as e:
            flash(f'Failed to send email: {str(e)}', 'danger')
        
        return redirect(url_for('admin.users'))
    
    return render_template('admin/appreciate.html', user=user, form=form)

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
    
    if donation.status == 'pending' and donation.payment_method == 'bank':
        donation.status = 'completed'
        campaign = donation.campaign
        campaign.raised_amount += donation.amount
        db.session.commit()
        flash('Donation confirmed', 'success')
    else:
        flash('Cannot confirm this donation', 'warning')
    
    return redirect(url_for('admin.donations'))
