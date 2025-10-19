# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Core Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

# Create admin user (first time setup)
python scripts/create_admin.py
```

### Database Management
```bash
# Initialize database
flask db init
flask db migrate -m "Migration message"
flask db upgrade

# Create tables programmatically
python -c "from main import app, db; from models import *; app.app_context().push(); db.create_all(); print('Tables created')"
```

### Testing
```bash
# Run tests (if test files exist)
python test_payments.py
```

### Linting & Code Quality
```bash
# Using pyproject.toml configuration
ruff check .  # For linting
pyright .     # For type checking (if configured)
```

## Architecture Overview

### Core Application Structure
This is a **Flask-based charity crowdfunding platform** built with a modular blueprint architecture:

- **main.py**: Main application entry point with core routes and self-ping keepalive system
- **config.py**: Configuration management with environment variable support
- **models.py**: SQLAlchemy database models with comprehensive relationships

### Key Blueprints
- **auth.py**: User authentication, registration, KYC verification, campaign creation
- **admin.py**: Admin dashboard with comprehensive management features including emergency recovery
- **payments.py**: Multi-gateway payment processing (PayPal, Paystack, Coinbase, Bank Transfer)

### Database Architecture
The platform uses a sophisticated relational model:

**Core Entities:**
- `User` → `KYC` (one-to-one) → `Campaign` (one-to-many) → `Donation` (one-to-many)
- `News` → `Comment` (one-to-many)
- `PaymentMethod` (configurable payment gateways)
- `Location` (geographic organization)

**Security & Monitoring:**
- `UserActivity` (activity logging)
- `Notification` (user notifications)
- `AuditLog` (admin action tracking)
- `SystemSettings` (encrypted configuration storage)

### Payment System Design
Multi-gateway architecture supporting:
- **Paystack**: Nigerian payments with USD→NGN conversion
- **PayPal**: Manual processing with fallback
- **Bank Transfer**: Manual verification workflow
- **Cryptocurrency**: Manual address-based payments

Payment flow: Donation creation → Gateway processing → Manual fallback → Admin verification

### Security Framework
- **security_utils.py**: Encryption, activity logging, location management
- **Cryptography**: Fernet encryption for sensitive data
- **CSRF Protection**: Flask-WTF integration
- **Activity Logging**: Comprehensive user action tracking
- **Location Services**: Consent-based user location with distance calculations

### File Upload System
Organized upload structure in `static/uploads/`:
- `kyc/`: KYC verification documents
- `campaigns/`: Campaign images
- `news/`: News article images
- `profiles/`: User profile pictures

### Admin Features
- **Emergency Recovery**: Token-based admin account recovery
- **KYC Management**: Document verification workflow
- **Campaign Moderation**: Publish/unpublish campaigns
- **Payment Configuration**: Dynamic payment method setup
- **Analytics Dashboard**: Comprehensive statistics
- **Backup/Restore**: Data export functionality

### Environment Configuration
Critical environment variables in `.env`:
- Database: `DATABASE_URL`
- Mail: `MAIL_SERVER`, `MAIL_USERNAME`, `MAIL_PASSWORD`
- PayPal: `PAYPAL_CLIENT_ID`, `PAYPAL_SECRET`, `PAYPAL_MODE`
- Paystack: `PAYSTACK_SECRET_KEY`, `PAYSTACK_PUBLIC_KEY`
- Coinbase: `COINBASE_API_KEY`, `COINBASE_WEBHOOK_SECRET`
- Security: `SECRET_KEY`, `ADMIN_RECOVERY_TOKEN`

### Template Structure
- **Base Template**: `templates/base.html`
- **Admin Templates**: `templates/admin/` (dashboard, users, campaigns, etc.)
- **User Templates**: Campaign pages, profile, news, payment flows
- **Manual Payment Pages**: Fallback payment instruction templates

### Self-Ping Keepalive
Background thread system to prevent hosting platform sleep:
- Configurable via `ENABLE_SELF_PING`, `SELF_PING_URL`
- 10-minute interval health checks
- Render deployment optimized

### Migration System
Flask-Migrate integration with versioned migrations in `migrations/versions/`:
- Database schema evolution tracking
- Payment method relationship fixes
- Donation model enhancements

## Development Notes

### Key Design Patterns
- **Blueprint modularization** for feature separation
- **Form validation** with Flask-WTF and WTForms
- **Activity logging** for security auditing
- **Graceful fallbacks** for payment processing
- **Manual verification workflows** for sensitive operations

### Database Relationships
- Users require KYC verification to create campaigns
- Campaigns must be admin-approved before publishing
- Donations track payment method and verification status
- Comments are user-specific and tied to news articles

### Security Considerations
- All sensitive data encrypted at rest
- Payment webhook signature verification
- CSRF protection on all forms
- Admin actions logged in audit trail
- Location data requires explicit user consent

### Payment Processing Flow
1. User initiates donation
2. Payment processor attempts automated processing
3. On failure, redirects to manual payment instructions
4. Admin verifies manual payments
5. Campaign raised amount updated on successful verification