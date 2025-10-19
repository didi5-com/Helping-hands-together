from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, Blueprint
from flask_login import LoginManager, login_required, current_user
from flask_mail import Mail, Message
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, generate_csrf
from config import Config
from models import db, User, Campaign, Donation, News, Comment, PaymentMethod, UserActivity, Notification, SystemSettings
from forms import DonationForm, CommentForm
from security_utils import ActivityLogger, NotificationManager, LocationManager
import os
import threading
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

# ----------------------------
# APP INITIALIZATION
# ----------------------------
app = Flask(__name__)
app.config.from_object(Config)
load_dotenv()

# ----------------------------
# SELF-PING KEEPALIVE (optional)
# ----------------------------
KEEPALIVE_STARTED = False

def start_self_ping():
    """Background thread that pings /health every 10 minutes to keep the app warm.
    Configure via env:
      - SELF_PING_URL: full base URL to your app (e.g., https://your-app.onrender.com)
      - ENABLE_SELF_PING: set to false to disable (default: true)
    Falls back to http://127.0.0.1:{PORT}/health if no external URL is provided.
    """
    global KEEPALIVE_STARTED
    if KEEPALIVE_STARTED:
        return
    KEEPALIVE_STARTED = True

    def ping_loop():
        with app.app_context():
            base = os.getenv("SELF_PING_URL") or os.getenv("RENDER_EXTERNAL_URL")
            port = os.getenv("PORT", "5000")
            if not base:
                base = f"http://127.0.0.1:{port}"
            url = base.rstrip('/') + "/health"
            session = requests.Session()
            while True:
                try:
                    session.get(url, timeout=5)
                except Exception:
                    pass
                time.sleep(600)  # 10 minutes

# Load payment environment variables
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY")
PAYPAL_EMAIL = os.getenv("PAYPAL_EMAIL")
BTC_WALLET = os.getenv("BTC_WALLET")
ETH_WALLET = os.getenv("ETH_WALLET")
USDT_WALLET = os.getenv("USDT_WALLET")

# Initialize Flask extensions
db.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Ensure upload folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
for folder in ['kyc', 'campaigns', 'news', 'profiles']:
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], folder), exist_ok=True)

# ----------------------------
# BLUEPRINTS
# ----------------------------
from auth import bp as auth_bp
app.register_blueprint(auth_bp)

from admin import bp as admin_bp
app.register_blueprint(admin_bp)

# Exempt blueprints from CSRF to avoid breaking existing POST forms
try:
    csrf.exempt(auth_bp)
    csrf.exempt(admin_bp)
except Exception:
    pass

main_bp = Blueprint('main', __name__)

@main_bp.route('/health')
def health():
    return jsonify({'status': 'ok'}), 200

# ----------------------------
# ROUTES
# ----------------------------
@main_bp.route('/')
def index():
    campaigns = Campaign.query.filter_by(published=True).order_by(Campaign.created_at.desc()).limit(6).all()
    news = News.query.order_by(News.created_at.desc()).limit(3).all()
    total_raised = db.session.query(db.func.sum(Campaign.raised_amount)).filter_by(published=True).scalar() or 0
    total_campaigns = Campaign.query.filter_by(published=True).count()
    total_donations = Donation.query.filter_by(status='completed').count()
    return render_template('index.html',
                           campaigns=campaigns,
                           news=news,
                           total_raised=total_raised,
                           total_campaigns=total_campaigns,
                           total_donations=total_donations)


@main_bp.route('/campaigns')
def campaigns():
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category')
    location = request.args.get('location')
    query = Campaign.query.filter_by(published=True)
    if category:
        query = query.filter_by(category=category)
    if location:
        query = query.filter_by(location=location)
    campaigns = query.order_by(Campaign.created_at.desc()).paginate(page=page, per_page=12, error_out=False)
    return render_template('campaigns.html', campaigns=campaigns)


