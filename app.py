from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_required, current_user
from flask_mail import Mail, Message
from flask_migrate import Migrate
from config import Config
from models import db, User, Campaign, Donation, News, Comment, PaymentMethod, Location
from forms import DonationForm, CommentForm
import os

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)

login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Ensure upload folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'kyc'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'campaigns'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'news'), exist_ok=True)

# Register blueprints
from auth import bp as auth_bp
app.register_blueprint(auth_bp)

from admin import bp as admin_bp
app.register_blueprint(admin_bp)

# Create blueprint for main routes
from flask import Blueprint
main_bp = Blueprint('main', __name__)

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
    form.payment_method.choices = [(pm.type, pm.name) for pm in payment_methods]

    recent_donations = Donation.query.filter_by(
        campaign_id=campaign.id, 
        status='completed'
    ).order_by(Donation.created_at.desc()).limit(10).all()

    return render_template('campaign.html', 
                         campaign=campaign, 
                         form=form,
                         recent_donations=recent_donations)

@main_bp.route('/donate/<int:campaign_id>', methods=['POST'])
def donate(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    form = DonationForm()

    payment_methods = PaymentMethod.query.filter_by(active=True).all()
    form.payment_method.choices = [(pm.type, pm.name) for pm in payment_methods]

    if form.validate_on_submit():
        from payments import get_payment_processor

        donation = Donation(
            campaign_id=campaign_id,
            donor_email=form.donor_email.data,
            donor_name=form.donor_name.data,
            amount=form.amount.data,
            payment_method=form.payment_method.data,
            anonymous=form.anonymous.data,
            status='pending'
        )
        db.session.add(donation)
        db.session.commit()

        # Process payment based on method
        payment_method = form.payment_method.data

        if payment_method == 'paypal':
            processor = get_payment_processor('paypal')
            result = processor.create_order(
                amount=form.amount.data,
                return_url=url_for('main.paypal_success', donation_id=donation.id, _external=True),
                cancel_url=url_for('main.donation_cancel', donation_id=donation.id, _external=True)
            )
            if 'approval_url' in result:
                donation.transaction_id = result['order_id']
                db.session.commit()
                return redirect(result['approval_url'])
            else:
                flash('Payment initialization failed', 'danger')

        elif payment_method == 'paystack':
            processor = get_payment_processor('paystack')
            result = processor.initialize_transaction(
                email=form.donor_email.data,
                amount=form.amount.data,
                reference=f'DON-{donation.id}',
                callback_url=url_for('main.paystack_callback', _external=True)
            )
            if 'authorization_url' in result:
                donation.transaction_id = result['reference']
                db.session.commit()
                return redirect(result['authorization_url'])
            else:
                flash('Payment initialization failed', 'danger')

        elif payment_method == 'crypto':
            processor = get_payment_processor('crypto')
            result = processor.create_charge(
                name=f'Donation to {campaign.title}',
                description=f'Donation by {form.donor_name.data}',
                amount=form.amount.data,
                metadata={'donation_id': donation.id, 'campaign_id': campaign_id}
            )
            if 'hosted_url' in result:
                donation.transaction_id = result['charge_id']
                db.session.commit()
                return redirect(result['hosted_url'])
            else:
                flash('Payment initialization failed', 'danger')

        elif payment_method == 'bank':
            # For bank transfer, show instructions
            flash('Please complete your bank transfer. Admin will verify and confirm your donation.', 'info')
            return redirect(url_for('main.bank_transfer_instructions', donation_id=donation.id))

    return redirect(url_for('main.campaign_detail', id=campaign_id))

@main_bp.route('/paypal/success')
def paypal_success():
    donation_id = request.args.get('donation_id')
    token = request.args.get('token')

    if donation_id and token:
        from payments import PayPalPayment
        donation = Donation.query.get(donation_id)
        if donation:
            processor = PayPalPayment()
            result = processor.capture_order(token)

            if 'error' not in result and result.get('status') == 'COMPLETED':
                donation.status = 'completed'
                campaign = donation.campaign
                campaign.raised_amount += donation.amount
                db.session.commit()

                flash('Thank you for your donation!', 'success')
                return redirect(url_for('main.donation_success'))

    flash('Payment verification failed', 'danger')
    return redirect(url_for('main.index'))

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
                campaign = donation.campaign
                campaign.raised_amount += donation.amount
                db.session.commit()

                flash('Thank you for your donation!', 'success')
                return redirect(url_for('main.donation_success'))

    flash('Payment verification failed', 'danger')
    return redirect(url_for('main.index'))

@main_bp.route('/donation/success')
def donation_success():
    return render_template('donation_success.html')

@main_bp.route('/donation/cancel/<int:donation_id>')
def donation_cancel(donation_id):
    donation = Donation.query.get(donation_id)
    if donation:
        donation.status = 'cancelled'
        db.session.commit()
    flash('Donation cancelled', 'info')
    return redirect(url_for('main.index'))

@main_bp.route('/bank-transfer/<int:donation_id>')
def bank_transfer_instructions(donation_id):
    donation = Donation.query.get_or_404(donation_id)
    bank_method = PaymentMethod.query.filter_by(type='bank', active=True).first()
    return render_template('bank_transfer.html', donation=donation, bank_method=bank_method)

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
        comment = Comment(
            news_id=news.id,
            user_id=current_user.id,
            content=form.content.data
        )
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

app.register_blueprint(main_bp)

# Webhooks
@app.route('/webhooks/coinbase', methods=['POST'])
def coinbase_webhook():
    from payments import CoinbaseCommercePayment

    signature = request.headers.get('X-CC-Webhook-Signature')
    body = request.data

    processor = CoinbaseCommercePayment()
    if processor.verify_webhook(signature, body):
        event = request.json

        if event['type'] == 'charge:confirmed':
            charge_id = event['data']['id']
            metadata = event['data'].get('metadata', {})
            donation_id = metadata.get('donation_id')

            if donation_id:
                donation = Donation.query.get(donation_id)
                if donation and donation.status == 'pending':
                    donation.status = 'completed'
                    campaign = donation.campaign
                    campaign.raised_amount += donation.amount
                    db.session.commit()

        return jsonify({'status': 'success'}), 200

    return jsonify({'status': 'invalid'}), 400

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
                campaign = donation.campaign
                campaign.raised_amount += donation.amount
                db.session.commit()

        return jsonify({'status': 'success'}), 200

    return jsonify({'status': 'invalid'}), 400

if __name__ == "__main__":
    from models import db

    with app.app_context():
        db.create_all()
        print("✅ All database tables created successfully!")

    app.run(host="0.0.0.0", port=5000)
