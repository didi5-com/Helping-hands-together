# Helping Hand Together - Charity Crowdfunding Platform

## Overview

Helping Hand Together is a Flask-based charity crowdfunding platform that enables users to create and support charitable campaigns. The platform features comprehensive user management, KYC verification, multiple payment gateway integrations (PayPal, Paystack, Coinbase Commerce, and Bank Transfer), and an admin dashboard for moderation and management.

The application follows a traditional Flask MVC architecture with Blueprint-based routing, SQLAlchemy ORM for database operations, and Jinja2 templating for server-side rendering.

## Recent Changes (October 2025)

### Payment System Improvements
- **Bank Transfer Template**: Created `bank_transfer.html` with complete bank transfer instructions and donation tracking
- **Payment UI Enhancement**: Improved donation form with icon-enhanced input fields and real-time payment method help text
- **PayPal Configuration**: Configured for live/production mode with proper API integration
- **Paystack Integration**: Verified API configuration for live transactions
- **Payment Form UX**: Added Bootstrap icons and contextual help for each payment method

### Email System Configuration
- **Gmail SMTP Setup**: Configured for Gmail App Password authentication
- **Mail Server**: Default SMTP server set to smtp.gmail.com with TLS support
- **Email Testing**: Admin appreciation email system ready for use

### Bug Fixes
- Fixed missing `bank_transfer.html` template causing 500 errors
- Fixed variable naming consistency in bank transfer route
- Improved error handling in payment processors
- **Image Upload Display Fix** (October 6, 2025): Resolved critical issue where uploaded images for campaigns and news were not displaying. The database fields use `image_path` but code was incorrectly using `image`. Fixed all occurrences in:
  - `auth.py`: Campaign image upload (line 133)
  - `admin.py`: News image upload (line 157)
  - Templates: `campaign.html`, `campaigns.html`, `index.html`, `news_list.html`, `news_detail.html`

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Application Structure
- **Blueprint-based Architecture**: The application is organized into modular blueprints (`auth`, `admin`, `main`) for separation of concerns and maintainable routing
- **MVC Pattern**: Models defined in `models.py`, views handled through Flask routes, and Jinja2 templates for presentation
- **Configuration Management**: Environment-based configuration using `python-dotenv` with fallback defaults for development

### Data Layer
- **ORM**: SQLAlchemy for database abstraction with Flask-SQLAlchemy integration
- **Database**: Currently configured for SQLite (development) with support for PostgreSQL via `DATABASE_URL` environment variable
- **Migration Management**: Flask-Migrate (Alembic) for database schema versioning
- **Core Models**:
  - `User`: Authentication, profile, admin flags, email verification
  - `Campaign`: Fundraising campaigns with goal tracking, publishing workflow
  - `Donation`: Transaction records with multiple payment method support
  - `KYC`: User verification documents with approval workflow
  - `News`: Content management with author attribution
  - `Comment`: User engagement on news articles
  - `PaymentMethod`: Configurable payment gateway credentials
  - `Location`: Geographic categorization

### Authentication & Authorization
- **User Authentication**: Flask-Login for session management with remember-me functionality
- **Password Security**: Werkzeug password hashing for secure credential storage
- **Access Control**: Decorator-based admin authorization (`@admin_required`)
- **KYC Verification**: Three-state verification workflow (pending/verified/rejected) required for campaign creation

### Payment Integration
- **Multi-Gateway Support**: Abstracted payment processing supporting:
  - PayPal (REST API with OAuth token management)
  - Paystack (transaction initialization and verification)
  - Coinbase Commerce (cryptocurrency hosted checkout)
  - Bank Transfer (manual admin confirmation workflow)
- **Payment Flow**: Form submission → gateway-specific processing → status tracking → admin confirmation (for bank transfers)
- **Transaction States**: Pending, completed, failed with campaign balance updates

