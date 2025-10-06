
from main import app, db
from models import User
from werkzeug.security import generate_password_hash

def init_database():
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if admin exists
        admin = User.query.filter_by(email='ikpedesire5@gmail.com').first()
        
        if not admin:
            # Create new admin user
            admin = User(
                email='ikpedesire5@gmail.com',
                name='Admin User',
                password_hash=generate_password_hash('didi5566'),
                is_admin=True,
                email_verified=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✓ Admin user created successfully!")
        else:
            # Update existing admin credentials
            admin.name = 'Admin User'
            admin.password_hash = generate_password_hash('didi5566')
            admin.is_admin = True
            admin.email_verified = True
            db.session.commit()
            print("✓ Admin user credentials updated successfully!")
        
        print("\n=== Admin Login Credentials ===")
        print(f"Email: ikpedesire5@gmail.com")
        print(f"Password: didi5566")
        print("================================\n")

if __name__ == '__main__':
    init_database()