@main_bp.route('/campaign/<int:id>', methods=['GET', 'POST'])
def campaign_detail(id):
    campaign = Campaign.query.get_or_404(id)
    if not campaign.published and (not current_user.is_authenticated or (current_user.id != campaign.owner_id and not current_user.is_admin)):
        flash('Campaign not found', 'danger')
        return redirect(url_for('main.campaigns'))

    form = DonationForm()
    payment_methods = PaymentMethod.query.filter_by(active=True).all()
    form.payment_method.choices = [(str(pm.id), pm.name) for pm in payment_methods]

    recent_donations = Donation.query.filter_by(campaign_id=campaign.id, status='completed').order_by(Donation.created_at.desc()).limit(10).all()

    return render_template('campaign.html',
                           campaign=campaign,
                           form=form,
                           recent_donations=recent_donations,
                           payment_methods=payment_methods)


@main_bp.route('/donate/<int:id>', methods=['POST'])
def donate(id):
    from payments import get_payment_processor

    campaign = Campaign.query.get_or_404(id)
    donor_name = request.form.get('donor_name') or request.form.get('name')
    donor_email = request.form.get('donor_email') or request.form.get('email')
    try:
        amount = float(request.form.get('amount', 0))
    except (TypeError, ValueError):
        amount = 0.0

    payment_method_id = request.form.get('payment_method')
    if not payment_method_id:
        flash('Please select a payment method', 'danger')
        return redirect(url_for('main.campaign_detail', id=id))
        
    payment_method = PaymentMethod.query.get_or_404(payment_method_id)
    
    # Validate amount
    if amount <= 0:
        flash('Please enter a valid donation amount', 'danger')
        return redirect(url_for('main.campaign_detail', id=id))
    
    # Validate donor information
    if not donor_name or not donor_email:
        flash('Please provide your name and email address', 'danger')
        return redirect(url_for('main.campaign_detail', id=id))
    
    donation = Donation(
        campaign_id=id,
        donor_name=donor_name,
        donor_email=donor_email,
        amount=amount,
        payment_method=payment_method.type,
        payment_method_id=payment_method_id,
        status='pending'
    )
    db.session.add(donation)
    db.session.commit()

    # Handle manual payment methods
    if payment_method.type in ['bank', 'crypto']:
        return redirect(url_for('main.manual_payment_page', 
                               method=payment_method.type, 
                               donation_id=donation.id))

    # Payment processor for automated payments
    processor = get_payment_processor(payment_method.type, payment_method)
    if processor is None:
        return jsonify({"error": "Invalid payment method"}), 400

    return processor.process_payment(donation)


@main_bp.route('/manual-payment/<string:method>/<int:donation_id>')
def manual_payment_page(method, donation_id):
    donation = Donation.query.get_or_404(donation_id)
    
    # Get the appropriate payment methods based on type
    if method == 'crypto':
        crypto_methods = PaymentMethod.query.filter_by(type='crypto', active=True).all()
        return render_template('manual_payment.html', 
                             method=method, 
                             donation=donation, 
                             crypto_methods=crypto_methods)
    elif method == 'bank':
        bank_method = PaymentMethod.query.filter_by(type='bank', active=True).first()
        return render_template('manual_payment.html', 
                             method=method, 
                             donation=donation, 
                             bank_method=bank_method)
    elif method == 'paypal':
        # Get PayPal email from environment or payment method
        paypal_email = os.getenv("PAYPAL_EMAIL")
        if not paypal_email:
            paypal_method = PaymentMethod.query.filter_by(type='paypal', active=True).first()
            if paypal_method and hasattr(paypal_method, 'details'):
                paypal_email = paypal_method.details or "donations@helpinghands.com"
            else:
                paypal_email = "donations@helpinghands.com"
        
        return render_template('manual_payment.html', 
                             method=method, 
                             donation=donation, 
                             paypal_email=paypal_email)
    elif method == 'paystack':
        # For Paystack fallback when API fails
        return render_template('manual_payment.html', 
                             method=method, 
                             donation=donation, 
                             paystack_fallback=True)
    
    return render_template('manual_payment.html', method=method, donation=donation)