### File Upload System
- **Storage**: Local filesystem under `static/uploads/` with subdirectories for different asset types (kyc, campaigns, news)
- **Validation**: File type restrictions (images: jpg/png/jpeg, documents: pdf) with size limits (16MB)
- **Security**: Werkzeug's `secure_filename()` for sanitization

### Email System
- **Provider**: Flask-Mail with SMTP configuration (Gmail-ready)
- **Use Cases**: 
  - Admin appreciation messages to users
  - Future: donation confirmations, campaign updates
- **Configuration**: TLS-enabled SMTP with app password support

### Admin Dashboard
- **Analytics**: Aggregated metrics (total users, campaigns, donations, raised amounts)
- **User Management**: Admin role toggling, appreciation messaging, user listing
- **Content Moderation**: 
  - KYC document review and approval/rejection
  - Campaign publishing workflow
  - News article management
- **Payment Administration**: 
  - Gateway credential configuration
  - Bank transfer confirmation
  - Donation tracking by status
- **Location Management**: Geographic tags for campaign categorization

### Frontend Architecture
- **Template Engine**: Jinja2 with template inheritance (`base.html`)
- **CSS Framework**: Bootstrap 5.3.2 for responsive UI
- **Icons**: Bootstrap Icons 1.11.1
- **Client-side Logic**: Minimal JavaScript, primarily for Bootstrap components
- **Styling**: Custom CSS variables for brand colors, card hover effects, gradient hero sections

### Security Considerations
- **CSRF Protection**: Flask-WTF forms with CSRF tokens
- **File Upload Validation**: Extension and MIME type checking
- **SQL Injection Prevention**: SQLAlchemy ORM parameterized queries
- **Session Security**: Flask's secure session cookies with configurable SECRET_KEY
- **Password Requirements**: Minimum 6 characters enforced at form validation

## External Dependencies

### Core Framework
- **Flask 3.0.0**: Web application framework
- **Flask-SQLAlchemy 3.1.1**: ORM integration
- **Flask-Migrate 4.0.5**: Database migration management
- **Flask-Login 0.6.3**: User session management
- **Flask-WTF 1.2.1**: Form handling and CSRF protection
- **Flask-Mail 0.9.1**: Email functionality

### Payment Gateways
- **PayPal**: REST API integration (credentials via environment variables)
- **Paystack**: HTTP API (public/secret key authentication)
- **Coinbase Commerce**: Hosted checkout API (API key authentication)
- **Bank Transfer**: Manual processing (no external API)

### Email Service
- **SMTP Provider**: Configurable (Gmail default)
- **Authentication**: App-specific passwords or OAuth2 (recommended for Gmail)

### Development Tools
- **python-dotenv 1.0.0**: Environment variable management
- **Werkzeug 3.0.1**: WSGI utilities, security helpers
- **WTForms 3.1.1**: Form validation library
- **email-validator 2.1.0**: Email format validation

### Production Dependencies
- **psycopg2-binary 2.9.9**: PostgreSQL adapter (for production database)
- **gunicorn 21.2.0**: WSGI HTTP server for production deployment
- **Pillow 10.1.0**: Image processing for uploads
- **requests 2.31.0**: HTTP library for payment gateway communication

### Database
- **Development**: SQLite (file-based, `hht.db`)
- **Production**: PostgreSQL (via `DATABASE_URL` environment variable)
- **Note**: Application uses SQLAlchemy ORM which abstracts database differences, but PostgreSQL is recommended for production due to concurrent access handling and JSON field support

### Required Environment Variables
- `SECRET_KEY`: Flask session encryption
- `DATABASE_URL`: PostgreSQL connection string (optional, defaults to SQLite)
- `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`: SMTP configuration
- `PAYPAL_CLIENT_ID`, `PAYPAL_SECRET`, `PAYPAL_MODE`: PayPal integration
- `PAYSTACK_PUBLIC_KEY`, `PAYSTACK_SECRET_KEY`: Paystack integration
- `COINBASE_API_KEY`, `COINBASE_WEBHOOK_SECRET`: Coinbase Commerce integration