
from main import app, db
from models import User
from werkzeug.security import generate_password_hash

def init_database():
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if admin exists
        admin = User.query.filter_by(email='admin@example.com').first()
        
        if not admin:
            admin = User(
                email='admin@example.com',
                name='Admin User',
                password_hash=generate_password_hash('admin123'),
                is_admin=True,
                email_verified=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✓ Admin user created!")
            print("  Email: admin@example.com")
            print("  Password: admin123")
            print("  Please change the password after first login!")
        else:
            print("✓ Admin user already exists")
        
        print("✓ Database initialized successfully!")

if __name__ == '__main__':
    init_database()
