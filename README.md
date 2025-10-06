
# Helping Hand Together - Charity Crowdfunding Platform

A comprehensive Flask-based crowdfunding platform for charity campaigns with integrated payment gateways (PayPal, Paystack, Coinbase Commerce, Bank Transfer).

## Features

### User Features
- User registration and authentication
- Profile management with KYC verification
- Browse and search campaigns
- Multiple payment options for donations
- Read news and comment
- Create campaigns (after KYC verification)
- Track personal campaigns and donations

### Admin Features
- Comprehensive admin dashboard
- User management
- KYC verification approval/rejection
- Campaign moderation (approve/reject)
- News management
- Payment method configuration
- Location management
- Send appreciation emails to users
- Donation tracking and management

### Payment Integration
- **PayPal**: Full integration with order creation and capture
- **Paystack**: Transaction initialization and verification
- **Coinbase Commerce**: Cryptocurrency payments via hosted checkout
- **Bank Transfer**: Manual confirmation by admin

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials:

```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///hht.db  # Or PostgreSQL connection string

# Mail Settings
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Payment Gateway Keys
PAYPAL_CLIENT_ID=your-paypal-client-id
PAYPAL_SECRET=your-paypal-secret
PAYPAL_MODE=sandbox  # or 'live' for production

PAYSTACK_SECRET_KEY=sk_test_your-secret-key
PAYSTACK_PUBLIC_KEY=pk_test_your-public-key

COINBASE_API_KEY=your-coinbase-api-key
COINBASE_WEBHOOK_SECRET=your-webhook-secret
```

### 3. Initialize Database

```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 4. Create Admin User

Run Python shell:

```bash
python
```

Then execute:

```python
from main import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    admin = User(
        email='admin@example.com',
        name='Admin User',
        password_hash=generate_password_hash('admin123'),
        is_admin=True,
        email_verified=True
    )
    db.session.add(admin)
    db.session.commit()
    print("Admin user created!")
```

### 5. Run the Application

```bash
python main.py
```

The application will be available at `http://0.0.0.0:5000`

## Payment Gateway Setup

### PayPal
1. Create a PayPal Developer account at https://developer.paypal.com
2. Create a REST API app to get Client ID and Secret
3. Use sandbox credentials for testing

### Paystack
1. Sign up at https://paystack.com
2. Get your test keys from the dashboard
3. Set up webhook URL: `https://your-domain.com/webhooks/paystack`

### Coinbase Commerce
1. Create account at https://commerce.coinbase.com
2. Get API key from Settings > API Keys
3. Set up webhook: `https://your-domain.com/webhooks/coinbase`

## Project Structure

```
helping-hand-together/
├── main.py                 # Main application entry point
├── config.py               # Configuration settings
├── models.py               # Database models
├── forms.py                # WTForms definitions
├── auth.py                 # Authentication blueprint
├── admin.py                # Admin blueprint
├── payments.py             # Payment gateway integrations
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
├── templates/              # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── campaign.html
│   ├── admin/              # Admin templates
│   └── ...
└── static/
    └── uploads/            # User-uploaded files
        ├── kyc/
        ├── campaigns/
        └── news/
```

## Security Considerations

1. **Never commit `.env` file** - Keep credentials secure
2. **Use HTTPS in production** - Especially for payment processing
3. **Enable CSRF protection** - Already configured via Flask-WTF
4. **Validate file uploads** - File type and size restrictions in place
5. **Use strong SECRET_KEY** - Generate with `python -c "import secrets; print(secrets.token_hex(32))"`
6. **Verify payment webhooks** - Signature verification implemented

## Production Deployment on Replit

1. Set environment variables in Replit Secrets tool
2. Configure PostgreSQL database (recommended for production)
3. Set up custom domain
4. Enable SSL/HTTPS
5. Configure email service (SendGrid, Mailgun, etc.)

## Support

For issues or questions, contact support@helpinghandtogether.org

## License

MIT License - See LICENSE file for details
