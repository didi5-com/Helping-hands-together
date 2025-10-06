
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
            admin = User(
                email='ikpedesire5@gmail.com',
                name='Admin User',
                password_hash=generate_password_hash('didi5566'),
                is_admin=True,
                email_verified=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✓ Admin user created!")
            print("  Email: ikpedesire5@gmail.com")
            print("  Password: didi5566")
        else:
            # Update existing admin credentials
            admin.email = 'ikpedesire5@gmail.com'
            admin.password_hash = generate_password_hash('didi5566')
            db.session.commit()
            print("✓ Admin user credentials updated!")
            print("  Email: ikpedesire5@gmail.com")
            print("  Password: didi5566")
        
        print("✓ Database initialized successfully!")

if __name__ == '__main__':
    init_database()base()
