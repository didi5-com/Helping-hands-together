
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, FloatField, SelectField, DateField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember me')
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    name = StringField('Full name', validators=[DataRequired(), Length(min=2, max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class KYCForm(FlaskForm):
    id_type = SelectField('ID Type', choices=[('passport', 'Passport'), ('driver_license', 'Driver License'), ('national_id', 'National ID')], validators=[DataRequired()])
    document = FileField('KYC Document (JPG, PNG, PDF)', validators=[FileRequired(), FileAllowed(['jpg', 'png', 'pdf'], 'Images and PDFs only!')])
    submit = SubmitField('Submit KYC')

class CampaignForm(FlaskForm):
    title = StringField('Campaign Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[DataRequired()])
    goal_amount = FloatField('Goal Amount ($)', validators=[DataRequired(), NumberRange(min=1)])
    location = StringField('Location', validators=[DataRequired(), Length(max=120)])
    category = StringField('Category', validators=[Optional(), Length(max=100)])
    end_date = DateField('End Date', validators=[Optional()], format='%Y-%m-%d')
    image = FileField('Campaign Image', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    submit = SubmitField('Create Campaign')

class DonationForm(FlaskForm):
    donor_name = StringField('Your Name', validators=[DataRequired(), Length(max=120)])
    donor_email = StringField('Your Email', validators=[DataRequired(), Email()])
    amount = FloatField('Donation Amount ($)', validators=[DataRequired(), NumberRange(min=1)])
    payment_method = SelectField('Payment Method', choices=[], validators=[DataRequired()])
    anonymous = BooleanField('Make donation anonymous')
    submit = SubmitField('Proceed to Payment')

class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired(), Length(min=1, max=500)])
    submit = SubmitField('Post Comment')

class NewsForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('Content', validators=[DataRequired()])
    image = FileField('Image', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    submit = SubmitField('Publish News')

class PaymentMethodForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=80)])
    type = SelectField('Type', choices=[('paypal', 'PayPal'), ('paystack', 'Paystack'), ('crypto', 'Cryptocurrency'), ('bank', 'Bank Transfer')], validators=[DataRequired()])
    
    # Crypto fields
    crypto_wallet_address = StringField('Crypto Wallet Address', validators=[Optional(), Length(max=200)])
    crypto_currency = SelectField('Cryptocurrency', choices=[('BTC', 'Bitcoin'), ('ETH', 'Ethereum'), ('USDT', 'Tether'), ('BNB', 'Binance Coin')], validators=[Optional()])
    
    # Bank transfer fields
    bank_name = StringField('Bank Name', validators=[Optional(), Length(max=100)])
    account_name = StringField('Account Name', validators=[Optional(), Length(max=100)])
    account_number = StringField('Account Number', validators=[Optional(), Length(max=50)])
    routing_number = StringField('Routing Number / SWIFT Code', validators=[Optional(), Length(max=50)])
    bank_address = TextAreaField('Bank Address', validators=[Optional()])
    
    # PayPal fields
    paypal_client_id = StringField('PayPal Client ID', validators=[Optional(), Length(max=200)])
    paypal_secret = StringField('PayPal Secret Key', validators=[Optional(), Length(max=200)])
    paypal_mode = SelectField('PayPal Mode', choices=[('sandbox', 'Sandbox'), ('live', 'Live')], validators=[Optional()])
    
    # Paystack fields
    paystack_public_key = StringField('Paystack Public Key', validators=[Optional(), Length(max=200)])
    paystack_secret_key = StringField('Paystack Secret Key', validators=[Optional(), Length(max=200)])
    
    details = TextAreaField('Additional Details/Instructions', validators=[Optional()])
    submit = SubmitField('Add Payment Method')

class LocationForm(FlaskForm):
    name = StringField('Location Name', validators=[DataRequired(), Length(max=120)])
    country = StringField('Country', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Add Location')

class AppreciationForm(FlaskForm):
    from_name = StringField('From Name', validators=[Optional(), Length(max=120)])
    from_email = StringField('From Gmail (optional)', validators=[Optional(), Email(), Length(max=200)])
    message = TextAreaField('Appreciation Message', validators=[DataRequired(), Length(min=10, max=1000)])
    submit = SubmitField('Send Appreciation')
