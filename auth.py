
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, KYC, Campaign
from forms import LoginForm, RegistrationForm, KYCForm, CampaignForm
import os
from datetime import datetime

bp = Blueprint('auth', __name__, url_prefix='/auth')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower()).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('auth.register'))
        
        user = User(
            email=form.email.data.lower(),
            name=form.name.data,
            password_hash=generate_password_hash(form.password.data)
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html', form=form)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('main.index'))

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    kyc_form = KYCForm()
    
    if kyc_form.validate_on_submit():
        file = kyc_form.document.data
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{current_user.id}_{datetime.utcnow().timestamp()}_{file.filename}")
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'kyc', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)
            
            if not current_user.kyc:
                kyc = KYC(
                    user_id=current_user.id,
                    document_path=filepath,
                    id_type=kyc_form.id_type.data,
                    status='pending'
                )
                db.session.add(kyc)
            else:
                current_user.kyc.document_path = filepath
                current_user.kyc.id_type = kyc_form.id_type.data
                current_user.kyc.status = 'pending'
                current_user.kyc.submitted_at = datetime.utcnow()
            
            db.session.commit()
            flash('KYC document submitted successfully! Awaiting verification.', 'success')
            return redirect(url_for('auth.profile'))
    
    campaigns = Campaign.query.filter_by(owner_id=current_user.id).order_by(Campaign.created_at.desc()).all()
    
    return render_template('profile.html', kyc_form=kyc_form, campaigns=campaigns)

@bp.route('/create-campaign', methods=['GET', 'POST'])
@login_required
def create_campaign():
    # Check if user has verified KYC
    if not current_user.kyc or current_user.kyc.status != 'verified':
        flash('You must complete KYC verification before creating a campaign', 'warning')
        return redirect(url_for('auth.profile'))
    
    form = CampaignForm()
    
    if form.validate_on_submit():
        campaign = Campaign(
            title=form.title.data,
            description=form.description.data,
            goal_amount=form.goal_amount.data,
            location=form.location.data,
            category=form.category.data,
            end_date=form.end_date.data,
            owner_id=current_user.id,
            published=False  # Requires admin approval
        )
        
        if form.image.data:
            file = form.image.data
            filename = secure_filename(f"campaign_{datetime.utcnow().timestamp()}_{file.filename}")
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'campaigns', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)
            campaign.image_path = f'/static/uploads/campaigns/{filename}'
        
        db.session.add(campaign)
        db.session.commit()
        
        flash('Campaign created! Awaiting admin approval.', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('create_campaign.html', form=form)
