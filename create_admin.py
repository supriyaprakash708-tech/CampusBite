
from database import get_connection
from werkzeug.security import generate_password_hash
from getpass import getpass

print("\n===== CampusBite Admin Account Setup =====\n")

name = input("Enter Admin Name: ").strip()
email = input("Enter Admin Email: ").strip().lower()
password = getpass("Create Admin Password: ")
confirm_password = getpass("Confirm Admin Password: ")

if not name or not email or "@" not in email:
    print("Invalid name or email.")
    raise SystemExit

if len(password) < 8:
    print("Password must contain at least 8 characters.")
    raise SystemExit

if password != confirm_password:
    print("Passwords do not match.")
    raise SystemExit

connection = get_connection()

existing = connection.execute("""
    SELECT user_id FROM users
    WHERE email = ? OR contact = ?
""", (email, email)).fetchone()

if existing:
    print("An account with this email already exists.")
else:
    connection.execute("""
        INSERT INTO users
        (name, contact, email, college_name, password_hash, role)
        VALUES (?, ?, ?, ?, ?, 'admin')
    """, (
        name,
        email,
        email,
        "CampusBite Administration",
        generate_password_hash(password)
    ))

    connection.commit()
    print("\nAdmin account created successfully!")

connection.close()