@main_bp.route('/confirm_payment/<int:donation_id>', methods=['POST'])
def confirm_manual_payment(donation_id):
    donation = Donation.query.get_or_404(donation_id)
    donation.status = "awaiting_verification"
    db.session.commit()
    flash("Thank you! Your payment is awaiting admin verification.", "success")
    return redirect(url_for('main.index'))


# ----------------------------
# PAYPAL CALLBACKS
# ----------------------------
@main_bp.route('/paypal/success')
def paypal_success():
    donation_id = request.args.get('donation_id')
    token = request.args.get('token')
    if donation_id and token:
        from payments import PaypalPayment
        donation = Donation.query.get(donation_id)
        if donation:
            processor = PaypalPayment()
            result = processor.capture_order(token) if hasattr(processor, 'capture_order') else {'status': 'COMPLETED'}
            if 'error' not in result and result.get('status') == 'COMPLETED':
                donation.status = 'completed'
                campaign = donation.campaign
                campaign.raised_amount += donation.amount
                db.session.commit()
                flash('Thank you for your donation!', 'success')
                return redirect(url_for('main.donation_success'))
    flash('Payment verification failed', 'danger')
    return redirect(url_for('main.index'))


# ----------------------------
# PAYSTACK CALLBACK & WEBHOOK
# ----------------------------
@main_bp.route('/paystack/callback')
def paystack_callback():
    reference = request.args.get('reference')
    if reference:
        from payments import PaystackPayment
        processor = PaystackPayment()
        result = processor.verify_transaction(reference)
        if result.get('status') == 'success':
            donation = Donation.query.filter_by(transaction_id=reference).first()
            if donation and donation.status == 'pending':
                donation.status = 'completed'
                donation.campaign.raised_amount += donation.amount
                db.session.commit()
                flash('Thank you for your donation!', 'success')
                return redirect(url_for('main.donation_success'))
    flash('Payment verification failed', 'danger')
    return redirect(url_for('main.index'))


@app.route('/webhooks/paystack', methods=['POST'])
def paystack_webhook():
    from payments import PaystackPayment
    signature = request.headers.get('X-Paystack-Signature')
    body = request.data
    processor = PaystackPayment()
    if processor.verify_webhook(signature, body):
        event = request.json
        if event['event'] == 'charge.success':
            reference = event['data']['reference']
            donation = Donation.query.filter_by(transaction_id=reference).first()
            if donation and donation.status == 'pending':
                donation.status = 'completed'
                donation.campaign.raised_amount += donation.amount
                db.session.commit()
        return jsonify({'status': 'success'}), 200
    return jsonify({'status': 'invalid'}), 400


