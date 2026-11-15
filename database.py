
import sqlite3
import os

# Store the database in the main CampusBite folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "campusbite.db")


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# CUSTOMER TABLE MIGRATION
def migrate_users_table():

    connection = get_connection()

    columns = connection.execute(
        "PRAGMA table_info(users)"
    ).fetchall()

    if not columns:
        connection.close()
        print("Users table will be created.")
        return

    column_names = [column["name"] for column in columns]

    # Add new columns without deleting existing customer information.
    if "email" not in column_names:
        connection.execute(
            "ALTER TABLE users ADD COLUMN email TEXT"
        )

    if "phone" not in column_names:
        connection.execute(
            "ALTER TABLE users ADD COLUMN phone TEXT"
        )

    if "college_name" not in column_names:
        connection.execute(
            "ALTER TABLE users ADD COLUMN college_name TEXT"
        )

    # Copy old contact information into the appropriate new column.
    if "contact" in column_names:

        connection.execute("""
            UPDATE users
            SET email = LOWER(contact)
            WHERE contact LIKE '%@%'
            AND email IS NULL
        """)

        connection.execute("""
            UPDATE users
            SET phone = contact
            WHERE contact NOT LIKE '%@%'
            AND phone IS NULL
        """)

    # Convert old student accounts to customer accounts.
    if "role" in column_names:

        connection.execute("""
            UPDATE users
            SET role = 'customer'
            WHERE LOWER(role) = 'student'
        """)

    connection.commit()
    connection.close()

    print("Customer table migration completed successfully!")


# CREATE DATABASE TABLES
def create_tables():

    connection = get_connection()

    connection.executescript("""

        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT UNIQUE,
            email TEXT,
            phone TEXT,
            college_name TEXT,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer'
        );

        CREATE UNIQUE INDEX IF NOT EXISTS unique_customer_email
        ON users(email)
        WHERE email IS NOT NULL;

        CREATE UNIQUE INDEX IF NOT EXISTS unique_customer_phone
        ON users(phone)
        WHERE phone IS NOT NULL;


        CREATE TABLE IF NOT EXISTS food_items (
            food_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            image TEXT,
            available INTEGER DEFAULT 1
        );


        CREATE TABLE IF NOT EXISTS pickup_slots (
            slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pickup_time TEXT NOT NULL,
            capacity INTEGER NOT NULL,
            active INTEGER DEFAULT 1
        );


        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            slot_id INTEGER NOT NULL,
            total REAL NOT NULL,
            payment_status TEXT DEFAULT 'pending',
            order_status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            collection_deadline TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (slot_id) REFERENCES pickup_slots(slot_id)
        );


        CREATE TABLE IF NOT EXISTS order_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            food_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (food_id) REFERENCES food_items(food_id)
        );


        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_status TEXT NOT NULL,
            transaction_reference TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        );


        CREATE TABLE IF NOT EXISTS order_status_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by INTEGER,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (updated_by) REFERENCES users(user_id)
        );

    """)

    connection.commit()
    connection.close()

    print("CampusBite database and tables created successfully!")


# ORDER TABLE MIGRATION
def migrate_orders_table():

    connection = get_connection()

    columns = connection.execute(
        "PRAGMA table_info(orders)"
    ).fetchall()

    column_names = [column["name"] for column in columns]

    if "pickup_date" not in column_names:

        connection.execute(
            "ALTER TABLE orders ADD COLUMN pickup_date TEXT"
        )

        connection.commit()

        print("Pickup date column added successfully!")

    else:
        print("Pickup date column already exists.")

    connection.close()


# INSERT SAMPLE FOOD ITEMS
def insert_sample_foods():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM food_items")

    count = cursor.fetchone()[0]

    if count == 0:

        sample_foods = [
            ("Veg Sandwich", "Snacks", 40, None, 1),
            ("Masala Dosa", "South Indian", 50, None, 1),
            ("Idli Vada", "South Indian", 35, None, 1),
            ("Veg Fried Rice", "Rice", 70, None, 1),
            ("Paneer Roll", "Snacks", 60, None, 1),
            ("Fresh Lime Juice", "Drinks", 30, None, 1),
            ("Tea", "Drinks", 15, None, 1),
            ("Veg Burger", "Fast Food", 55, None, 1)
        ]

        cursor.executemany("""
            INSERT INTO food_items
            (name, category, price, image, available)
            VALUES (?, ?, ?, ?, ?)
        """, sample_foods)

        connection.commit()

        print("Sample food items added successfully!")

    else:
        print("Food items already exist. No duplicates added.")

    connection.close()


# GENERATE PICKUP SLOTS
def generate_pickup_slots():

    connection = get_connection()

    cursor = connection.cursor()

    # Check whether pickup slots already exist.
    cursor.execute("SELECT COUNT(*) FROM pickup_slots")

    count = cursor.fetchone()[0]

    if count > 0:

        print("Pickup slots already exist. No duplicates added.")

        connection.close()
        return

    # Generate pickup slots from 8:00 AM to 7:00 PM.
    start_minutes = 8 * 60
    end_minutes = 19 * 60

    capacity = 10

    for minutes in range(start_minutes, end_minutes, 15):

        hours = minutes // 60
        remaining_minutes = minutes % 60

        pickup_time = f"{hours:02d}:{remaining_minutes:02d}"

        cursor.execute("""
            INSERT INTO pickup_slots
            (pickup_time, capacity, active)
            VALUES (?, ?, 1)
        """, (pickup_time, capacity))

    connection.commit()
    connection.close()

    print("Pickup slots generated successfully!")


# MAIN EXECUTION
if __name__ == "__main__":

    migrate_users_table()

    create_tables()

    migrate_orders_table()

    insert_sample_foods()

    generate_pickup_slots()
