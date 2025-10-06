
import os
import json
import hmac
import hashlib
import base64
import requests
from flask import current_app, url_for

class PayPalPayment:
    """PayPal REST API integration"""
    
    def __init__(self):
        self.client_id = current_app.config['PAYPAL_CLIENT_ID']
        self.secret = current_app.config['PAYPAL_SECRET']
        self.mode = current_app.config.get('PAYPAL_MODE', 'sandbox')
        
        if self.mode == 'sandbox':
            self.base_url = 'https://api.sandbox.paypal.com'
        else:
            self.base_url = 'https://api.paypal.com'
    
    def get_access_token(self):
        """Get PayPal OAuth access token"""
        url = f'{self.base_url}/v1/oauth2/token'
        headers = {
            'Accept': 'application/json',
            'Accept-Language': 'en_US',
        }
        auth = (self.client_id, self.secret)
        data = {'grant_type': 'client_credentials'}
        
        try:
            response = requests.post(url, headers=headers, auth=auth, data=data)
            response.raise_for_status()
            return response.json()['access_token']
        except Exception as e:
            current_app.logger.error(f'PayPal auth error: {e}')
            return None
    
    def create_order(self, amount, currency='USD', return_url=None, cancel_url=None):
        """Create PayPal order"""
        access_token = self.get_access_token()
        if not access_token:
            return {'error': 'Failed to authenticate with PayPal'}
        
        url = f'{self.base_url}/v2/checkout/orders'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        payload = {
            'intent': 'CAPTURE',
            'purchase_units': [{
                'amount': {
                    'currency_code': currency,
                    'value': str(amount)
                }
            }],
            'application_context': {
                'return_url': return_url or url_for('main.donation_success', _external=True),
                'cancel_url': cancel_url or url_for('main.donation_cancel', _external=True),
                'brand_name': 'Helping Hand Together',
                'user_action': 'PAY_NOW'
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Get approval URL
            approval_url = None
            for link in data.get('links', []):
                if link['rel'] == 'approve':
                    approval_url = link['href']
                    break
            
            return {
                'order_id': data['id'],
                'approval_url': approval_url,
                'status': data['status']
            }
        except Exception as e:
            current_app.logger.error(f'PayPal order creation error: {e}')
            return {'error': str(e)}
    
    def capture_order(self, order_id):
        """Capture/complete PayPal order"""
        access_token = self.get_access_token()
        if not access_token:
            return {'error': 'Failed to authenticate with PayPal'}
        
        url = f'{self.base_url}/v2/checkout/orders/{order_id}/capture'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        try:
            response = requests.post(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            current_app.logger.error(f'PayPal capture error: {e}')
            return {'error': str(e)}
    
    def verify_webhook(self, headers, body):
        """Verify PayPal webhook signature"""
        # Implementation for webhook verification
        # Use PayPal's webhook signature verification
        return True


class PaystackPayment:
    """Paystack API integration"""
    
    def __init__(self):
        self.secret_key = current_app.config['PAYSTACK_SECRET_KEY']
        self.public_key = current_app.config.get('PAYSTACK_PUBLIC_KEY')
        self.base_url = 'https://api.paystack.co'
    
    def initialize_transaction(self, email, amount, reference=None, callback_url=None):
        """Initialize Paystack transaction"""
        url = f'{self.base_url}/transaction/initialize'
        headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }
        
        # Paystack accepts amount in kobo (smallest currency unit)
        amount_kobo = int(amount * 100)
        
        payload = {
            'email': email,
            'amount': amount_kobo,
            'currency': 'NGN',  # Change based on your needs
            'callback_url': callback_url or url_for('main.paystack_callback', _external=True)
        }
        
        if reference:
            payload['reference'] = reference
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if data['status']:
                return {
                    'authorization_url': data['data']['authorization_url'],
                    'access_code': data['data']['access_code'],
                    'reference': data['data']['reference']
                }
            else:
                return {'error': data.get('message', 'Transaction initialization failed')}
        except Exception as e:
            current_app.logger.error(f'Paystack initialization error: {e}')
            return {'error': str(e)}
    
    def verify_transaction(self, reference):
        """Verify Paystack transaction"""
        url = f'{self.base_url}/transaction/verify/{reference}'
        headers = {
            'Authorization': f'Bearer {self.secret_key}'
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] and data['data']['status'] == 'success':
                return {
                    'status': 'success',
                    'amount': data['data']['amount'] / 100,  # Convert from kobo
                    'reference': data['data']['reference'],
                    'paid_at': data['data']['paid_at'],
                    'customer': data['data']['customer']
                }
            else:
                return {'status': 'failed', 'message': data.get('message')}
        except Exception as e:
            current_app.logger.error(f'Paystack verification error: {e}')
            return {'status': 'error', 'message': str(e)}
    
    def verify_webhook(self, signature, body):
        """Verify Paystack webhook signature"""
        hash_signature = hmac.new(
            self.secret_key.encode('utf-8'),
            body,
            hashlib.sha512
        ).hexdigest()
        return hash_signature == signature


class CoinbaseCommercePayment:
    """Coinbase Commerce API integration"""
    
    def __init__(self):
        self.api_key = current_app.config['COINBASE_API_KEY']
        self.webhook_secret = current_app.config.get('COINBASE_WEBHOOK_SECRET')
        self.base_url = 'https://api.commerce.coinbase.com'
    
    def create_charge(self, name, description, amount, currency='USD', metadata=None):
        """Create Coinbase Commerce charge"""
        url = f'{self.base_url}/charges'
        headers = {
            'Content-Type': 'application/json',
            'X-CC-Api-Key': self.api_key,
            'X-CC-Version': '2018-03-22'
        }
        
        payload = {
            'name': name,
            'description': description,
            'pricing_type': 'fixed_price',
            'local_price': {
                'amount': str(amount),
                'currency': currency
            },
            'metadata': metadata or {},
            'redirect_url': url_for('main.donation_success', _external=True),
            'cancel_url': url_for('main.donation_cancel', _external=True)
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            return {
                'charge_id': data['data']['id'],
                'hosted_url': data['data']['hosted_url'],
                'code': data['data']['code'],
                'addresses': data['data']['addresses']
            }
        except Exception as e:
            current_app.logger.error(f'Coinbase charge creation error: {e}')
            return {'error': str(e)}
    
    def get_charge(self, charge_id):
        """Retrieve Coinbase Commerce charge"""
        url = f'{self.base_url}/charges/{charge_id}'
        headers = {
            'X-CC-Api-Key': self.api_key,
            'X-CC-Version': '2018-03-22'
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            current_app.logger.error(f'Coinbase charge retrieval error: {e}')
            return {'error': str(e)}
    
    def verify_webhook(self, signature, body):
        """Verify Coinbase Commerce webhook signature"""
        computed_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(computed_signature, signature)


def get_payment_processor(payment_method):
    """Factory function to get payment processor"""
    if payment_method == 'paypal':
        return PayPalPayment()
    elif payment_method == 'paystack':
        return PaystackPayment()
    elif payment_method == 'crypto':
        return CoinbaseCommercePayment()
    else:
        return None