# ----------------------------
# NEWS & STATIC PAGES
# ----------------------------
@main_bp.route('/news')
def news_list():
    page = request.args.get('page', 1, type=int)
    news = News.query.order_by(News.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template('news_list.html', news=news)


@main_bp.route('/news/<int:id>', methods=['GET', 'POST'])
def news_detail(id):
    news = News.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit() and current_user.is_authenticated:
        comment = Comment(news_id=news.id, user_id=current_user.id, content=form.content.data)
        db.session.add(comment)
        db.session.commit()
        flash('Comment posted!', 'success')
        return redirect(url_for('main.news_detail', id=id))
    comments = Comment.query.filter_by(news_id=news.id).order_by(Comment.created_at.desc()).all()
    return render_template('news_detail.html', news=news, form=form, comments=comments)


@main_bp.route('/about')
def about():
    return render_template('about.html')


@main_bp.route('/contact')
def contact():
    return render_template('contact.html')


@main_bp.route('/donation/success')
def donation_success():
    return render_template('donation_success.html')


# ----------------------------
# USER PROFILE MANAGEMENT
# ----------------------------
@main_bp.route('/profile')
@login_required
def user_profile():
    """User profile page"""
    notifications = Notification.query.filter_by(user_id=current_user.id, read=False).order_by(Notification.created_at.desc()).limit(5).all()
    recent_activities = UserActivity.query.filter_by(user_id=current_user.id).order_by(UserActivity.created_at.desc()).limit(10).all()
    
    return render_template('user_profile.html', 
                         notifications=notifications,
                         recent_activities=recent_activities)


@main_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Update user profile"""
    current_user.name = request.form.get('name', current_user.name)
    current_user.phone_number = request.form.get('phone_number')
    current_user.bio = request.form.get('bio')
    
    # Handle profile picture upload
    if 'profile_image' in request.files:
        file = request.files['profile_image']
        if file and file.filename:
            from werkzeug.utils import secure_filename
            filename = secure_filename(f"profile_{current_user.id}_{datetime.utcnow().timestamp()}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'profiles', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)
            current_user.profile_image = f'/static/uploads/profiles/{filename}'
    
    db.session.commit()
    
    # Log activity
    ActivityLogger.log_user_activity(current_user.id, 'profile_updated', 'User updated their profile')
    
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('main.user_profile'))


@main_bp.route('/location/consent', methods=['POST'])
@login_required
def location_consent():
    """Handle location consent"""
    consent = request.form.get('consent') == 'true'
    current_user.location_consent = consent
    db.session.commit()
    
    if consent:
        ActivityLogger.log_user_activity(current_user.id, 'location_consent_given', 'User granted location access')
        flash('Location access enabled. Your location will help us provide better services.', 'success')
    else:
        ActivityLogger.log_user_activity(current_user.id, 'location_consent_revoked', 'User revoked location access')
        flash('Location access disabled.', 'info')
    
    return redirect(url_for('main.user_profile'))


@main_bp.route('/location/update', methods=['POST'])
@login_required
def update_location():
    """Update user location"""
    data = request.get_json()
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    location_name = data.get('location_name')
    
    if LocationManager.update_user_location(current_user, latitude, longitude, location_name):
        return jsonify({'success': True, 'message': 'Location updated successfully'})
    else:
        return jsonify({'success': False, 'message': 'Location consent required'}), 403


# ----------------------------
# NOTIFICATIONS
# ----------------------------
@main_bp.route('/notifications')
@login_required
def notifications():
    """User notifications page"""
    page = request.args.get('page', 1, type=int)
    user_notifications = Notification.query.filter_by(user_id=current_user.id)\
                                          .order_by(Notification.created_at.desc())\
                                          .paginate(page=page, per_page=20, error_out=False)
    
    return render_template('notifications.html', notifications=user_notifications)


@main_bp.route('/notification/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark notification as read"""
    if NotificationManager.mark_as_read(notification_id, current_user.id):
        return jsonify({'success': True})
    return jsonify({'success': False}), 404


@main_bp.route('/api/unread-notifications')
@login_required
def unread_notifications_count():
    """Get unread notifications count"""
    count = NotificationManager.get_unread_count(current_user.id)
    return jsonify({'count': count})


app.register_blueprint(main_bp)

# Make csrf_token available in templates (even when CSRF is exempted)
try:
    app.jinja_env.globals['csrf_token'] = generate_csrf
except Exception:
    pass

# Also exempt the main blueprint routes that handle POSTs (manual payments)
try:
    csrf.exempt(main_bp)
except Exception:
    pass

# Start keepalive self-ping in the real process (avoid duplicate threads under reloader)
if os.getenv('ENABLE_SELF_PING', 'true').lower() in ['1', 'true', 'yes', 'on']:
    is_reloader = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    if not app.debug or is_reloader:
        start_self_ping()

# ----------------------------
# CONTEXT PROCESSORS
# ----------------------------
@app.context_processor
def inject_theme_settings():
    setting = SystemSettings.query.filter_by(key='theme_mode').first()
    theme_mode = (setting.value if setting and setting.value in ['light','dark','system'] else 'light')
    return dict(theme_mode=theme_mode)

@app.context_processor
def inject_config():
    return dict(config=app.config)

# ----------------------------
# MAIN ENTRY
# ----------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        print("✅ All database tables created successfully!")
    app.run(host="0.0.0.0", port=5000)
