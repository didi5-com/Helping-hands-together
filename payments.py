import os
import time
import requests
import hmac
import hashlib
from flask import jsonify, url_for, redirect, flash
from models import db, SystemSettings

# ---- Paystack processor (uses admin-configured keys) ----
class PaystackPayment:
    def __init__(self, payment_method=None):
        if payment_method and payment_method.paystack_secret_key:
            self.secret_key = payment_method.paystack_secret_key
            self.public_key = payment_method.paystack_public_key
        else:
            # Fallback to environment variables
            self.secret_key = os.getenv("PAYSTACK_SECRET_KEY")
            self.public_key = os.getenv("PAYSTACK_PUBLIC_KEY")

    def process_payment(self, donation):
        # Create a reference and store it
        reference = f"PSK_{donation.id}_{int(time.time())}"
        donation.transaction_id = reference
        donation.status = "pending"
        db.session.commit()

        # Determine USD->NGN conversion rate
        rate_setting = SystemSettings.query.filter_by(key='usd_ngn_rate').first()
        try:
            usd_ngn_rate = float(rate_setting.value) if (rate_setting and rate_setting.value) else float(os.getenv('USD_NGN_RATE', '1500'))
        except (TypeError, ValueError):
            usd_ngn_rate = 1500.0

        # Convert USD amount to NGN kobo for Paystack
        amount_kobo = int(round(donation.amount * usd_ngn_rate * 100))

        # Initialize Paystack transaction
        if self.secret_key:
            headers = {
                'Authorization': f'Bearer {self.secret_key}',
                'Content-Type': 'application/json'
            }
            
            callback_url = url_for('main.paystack_callback', _external=True)
            
            payload = {
                'email': donation.donor_email,
                'amount': amount_kobo,  # NGN in kobo
                'reference': reference,
                'currency': 'NGN',
                'callback_url': callback_url,
                'metadata': {
                    'original_amount_usd': donation.amount,
                    'applied_rate': usd_ngn_rate
                }
            }
            
            try:
                response = requests.post(
                    'https://api.paystack.co/transaction/initialize',
                    headers=headers,
                    json=payload,
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data['status']:
                        # Return HTML redirect to Paystack checkout
                        return redirect(data['data']['authorization_url'])
                        
            except requests.exceptions.RequestException as e:
                print(f"Paystack API error: {e}")
        
        # Fallback to manual payment
        flash('Paystack payment could not be initialized. Please use the instructions below or try again later.', 'warning')
        return redirect(url_for('main.manual_payment_page', method='paystack', donation_id=donation.id))

    def verify_transaction(self, reference):
        # Verify transaction with Paystack API
        if not self.secret_key:
            return {"status": "failed", "message": "No secret key configured"}
        
        headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(
                f'https://api.paystack.co/transaction/verify/{reference}',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['status'] and data['data']['status'] == 'success':
                    return {
                        "status": "success",
                        "amount": data['data']['amount'] / 100,  # Convert from kobo
                        "reference": data['data']['reference'],
                        "customer_email": data['data']['customer']['email']
                    }
            
            return {"status": "failed", "message": "Transaction verification failed"}
            
        except requests.exceptions.RequestException as e:
            return {"status": "failed", "message": f"API error: {str(e)}"}

    def verify_webhook(self, signature, body):
        # If you want webhook verification using your secret, compute HMAC and compare.
        # Paystack docs: verify using secret_key and sha512
        if not self.secret_key or not signature:
            return False
        computed = hmac.new(self.secret_key.encode('utf-8'), body, hashlib.sha512).hexdigest()
        return computed == signature

# ---- PayPal processor (uses admin-configured settings) ----
class PaypalPayment:
    def __init__(self, payment_method=None):
        if payment_method:
            self.client_id = payment_method.paypal_client_id
            self.secret = payment_method.paypal_secret  
            self.mode = payment_method.paypal_mode or 'sandbox'
        else:
            # Fallback to environment variables
            self.client_id = os.getenv("PAYPAL_CLIENT_ID")
            self.secret = os.getenv("PAYPAL_SECRET") 
            self.mode = os.getenv("PAYPAL_MODE", 'sandbox')
        
        self.base_url = 'https://api-m.sandbox.paypal.com' if self.mode == 'sandbox' else 'https://api-m.paypal.com'

    def process_payment(self, donation):
        # Set donation status to pending
        donation.status = "pending"
        db.session.commit()
        
        # Redirect to manual PayPal payment page
        return redirect(url_for('main.manual_payment_page', method='paypal', donation_id=donation.id))

    # optional placeholder if you later add API flow
    def capture_order(self, order_id):
        # Implement real capture if using PayPal REST API
        return {"error": "not_implemented"}

# ---- Manual bank (fallback) ----
class ManualBankPayment:
    def __init__(self, payment_method=None):
        self.payment_method = payment_method
    
    def process_payment(self, donation):
        donation.status = 'pending'
        db.session.commit()
        return jsonify({
            "message": "Bank transfer initiated. Awaiting confirmation from admin.",
            "status": "pending",
            "donation_id": donation.id
        })

# ---- Helper to get processor ----
def get_payment_processor(payment_type, payment_method=None):
    processors = {
        'paypal': PaypalPayment,
        'paystack': PaystackPayment,
        'bank': ManualBankPayment,
        'manual': ManualBankPayment,
        'crypto': ManualBankPayment  # crypto treated as manual address fallback
    }
    cls = processors.get(payment_type)
    return cls(payment_method) if cls else None
