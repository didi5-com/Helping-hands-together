#!/usr/bin/env python
import argparse
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import app, db
from models import User
from werkzeug.security import generate_password_hash


def ensure_admin(email: str, password: str, name: str = "Admin"):
    email = email.strip().lower()
    with app.app_context():
        db.create_all()
        user = User.query.filter_by(email=email).first()
        if user:
            user.is_admin = True
            user.email_verified = True
            user.password_hash = generate_password_hash(password)
        else:
            user = User(
                email=email,
                name=name,
                password_hash=generate_password_hash(password),
                is_admin=True,
                email_verified=True,
            )
            db.session.add(user)
        db.session.commit()
        print(f"Admin ensured for {email}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or update an admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="Admin User")
    args = parser.parse_args()
    ensure_admin(args.email, args.password, args.name)
