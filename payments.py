
import os
import json
import hmac
import hashlib
import base64
import requests
from flask import current_app

def get_payment_processor(payment_type):
    processors = {
        'paypal': PayPalPayment,
        'paystack': PaystackPayment,
        'crypto': CoinbaseCommercePayment,
        'bank': BankTransferPayment
    }
    return processors.get(payment_type)()

class PayPalPayment:
    def __init__(self):
        self.client_id = os.getenv('PAYPAL_CLIENT_ID')
        self.secret = os.getenv('PAYPAL_SECRET')
        self.mode = os.getenv('PAYPAL_MODE', 'sandbox')
        self.base_url = f"https://api-m.{'sandbox.' if self.mode == 'sandbox' else ''}paypal.com"
    
    def get_access_token(self):
        url = f"{self.base_url}/v1/oauth2/token"
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US",
        }
        auth = (self.client_id, self.secret)
        data = {"grant_type": "client_credentials"}
        
        response = requests.post(url, headers=headers, auth=auth, data=data)
        return response.json().get('access_token')
    
    def create_order(self, amount, return_url, cancel_url):
        access_token = self.get_access_token()
        url = f"{self.base_url}/v2/checkout/orders"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {
                    "currency_code": "USD",
                    "value": str(amount)
                }
            }],
            "application_context": {
                "return_url": return_url,
                "cancel_url": cancel_url
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        
        if response.status_code == 201:
            approval_url = next((link['href'] for link in data.get('links', []) if link['rel'] == 'approve'), None)
            return {
                'order_id': data['id'],
                'approval_url': approval_url
            }
        return {'error': data}
    
    def capture_order(self, order_id):
        access_token = self.get_access_token()
        url = f"{self.base_url}/v2/checkout/orders/{order_id}/capture"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        
        response = requests.post(url, headers=headers)
        return response.json()

class PaystackPayment:
    def __init__(self):
        self.secret_key = os.getenv('PAYSTACK_SECRET_KEY')
        self.public_key = os.getenv('PAYSTACK_PUBLIC_KEY')
        self.base_url = "https://api.paystack.co"
    
    def initialize_transaction(self, email, amount, reference, callback_url):
        url = f"{self.base_url}/transaction/initialize"
        
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "email": email,
            "amount": int(amount * 100),  # Convert to kobo/cents
            "reference": reference,
            "callback_url": callback_url
        }
        
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        
        if data.get('status'):
            return {
                'authorization_url': data['data']['authorization_url'],
                'access_code': data['data']['access_code'],
                'reference': data['data']['reference']
            }
        return {'error': data.get('message')}
    
    def verify_transaction(self, reference):
        url = f"{self.base_url}/transaction/verify/{reference}"
        
        headers = {
            "Authorization": f"Bearer {self.secret_key}"
        }
        
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if data.get('status') and data['data']['status'] == 'success':
            return {
                'status': 'success',
                'amount': data['data']['amount'] / 100,  # Convert from kobo/cents
                'reference': data['data']['reference']
            }
        return {'status': 'failed'}
    
    def verify_webhook(self, signature, payload):
        expected_signature = hmac.new(
            self.secret_key.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)

class CoinbaseCommercePayment:
    def __init__(self):
        self.api_key = os.getenv('COINBASE_API_KEY')
        self.webhook_secret = os.getenv('COINBASE_WEBHOOK_SECRET')
        self.base_url = "https://api.commerce.coinbase.com"
    
    def create_charge(self, name, description, amount, metadata=None):
        url = f"{self.base_url}/charges"
        
        headers = {
            "Content-Type": "application/json",
            "X-CC-Api-Key": self.api_key,
            "X-CC-Version": "2018-03-22"
        }
        
        payload = {
            "name": name,
            "description": description,
            "pricing_type": "fixed_price",
            "local_price": {
                "amount": str(amount),
                "currency": "USD"
            },
            "metadata": metadata or {}
        }
        
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        
        if 'data' in data:
            return {
                'charge_id': data['data']['id'],
                'hosted_url': data['data']['hosted_url'],
                'code': data['data']['code']
            }
        return {'error': data}
    
    def verify_webhook(self, signature, payload):
        expected_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)

class BankTransferPayment:
    def __init__(self):
        pass
    
    def get_instructions(self):
        return {
            'message': 'Please transfer to the bank account details provided by admin'
        }
