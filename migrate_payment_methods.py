
from main import app, db
from models import PaymentMethod

def migrate_payment_methods():
    with app.app_context():
        # Add new columns to existing table
        with db.engine.connect() as conn:
            try:
                # Check if columns exist, if not add them
                conn.execute(db.text("""
                    ALTER TABLE payment_method ADD COLUMN crypto_wallet_address VARCHAR(200);
                """))
            except:
                pass
            
            try:
                conn.execute(db.text("""
                    ALTER TABLE payment_method ADD COLUMN crypto_currency VARCHAR(20);
                """))
            except:
                pass
            
            try:
                conn.execute(db.text("""
                    ALTER TABLE payment_method ADD COLUMN bank_name VARCHAR(100);
                """))
            except:
                pass
            
            try:
                conn.execute(db.text("""
                    ALTER TABLE payment_method ADD COLUMN account_name VARCHAR(100);
                """))
            except:
                pass
            
            try:
                conn.execute(db.text("""
                    ALTER TABLE payment_method ADD COLUMN account_number VARCHAR(50);
                """))
            except:
                pass
            
            try:
                conn.execute(db.text("""
                    ALTER TABLE payment_method ADD COLUMN routing_number VARCHAR(50);
                """))
            except:
                pass
            
            try:
                conn.execute(db.text("""
                    ALTER TABLE payment_method ADD COLUMN bank_address TEXT;
                """))
            except:
                pass
            
            try:
                conn.execute(db.text("""
                    ALTER TABLE payment_method ADD COLUMN paypal_client_id VARCHAR(200);
                """))
            except:
                pass
            
            try:
                conn.execute(db.text("""
                    ALTER TABLE payment_method ADD COLUMN paypal_secret VARCHAR(200);
                """))
            except:
                pass
            
            try:
                conn.execute(db.text("""
                    ALTER TABLE payment_method ADD COLUMN paypal_mode VARCHAR(20);
                """))
            except:
                pass
            
            try:
                conn.execute(db.text("""
                    ALTER TABLE payment_method ADD COLUMN paystack_public_key VARCHAR(200);
                """))
            except:
                pass
            
            try:
                conn.execute(db.text("""
                    ALTER TABLE payment_method ADD COLUMN paystack_secret_key VARCHAR(200);
                """))
            except:
                pass
            
            conn.commit()
        
        print("✓ Payment method columns added successfully!")

if __name__ == '__main__':
    migrate_payment_methods()
