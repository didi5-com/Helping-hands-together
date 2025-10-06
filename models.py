
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(120))
    is_admin = db.Column(db.Boolean, default=False)
    profile_image = db.Column(db.String(256))
    email_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    kyc = db.relationship('KYC', backref='user', uselist=False, cascade='all, delete-orphan')
    campaigns = db.relationship('Campaign', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.email}>'

class KYC(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    document_path = db.Column(db.String(256))
    id_type = db.Column(db.String(50))  # passport, driver_license, national_id
    status = db.Column(db.String(32), default='pending')  # pending/verified/rejected
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_at = db.Column(db.DateTime)

class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    goal_amount = db.Column(db.Float, default=0.0)
    raised_amount = db.Column(db.Float, default=0.0)
    image = db.Column(db.String(256))
    published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    location = db.Column(db.String(120))
    category = db.Column(db.String(100))

    donations = db.relationship('Donation', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')

    def progress_percentage(self):
        if self.goal_amount > 0:
            return min(int((self.raised_amount / self.goal_amount) * 100), 100)
        return 0

class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    donor_email = db.Column(db.String(120))
    donor_name = db.Column(db.String(120))
    amount = db.Column(db.Float)
    payment_method = db.Column(db.String(64))
    transaction_id = db.Column(db.String(200))
    status = db.Column(db.String(32), default='pending')  # pending/completed/failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    anonymous = db.Column(db.Boolean, default=False)

class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    image = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    author = db.relationship('User', backref='news_posts')
    comments = db.relationship('Comment', backref='news', lazy='dynamic', cascade='all, delete-orphan')

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    news_id = db.Column(db.Integer, db.ForeignKey('news.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PaymentMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    type = db.Column(db.String(40), nullable=False)  # paypal/paystack/crypto/bank
    details = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    country = db.Column(db.String(100))
    active = db.Column(db.Boolean, default=True)
