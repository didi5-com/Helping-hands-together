
import os
import requests
import hmac
import hashlib
from flask import current_app

class PayPalPayment:
    def __init__(self, payment_method=None):
        if payment_method:
            self.client_id = payment_method.paypal_client_id
            self.secret = payment_method.paypal_secret
            self.mode = payment_method.paypal_mode or 'sandbox'
        else:
            self.client_id = os.getenv('PAYPAL_CLIENT_ID')
            self.secret = os.getenv('PAYPAL_SECRET')
            self.mode = os.getenv('PAYPAL_MODE', 'sandbox')
        self.base_url = 'https://api-m.sandbox.paypal.com' if self.mode == 'sandbox' else 'https://api-m.paypal.com'
    
    def get_access_token(self):
        url = f'{self.base_url}/v1/oauth2/token'
        headers = {'Accept': 'application/json', 'Accept-Language': 'en_US'}
        data = {'grant_type': 'client_credentials'}
        
        response = requests.post(url, headers=headers, data=data, auth=(self.client_id, self.secret))
        
        if response.status_code == 200:
            return response.json().get('access_token')
        return None
    
    def create_order(self, amount, return_url, cancel_url):
        access_token = self.get_access_token()
        if not access_token:
            return {'error': 'Failed to get access token'}
        
        url = f'{self.base_url}/v2/checkout/orders'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        data = {
            'intent': 'CAPTURE',
            'purchase_units': [{
                'amount': {
                    'currency_code': 'USD',
                    'value': str(amount)
                }
            }],
            'application_context': {
                'return_url': return_url,
                'cancel_url': cancel_url
            }
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 201:
            order = response.json()
            approval_url = next((link['href'] for link in order['links'] if link['rel'] == 'approve'), None)
            return {
                'order_id': order['id'],
                'approval_url': approval_url
            }
        
        return {'error': 'Failed to create order'}
    
    def capture_order(self, order_id):
        access_token = self.get_access_token()
        if not access_token:
            return {'error': 'Failed to get access token'}
        
        url = f'{self.base_url}/v2/checkout/orders/{order_id}/capture'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.post(url, headers=headers)
        
        if response.status_code == 201:
            return response.json()
        
        return {'error': 'Failed to capture order'}


class PaystackPayment:
    def __init__(self, payment_method=None):
        if payment_method:
            self.secret_key = payment_method.paystack_secret_key
        else:
            self.secret_key = os.getenv('PAYSTACK_SECRET_KEY')
        self.base_url = 'https://api.paystack.co'
    
    def initialize_transaction(self, email, amount, reference, callback_url):
        url = f'{self.base_url}/transaction/initialize'
        headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'email': email,
            'amount': int(amount * 100),  # Paystack uses kobo/cents
            'reference': reference,
            'callback_url': callback_url
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            if result['status']:
                return {
                    'authorization_url': result['data']['authorization_url'],
                    'access_code': result['data']['access_code'],
                    'reference': result['data']['reference']
                }
        
        return {'error': 'Failed to initialize transaction'}
    
    def verify_transaction(self, reference):
        url = f'{self.base_url}/transaction/verify/{reference}'
        headers = {
            'Authorization': f'Bearer {self.secret_key}'
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            if result['status'] and result['data']['status'] == 'success':
                return {'status': 'success', 'data': result['data']}
        
        return {'status': 'failed'}
    
    def verify_webhook(self, signature, body):
        computed_signature = hmac.new(
            self.secret_key.encode('utf-8'),
            body,
            hashlib.sha512
        ).hexdigest()
        
        return signature == computed_signature


class CoinbaseCommercePayment:
    def __init__(self):
        self.api_key = os.getenv('COINBASE_API_KEY')
        self.webhook_secret = os.getenv('COINBASE_WEBHOOK_SECRET')
        self.base_url = 'https://api.commerce.coinbase.com'
    
    def create_charge(self, name, description, amount, metadata=None):
        url = f'{self.base_url}/charges'
        headers = {
            'Content-Type': 'application/json',
            'X-CC-Api-Key': self.api_key,
            'X-CC-Version': '2018-03-22'
        }
        
        data = {
            'name': name,
            'description': description,
            'pricing_type': 'fixed_price',
            'local_price': {
                'amount': str(amount),
                'currency': 'USD'
            },
            'metadata': metadata or {}
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 201:
            result = response.json()
            return {
                'charge_id': result['data']['id'],
                'hosted_url': result['data']['hosted_url'],
                'code': result['data']['code']
            }
        
        return {'error': 'Failed to create charge'}
    
    def verify_webhook(self, signature, body):
        computed_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return signature == computed_signature


def get_payment_processor(payment_type):
    processors = {
        'paypal': PayPalPayment,
        'paystack': PaystackPayment,
        'crypto': CoinbaseCommercePayment
    }
    
    processor_class = processors.get(payment_type)
    if processor_class:
        return processor_class()
    
    return None
