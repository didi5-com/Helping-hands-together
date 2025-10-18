#!/usr/bin/env python3
"""
Payment System Test Script
Tests all payment methods and flows in the donation system
"""

import os
import sys
import requests
import json
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_paystack_integration():
    """Test Paystack payment processor"""
    print("🧪 Testing Paystack Integration...")
    
    try:
        from payments import PaystackPayment, get_payment_processor
        
        # Test with mock payment method
        class MockPaymentMethod:
            paystack_secret_key = os.getenv("PAYSTACK_SECRET_KEY", "test_key")
            paystack_public_key = os.getenv("PAYSTACK_PUBLIC_KEY", "test_key")
        
        # Test processor initialization
        processor = PaystackPayment(MockPaymentMethod())
        print("✅ Paystack processor initialized successfully")
        
        # Test get_payment_processor factory
        processor2 = get_payment_processor('paystack', MockPaymentMethod())
        if processor2:
            print("✅ Payment processor factory works")
        else:
            print("❌ Payment processor factory failed")
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
    except Exception as e:
        print(f"❌ Paystack test failed: {e}")

def test_paypal_integration():
    """Test PayPal payment processor"""
    print("🧪 Testing PayPal Integration...")
    
    try:
        from payments import PaypalPayment, get_payment_processor
        
        # Test with mock payment method
        class MockPaymentMethod:
            paypal_client_id = "test_client_id"
            paypal_secret = "test_secret"
            paypal_mode = "sandbox"
        
        # Test processor initialization
        processor = PaypalPayment(MockPaymentMethod())
        print("✅ PayPal processor initialized successfully")
        
        # Test get_payment_processor factory
        processor2 = get_payment_processor('paypal', MockPaymentMethod())
        if processor2:
            print("✅ Payment processor factory works for PayPal")
        else:
            print("❌ Payment processor factory failed for PayPal")
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
    except Exception as e:
        print(f"❌ PayPal test failed: {e}")

def test_manual_payment_processors():
    """Test manual payment processors"""
    print("🧪 Testing Manual Payment Processors...")
    
    try:
        from payments import ManualBankPayment, get_payment_processor
        
        # Test bank payment processor
        processor = ManualBankPayment()
        print("✅ Manual bank processor initialized successfully")
        
        # Test factory for crypto and bank
        crypto_processor = get_payment_processor('crypto')
        bank_processor = get_payment_processor('bank')
        
        if crypto_processor and bank_processor:
            print("✅ Manual payment processors work via factory")
        else:
            print("❌ Manual payment processor factory failed")
            
    except Exception as e:
        print(f"❌ Manual payment test failed: {e}")

def test_database_models():
    """Test database models for payment system"""
    print("🧪 Testing Database Models...")
    
    try:
        from models import PaymentMethod, Donation, Campaign, User
        print("✅ All payment-related models imported successfully")
        
        # Check if PaymentMethod has all required fields
        pm_fields = ['name', 'type', 'details', 'crypto_wallet_address', 'crypto_currency', 
                    'bank_name', 'account_name', 'account_number', 'paypal_client_id', 
                    'paypal_secret', 'paystack_public_key', 'paystack_secret_key', 'active']
        
        for field in pm_fields:
            if hasattr(PaymentMethod, field):
                print(f"✅ PaymentMethod has {field} field")
            else:
                print(f"❌ PaymentMethod missing {field} field")
                
    except ImportError as e:
        print(f"❌ Database model import error: {e}")
    except Exception as e:
        print(f"❌ Database model test failed: {e}")

def test_flask_routes():
    """Test Flask routes (requires running app)"""
    print("🧪 Testing Flask Routes...")
    
    # Check if app is running on default port
    try:
        response = requests.get('http://127.0.0.1:5000/', timeout=5)
        if response.status_code == 200:
            print("✅ Flask app is running")
            
            # Test campaign page
            try:
                campaigns_response = requests.get('http://127.0.0.1:5000/campaigns', timeout=5)
                if campaigns_response.status_code == 200:
                    print("✅ Campaigns page accessible")
                else:
                    print(f"❌ Campaigns page returned {campaigns_response.status_code}")
            except:
                print("❌ Could not access campaigns page")
        else:
            print(f"❌ Flask app returned status {response.status_code}")
            
    except requests.exceptions.RequestException:
        print("❌ Flask app not running or not accessible on http://127.0.0.1:5000/")
        print("   Start the app with: python main.py")

def test_environment_variables():
    """Test environment variables for payment systems"""
    print("🧪 Testing Environment Variables...")
    
    env_vars = {
        'PAYSTACK_SECRET_KEY': 'Paystack secret key',
        'PAYSTACK_PUBLIC_KEY': 'Paystack public key', 
        'PAYPAL_EMAIL': 'PayPal email for manual payments',
        'PAYPAL_CLIENT_ID': 'PayPal client ID',
        'PAYPAL_SECRET': 'PayPal secret key'
    }
    
    for var, description in env_vars.items():
        value = os.getenv(var)
        if value:
            print(f"✅ {var} is set ({'*' * min(10, len(value))}...)")
        else:
            print(f"⚠️  {var} not set - {description}")

def test_template_files():
    """Test template files existence"""
    print("🧪 Testing Template Files...")
    
    templates = [
        'templates/campaign.html',
        'templates/manual_payment.html',
        'templates/donation_success.html'
    ]
    
    for template in templates:
        if os.path.exists(template):
            print(f"✅ {template} exists")
        else:
            print(f"❌ {template} missing")

def main():
    """Run all tests"""
    print("🚀 Starting Payment System Tests")
    print("=" * 50)
    
    test_environment_variables()
    print()
    
    test_database_models() 
    print()
    
    test_paystack_integration()
    print()
    
    test_paypal_integration()
    print()
    
    test_manual_payment_processors()
    print()
    
    test_template_files()
    print()
    
    test_flask_routes()
    print()
    
    print("=" * 50)
    print("✅ Payment system testing completed!")
    print()
    print("🔧 To set up payment processing:")
    print("1. Add your Paystack keys to environment variables:")
    print("   PAYSTACK_SECRET_KEY=sk_test_xxxxx")
    print("   PAYSTACK_PUBLIC_KEY=pk_test_xxxxx")
    print()
    print("2. Add PayPal email for manual payments:")
    print("   PAYPAL_EMAIL=donations@yourdomain.com")
    print()
    print("3. Configure payment methods in admin panel")
    print("4. Test donations on a live campaign")

if __name__ == "__main__":
    main()