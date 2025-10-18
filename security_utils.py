import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from flask import request, current_app
from models import db, AuditLog, UserActivity

class SecurityManager:
    """Handles encryption, decryption, and security operations"""
    
    def __init__(self):
        self.key = self._get_or_create_key()
        self.cipher_suite = Fernet(self.key)
    
    def _get_or_create_key(self):
        """Get or create encryption key"""
        key_file = 'security.key'
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            return key
    
    def encrypt_data(self, data):
        """Encrypt sensitive data"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        return self.cipher_suite.encrypt(data).decode('utf-8')
    
    def decrypt_data(self, encrypted_data):
        """Decrypt sensitive data"""
        if isinstance(encrypted_data, str):
            encrypted_data = encrypted_data.encode('utf-8')
        return self.cipher_suite.decrypt(encrypted_data).decode('utf-8')
    
    def hash_sensitive_data(self, data):
        """Hash sensitive data for storage"""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
    
    def generate_secure_token(self, length=32):
        """Generate secure random token"""
        return secrets.token_urlsafe(length)
    
    def validate_payment_data(self, payment_data):
        """Validate and sanitize payment method data"""
        errors = []
        
        if payment_data.get('type') == 'paystack':
            if not payment_data.get('paystack_secret_key'):
                errors.append('Paystack secret key is required')
            if not payment_data.get('paystack_public_key'):
                errors.append('Paystack public key is required')
                
        elif payment_data.get('type') == 'paypal':
            if not payment_data.get('paypal_client_id'):
                errors.append('PayPal client ID is required')
            if not payment_data.get('paypal_secret'):
                errors.append('PayPal secret is required')
                
        elif payment_data.get('type') == 'crypto':
            if not payment_data.get('crypto_wallet_address'):
                errors.append('Crypto wallet address is required')
            if not payment_data.get('crypto_currency'):
                errors.append('Crypto currency type is required')
                
        elif payment_data.get('type') == 'bank':
            required_fields = ['bank_name', 'account_name', 'account_number']
            for field in required_fields:
                if not payment_data.get(field):
                    errors.append(f'{field.replace("_", " ").title()} is required')
        
        return errors

class ActivityLogger:
    """Logs user activities and system actions"""
    
    @staticmethod
    def log_user_activity(user_id, activity_type, description=None):
        """Log user activity"""
        try:
            activity = UserActivity(
                user_id=user_id,
                activity_type=activity_type,
                description=description,
                ip_address=request.remote_addr if request else None,
                user_agent=request.user_agent.string if request else None
            )
            db.session.add(activity)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Failed to log activity: {e}")
    
    @staticmethod
    def log_audit_action(user_id, action, table_name=None, record_id=None, old_values=None, new_values=None):
        """Log audit action"""
        try:
            audit_log = AuditLog(
                user_id=user_id,
                action=action,
                table_name=table_name,
                record_id=record_id,
                old_values=json.dumps(old_values) if old_values else None,
                new_values=json.dumps(new_values) if new_values else None,
                ip_address=request.remote_addr if request else None
            )
            db.session.add(audit_log)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Failed to log audit action: {e}")

class LocationManager:
    """Handles location-related functionality"""
    
    @staticmethod
    def update_user_location(user, latitude, longitude, location_name=None):
        """Update user location with consent"""
        if user.location_consent:
            user.latitude = latitude
            user.longitude = longitude
            if location_name:
                user.location = location_name
            db.session.commit()
            
            # Log location update
            ActivityLogger.log_user_activity(
                user.id, 
                'location_update', 
                f'Location updated to {location_name or "coordinates"}'
            )
            return True
        return False
    
    @staticmethod
    def get_user_distance(user1, user2):
        """Calculate distance between two users"""
        if not all([user1.latitude, user1.longitude, user2.latitude, user2.longitude]):
            return None
        
        # Simple distance calculation (in km)
        import math
        lat1, lon1 = math.radians(user1.latitude), math.radians(user1.longitude)
        lat2, lon2 = math.radians(user2.latitude), math.radians(user2.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Earth's radius in km
        
        return c * r

class NotificationManager:
    """Handles system notifications"""
    
    @staticmethod
    def create_notification(user_id, title, message, notification_type='info'):
        """Create a notification for a user"""
        from models import Notification
        try:
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message,
                type=notification_type
            )
            db.session.add(notification)
            db.session.commit()
            return notification
        except Exception as e:
            current_app.logger.error(f"Failed to create notification: {e}")
            return None
    
    @staticmethod
    def mark_as_read(notification_id, user_id):
        """Mark notification as read"""
        from models import Notification
        try:
            notification = Notification.query.filter_by(
                id=notification_id, 
                user_id=user_id
            ).first()
            if notification:
                notification.read = True
                db.session.commit()
                return True
        except Exception as e:
            current_app.logger.error(f"Failed to mark notification as read: {e}")
        return False
    
    @staticmethod
    def get_unread_count(user_id):
        """Get count of unread notifications"""
        from models import Notification
        try:
            return Notification.query.filter_by(user_id=user_id, read=False).count()
        except Exception as e:
            current_app.logger.error(f"Failed to get unread count: {e}")
            return 0

def get_client_ip():
    """Get client IP address"""
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        return request.environ['REMOTE_ADDR']
    else:
        return request.environ['HTTP_X_FORWARDED_FOR']

def is_safe_url(target):
    """Check if URL is safe for redirect"""
    from urllib.parse import urlparse, urljoin
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

def generate_csrf_token():
    """Generate CSRF token"""
    return secrets.token_urlsafe(32)

# Initialize security manager
security_manager = SecurityManager()