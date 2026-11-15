
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, session
from database import get_connection
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import re
import os


app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "campusbite-local-development-key"
)

app.jinja_env.globals.update(datetime=datetime)

# =====================================================
# HOME PAGE
# =====================================================

@app.route("/")
def home():
    return render_template("index.html")


# =====================================================
# FOOD MENU
# =====================================================

@app.route("/menu")
def menu():

    connection = get_connection()

    try:
        foods = connection.execute("""
            SELECT * FROM food_items
            ORDER BY category, name
        """).fetchall()

    finally:
        connection.close()

    return render_template("menu.html", foods=foods)


# =====================================================
# CUSTOMER REGISTRATION
# =====================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        college_name = request.form.get("college_name", "").strip()
        password = request.form.get("password", "")

        if not all([name, email, phone, college_name, password]):
            return render_template(
                "register.html",
                message="Please fill in all fields.",
                message_type="error"
            )

        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            return render_template(
                "register.html",
                message="Please enter a valid email address.",
                message_type="error"
            )

        phone = re.sub(r"[\s-]", "", phone)

        if not re.fullmatch(r"\+?\d{10,15}", phone):
            return render_template(
                "register.html",
                message="Please enter a valid phone number.",
                message_type="error"
            )

        if len(password) < 8:
            return render_template(
                "register.html",
                message="Password must contain at least 8 characters.",
                message_type="error"
            )

        password_hash = generate_password_hash(password)

        connection = get_connection()

        try:
            connection.execute("""
                INSERT INTO users
                (name, contact, email, phone, college_name,
                 password_hash, role)
                VALUES (?, ?, ?, ?, ?, ?, 'customer')
            """, (
                name,
                email,
                email,
                phone,
                college_name,
                password_hash
            ))

            connection.commit()

            return render_template(
                "register.html",
                message="Customer registration successful! You can now log in.",
                message_type="success"
            )

        except sqlite3.IntegrityError:
            return render_template(
                "register.html",
                message="This email address or phone number is already registered.",
                message_type="error"
            )

        finally:
            connection.close()

    return render_template("register.html")


# =====================================================
# CUSTOMER LOGIN
# =====================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        contact = request.form.get("contact", "").strip()

        if "@" in contact:
            contact = contact.lower()
        else:
            contact = re.sub(r"[\s-]", "", contact)

        password = request.form.get("password", "")

        connection = get_connection()

        try:
            customer = connection.execute("""
                SELECT * FROM users
                WHERE (email = ? OR phone = ? OR contact = ?)
                AND role = 'customer'
            """, (contact, contact, contact)).fetchone()

        finally:
            connection.close()

        if customer and check_password_hash(
            customer["password_hash"], password
        ):

            session["user_id"] = customer["user_id"]
            session["customer_name"] = customer["name"]

            return redirect(url_for("menu"))

        return render_template(
            "login.html",
            message="Invalid email/phone number or password.",
            message_type="error"
        )

    return render_template("login.html")


# =====================================================
# ADMIN LOGIN
# =====================================================

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        connection = get_connection()

        try:
            admin = connection.execute("""
                SELECT * FROM users
                WHERE email = ?
                AND role = 'admin'
            """, (email,)).fetchone()

        finally:
            connection.close()

        if admin and check_password_hash(
            admin["password_hash"], password
        ):

            session["admin_id"] = admin["user_id"]
            session["admin_name"] = admin["name"]

            return redirect(url_for("admin_dashboard"))

        return render_template(
            "admin_login.html",
            message="Invalid admin email or password.",
            message_type="error"
        )

    return render_template("admin_login.html")


# =====================================================
# ADMIN DASHBOARD
# =====================================================

@app.route("/admin-dashboard")
def admin_dashboard():

    if not session.get("admin_id"):
        return redirect(url_for("admin_login"))

    connection = get_connection()

    try:

        # DASHBOARD STATISTICS

        total_orders = connection.execute("""
            SELECT COUNT(*) FROM orders
        """).fetchone()[0]

        pending_orders = connection.execute("""
            SELECT COUNT(*) FROM orders
            WHERE LOWER(order_status) = 'paid'
        """).fetchone()[0]

        completed_orders = connection.execute("""
            SELECT COUNT(*) FROM orders
            WHERE LOWER(order_status) = 'completed'
        """).fetchone()[0]

        total_customers = connection.execute("""
            SELECT COUNT(*) FROM users
            WHERE role = 'customer'
        """).fetchone()[0]


        # RECENT ORDERS

        recent_orders = connection.execute("""
            SELECT
                o.order_id,
                u.name AS customer_name,
                o.total,
                o.order_status,
                o.payment_status,
                o.pickup_date,
                p.pickup_time
            FROM orders o
            JOIN users u ON o.user_id = u.user_id
            LEFT JOIN pickup_slots p ON o.slot_id = p.slot_id
            ORDER BY o.created_at DESC
            LIMIT 10
        """).fetchall()


        # MANAGE FOOD

        foods = connection.execute("""
            SELECT *
            FROM food_items
            ORDER BY category, name
        """).fetchall()


        # MANAGE ALL ORDERS

        all_orders = connection.execute("""
            SELECT
                o.order_id,
                o.total,
                o.payment_status,
                o.order_status,
                o.pickup_date,
                o.created_at,

                u.name AS customer_name,
                u.email AS customer_email,
                u.phone AS customer_phone,

                p.pickup_time,

                (
                    SELECT GROUP_CONCAT(
                        f.name || ' x ' || oi.quantity,
                        ', '
                    )
                    FROM order_items oi
                    JOIN food_items f
                        ON oi.food_id = f.food_id
                    WHERE oi.order_id = o.order_id
                ) AS ordered_items

            FROM orders o

            JOIN users u
                ON o.user_id = u.user_id

            LEFT JOIN pickup_slots p
                ON o.slot_id = p.slot_id

            ORDER BY o.created_at DESC
        """).fetchall()
        pickup_slots = connection.execute("""
    SELECT *
    FROM pickup_slots
    ORDER BY pickup_time
""").fetchall()

                # MANAGE PICKUP SLOTS

        pickup_slots = connection.execute("""
            SELECT *
            FROM pickup_slots
            ORDER BY pickup_time
        """).fetchall()

    finally:
        connection.close()

    return render_template(
        "admin_dashboard.html",

        admin_name=session.get("admin_name"),

        total_orders=total_orders,
        pending_orders=pending_orders,
        completed_orders=completed_orders,
        total_customers=total_customers,

        recent_orders=recent_orders,
        foods=foods,
        all_orders=all_orders,

        pickup_slots=pickup_slots
    )
# =====================================================
# ADMIN - ADD PICKUP SLOT
# =====================================================
@app.route("/admin-add-pickup-slot", methods=["POST"])
def admin_add_pickup_slot():

    if not session.get("admin_id"):
        return redirect(url_for("admin_login"))

    pickup_time_input = request.form.get(
        "pickup_time", ""
    ).strip().upper()

    capacity = request.form.get("capacity", "").strip()

    try:
        # Convert AM/PM into database format
        pickup_time = datetime.strptime(
            pickup_time_input,
            "%I:%M %p"
        ).strftime("%H:%M")

        capacity = int(capacity)

        if capacity <= 0:
            raise ValueError

    except ValueError:
        return redirect(
            url_for("admin_dashboard", _anchor="pickup-slots")
        )

    connection = get_connection()

    try:
        existing = connection.execute("""
            SELECT slot_id
            FROM pickup_slots
            WHERE pickup_time = ?
        """, (pickup_time,)).fetchone()

        if existing:
            return redirect(
                url_for("admin_dashboard", _anchor="pickup-slots")
            )

        connection.execute("""
            INSERT INTO pickup_slots
            (pickup_time, capacity, active)
            VALUES (?, ?, 1)
        """, (pickup_time, capacity))

        connection.commit()

    finally:
        connection.close()

    return redirect(
        url_for("admin_dashboard", _anchor="pickup-slots")
    )

# =====================================================
# ADMIN - UPDATE PICKUP SLOT
# =====================================================

@app.route("/admin-update-pickup-slot/<int:slot_id>", methods=["POST"])
def admin_update_pickup_slot(slot_id):

    if not session.get("admin_id"):
        return redirect(url_for("admin_login"))

    pickup_time_input = request.form.get(
        "pickup_time", ""
    ).strip().upper()

    capacity = request.form.get("capacity", "").strip()

    try:
        # Convert AM/PM into database format
        pickup_time = datetime.strptime(
            pickup_time_input,
            "%I:%M %p"
        ).strftime("%H:%M")

        capacity = int(capacity)

        if capacity <= 0:
            raise ValueError

    except ValueError:
        return redirect(
            url_for("admin_dashboard", _anchor="pickup-slots")
        )

    connection = get_connection()

    try:
        slot = connection.execute("""
            SELECT slot_id
            FROM pickup_slots
            WHERE slot_id = ?
        """, (slot_id,)).fetchone()

        if slot is None:
            return redirect(
                url_for("admin_dashboard", _anchor="pickup-slots")
            )

        duplicate = connection.execute("""
            SELECT slot_id
            FROM pickup_slots
            WHERE pickup_time = ?
            AND slot_id != ?
        """, (pickup_time, slot_id)).fetchone()

        if duplicate:
            return redirect(
                url_for("admin_dashboard", _anchor="pickup-slots")
            )

        overbooked = connection.execute("""
            SELECT COUNT(*)
            FROM orders
            WHERE slot_id = ?
            AND payment_status = 'paid'
            AND LOWER(order_status) != 'cancelled'
            GROUP BY pickup_date
            HAVING COUNT(*) > ?
            LIMIT 1
        """, (slot_id, capacity)).fetchone()

        if overbooked:
            return redirect(
                url_for("admin_dashboard", _anchor="pickup-slots")
            )

        connection.execute("""
            UPDATE pickup_slots
            SET pickup_time = ?,
                capacity = ?
            WHERE slot_id = ?
        """, (pickup_time, capacity, slot_id))

        connection.commit()

    finally:
        connection.close()

    return redirect(
        url_for("admin_dashboard", _anchor="pickup-slots")
    )


# =====================================================
# ADMIN - ENABLE / DISABLE PICKUP SLOT
# =====================================================

@app.route("/admin-toggle-pickup-slot/<int:slot_id>", methods=["POST"])
def admin_toggle_pickup_slot(slot_id):

    if not session.get("admin_id"):
        return redirect(url_for("admin_login"))

    connection = get_connection()

    try:
        slot = connection.execute("""
            SELECT active
            FROM pickup_slots
            WHERE slot_id = ?
        """, (slot_id,)).fetchone()

        if slot:
            new_status = 0 if slot["active"] == 1 else 1

            connection.execute("""
                UPDATE pickup_slots
                SET active = ?
                WHERE slot_id = ?
            """, (new_status, slot_id))

            connection.commit()

    finally:
        connection.close()

    return redirect(
        url_for("admin_dashboard", _anchor="pickup-slots")
    )


# =====================================================
# ADMIN - VIEW ALL ORDERS (SEPARATE PAGE KEPT)
# =====================================================

@app.route("/admin-orders")
def admin_orders():

    if not session.get("admin_id"):
        return redirect(url_for("admin_login"))

    connection = get_connection()

    try:
        orders = connection.execute("""
            SELECT
                o.order_id,
                o.total,
                o.payment_status,
                o.order_status,
                o.pickup_date,
                o.created_at,

                u.name AS customer_name,
                u.email AS customer_email,
                u.phone AS customer_phone,

                p.pickup_time

            FROM orders o

            JOIN users u
                ON o.user_id = u.user_id

            LEFT JOIN pickup_slots p
                ON o.slot_id = p.slot_id

            ORDER BY o.created_at DESC
        """).fetchall()

    finally:
        connection.close()

    return render_template(
        "admin_orders.html",
        orders=orders
    )


# =====================================================
# ADMIN - VIEW ALL FOOD ITEMS
# =====================================================

@app.route("/admin-foods")
def admin_foods():

    if not session.get("admin_id"):
        return redirect(url_for("admin_login"))

    connection = get_connection()

    try:
        foods = connection.execute("""
            SELECT *
            FROM food_items
            ORDER BY category, name
        """).fetchall()

    finally:
        connection.close()

    return render_template(
        "admin_foods.html",
        foods=foods,
        admin_name=session.get("admin_name")
    )


# =====================================================
# ADMIN - ADD FOOD ITEM
# =====================================================

@app.route("/admin-add-food", methods=["GET", "POST"])
def admin_add_food():

    if not session.get("admin_id"):
        return redirect(url_for("admin_login"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        price = request.form.get("price", "").strip()

        image_file = request.files.get("image")

        if not name or not category or not price:
            return render_template(
                "admin_add_food.html",
                admin_name=session.get("admin_name"),
                message="Please fill in all required fields."
            )

        try:
            price = float(price)

            if price <= 0:
                raise ValueError

        except ValueError:
            return render_template(
                "admin_add_food.html",
                admin_name=session.get("admin_name"),
                message="Please enter a valid price greater than zero."
            )

        image_name = None

        if image_file and image_file.filename:

            allowed_extensions = {
                "png", "jpg", "jpeg", "webp"
            }

            if "." not in image_file.filename:
                return render_template(
                    "admin_add_food.html",
                    admin_name=session.get("admin_name"),
                    message="Invalid image filename."
                )

            extension = image_file.filename.rsplit(
                ".", 1
            )[-1].lower()

            if extension not in allowed_extensions:
                return render_template(
                    "admin_add_food.html",
                    admin_name=session.get("admin_name"),
                    message="Only PNG, JPG, JPEG and WEBP images are allowed."
                )

            image_name = secure_filename(image_file.filename)

            if not image_name:
                return render_template(
                    "admin_add_food.html",
                    admin_name=session.get("admin_name"),
                    message="Invalid image filename."
                )

            image_directory = os.path.join(
                app.root_path,
                "static",
                "images"
            )

            os.makedirs(image_directory, exist_ok=True)

            image_path = os.path.join(
                image_directory,
                image_name
            )

            image_file.save(image_path)

        connection = get_connection()

        try:
            connection.execute("""
                INSERT INTO food_items
                (name, category, price, image, available)
                VALUES (?, ?, ?, ?, 1)
            """, (
                name,
                category,
                price,
                image_name
            ))

            connection.commit()

        finally:
            connection.close()

        return redirect(url_for("admin_dashboard"))

    return render_template(
        "admin_add_food.html",
        admin_name=session.get("admin_name")
    )


# =====================================================
# ADMIN - EDIT FOOD ITEM
# =====================================================

@app.route("/admin-edit-food/<int:food_id>", methods=["GET", "POST"])
def admin_edit_food(food_id):

    if not session.get("admin_id"):
        return redirect(url_for("admin_login"))

    connection = get_connection()

    try:

        food = connection.execute("""
            SELECT *
            FROM food_items
            WHERE food_id = ?
        """, (food_id,)).fetchone()

        if not food:
            return redirect(url_for("admin_dashboard"))

        if request.method == "POST":

            name = request.form.get("name", "").strip()
            category = request.form.get("category", "").strip()
            price = request.form.get("price", "").strip()

            image_file = request.files.get("image")

            if not name or not category or not price:
                return render_template(
                    "admin_edit_food.html",
                    food=food,
                    admin_name=session.get("admin_name"),
                    message="Please fill in all required fields."
                )

            try:
                price = float(price)

                if price <= 0:
                    raise ValueError

            except ValueError:
                return render_template(
                    "admin_edit_food.html",
                    food=food,
                    admin_name=session.get("admin_name"),
                    message="Enter a valid price greater than zero."
                )

            image_name = food["image"]

            if image_file and image_file.filename:

                allowed_extensions = {
                    "png", "jpg", "jpeg", "webp"
                }

                if "." not in image_file.filename:
                    return render_template(
                        "admin_edit_food.html",
                        food=food,
                        admin_name=session.get("admin_name"),
                        message="Invalid image filename."
                    )

                extension = image_file.filename.rsplit(
                    ".", 1
                )[-1].lower()

                if extension not in allowed_extensions:
                    return render_template(
                        "admin_edit_food.html",
                        food=food,
                        admin_name=session.get("admin_name"),
                        message="Only PNG, JPG, JPEG and WEBP images are allowed."
                    )

                image_name = secure_filename(image_file.filename)

                if not image_name:
                    return render_template(
                        "admin_edit_food.html",
                        food=food,
                        admin_name=session.get("admin_name"),
                        message="Invalid image filename."
                    )

                image_directory = os.path.join(
                    app.root_path,
                    "static",
                    "images"
                )

                os.makedirs(image_directory, exist_ok=True)

                image_path = os.path.join(
                    image_directory,
                    image_name
                )

                image_file.save(image_path)

            connection.execute("""
                UPDATE food_items
                SET name = ?,
                    category = ?,
                    price = ?,
                    image = ?
                WHERE food_id = ?
            """, (
                name,
                category,
                price,
                image_name,
                food_id
            ))

            connection.commit()

            return redirect(url_for("admin_dashboard"))

        return render_template(
            "admin_edit_food.html",
            food=food,
            admin_name=session.get("admin_name")
        )

    finally:
        connection.close()


# =====================================================
# ADMIN - ENABLE / DISABLE FOOD
# =====================================================

@app.route("/admin-toggle-food/<int:food_id>", methods=["POST"])
def admin_toggle_food(food_id):

    if not session.get("admin_id"):
        return redirect(url_for("admin_login"))

    connection = get_connection()

    try:

        food = connection.execute("""
            SELECT available
            FROM food_items
            WHERE food_id = ?
        """, (food_id,)).fetchone()

        if food:

            new_status = 0 if food["available"] == 1 else 1

            connection.execute("""
                UPDATE food_items
                SET available = ?
                WHERE food_id = ?
            """, (new_status, food_id))

            connection.commit()

    finally:
        connection.close()

    return redirect(url_for("admin_dashboard"))


# =====================================================
# ADMIN - UPDATE ORDER STATUS
# =====================================================

@app.route("/admin-update-order/<int:order_id>", methods=["POST"])
def admin_update_order(order_id):

    if not session.get("admin_id"):
        return redirect(url_for("admin_login"))

    allowed_statuses = [
        "Paid",
        "Preparing",
        "Ready",
        "Completed",
        "Cancelled"
    ]

    new_status = request.form.get(
        "order_status", ""
    ).strip()

    if new_status not in allowed_statuses:
        return redirect(url_for("admin_dashboard"))

    connection = get_connection()

    try:

        order = connection.execute("""
            SELECT order_id
            FROM orders
            WHERE order_id = ?
        """, (order_id,)).fetchone()

        if order is None:
            return redirect(url_for("admin_dashboard"))

        connection.execute("""
            UPDATE orders
            SET order_status = ?
            WHERE order_id = ?
        """, (new_status, order_id))

        connection.execute("""
            INSERT INTO order_status_history
            (order_id, status, updated_by)
            VALUES (?, ?, ?)
        """, (
            order_id,
            new_status,
            session["admin_id"]
        ))

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return redirect(url_for("admin_dashboard"))


# =====================================================
# ADMIN - VIEW INDIVIDUAL ORDER DETAILS
# =====================================================

@app.route("/admin-order-details/<int:order_id>")
def admin_order_details(order_id):

    if not session.get("admin_id"):
        return redirect(url_for("admin_login"))

    connection = get_connection()

    try:

        order = connection.execute("""
            SELECT
                o.order_id,
                o.total,
                o.payment_status,
                o.order_status,
                o.pickup_date,
                o.created_at,

                u.name AS customer_name,
                u.email AS customer_email,
                u.phone AS customer_phone,

                p.pickup_time

            FROM orders o

            JOIN users u
                ON o.user_id = u.user_id

            LEFT JOIN pickup_slots p
                ON o.slot_id = p.slot_id

            WHERE o.order_id = ?
        """, (order_id,)).fetchone()

        if order is None:
            return redirect(url_for("admin_dashboard"))

        items = connection.execute("""
            SELECT
                f.name AS food_name,
                f.category,
                oi.quantity,
                oi.unit_price,
                (oi.quantity * oi.unit_price) AS subtotal

            FROM order_items oi

            JOIN food_items f
                ON oi.food_id = f.food_id

            WHERE oi.order_id = ?
        """, (order_id,)).fetchall()

        history = connection.execute("""
            SELECT
                status,
                updated_at,
                updated_by

            FROM order_status_history

            WHERE order_id = ?

            ORDER BY updated_at ASC, history_id ASC
        """, (order_id,)).fetchall()

    finally:
        connection.close()

    return render_template(
        "admin_order_details.html",
        order=order,
        items=items,
        history=history
    )


# =====================================================
# ADD FOOD TO CART
# =====================================================

@app.route("/add-to-cart/<int:food_id>", methods=["POST"])
def add_to_cart(food_id):

    if not session.get("user_id"):
        return redirect(url_for("login"))

    connection = get_connection()

    try:
        food = connection.execute("""
            SELECT *
            FROM food_items
            WHERE food_id = ? AND available = 1
        """, (food_id,)).fetchone()

    finally:
        connection.close()

    if food is None:
        return redirect(url_for("menu"))

    cart = session.get("cart", {})

    food_key = str(food_id)

    cart[food_key] = cart.get(food_key, 0) + 1

    session["cart"] = cart

    return redirect(url_for("menu"))


# =====================================================
# VIEW CART
# =====================================================

@app.route("/cart")
def view_cart():

    if not session.get("user_id"):
        return redirect(url_for("login"))

    cart = session.get("cart", {})

    connection = get_connection()

    cart_items = []
    total = 0

    try:

        for food_id, quantity in cart.items():

            food = connection.execute("""
                SELECT *
                FROM food_items
                WHERE food_id = ?
            """, (food_id,)).fetchone()

            if food:

                subtotal = food["price"] * quantity

                cart_items.append({
                    "food_id": food["food_id"],
                    "name": food["name"],
                    "price": food["price"],
                    "quantity": quantity,
                    "subtotal": subtotal
                })

                total += subtotal

    finally:
        connection.close()

    return render_template(
        "cart.html",
        cart_items=cart_items,
        total=total
    )


# =====================================================
# UPDATE CART QUANTITY
# =====================================================

@app.route("/update-cart/<int:food_id>", methods=["POST"])
def update_cart(food_id):

    if not session.get("user_id"):
        return redirect(url_for("login"))

    try:
        quantity = int(request.form.get("quantity", 0))

    except ValueError:
        return redirect(url_for("view_cart"))

    cart = session.get("cart", {})

    food_key = str(food_id)

    if food_key in cart:

        if quantity <= 0:
            cart.pop(food_key)

        elif quantity <= 20:
            cart[food_key] = quantity

    session["cart"] = cart

    return redirect(url_for("view_cart"))


# =====================================================
# CHECKOUT
# =====================================================

@app.route("/checkout", methods=["GET"])
def checkout():

    if not session.get("user_id"):
        return redirect(url_for("login"))

    cart = session.get("cart", {})

    if not cart:
        return redirect(url_for("view_cart"))

    connection = get_connection()

    cart_items = []
    total = 0

    try:

        for food_id, quantity in cart.items():

            food = connection.execute("""
                SELECT *
                FROM food_items
                WHERE food_id = ? AND available = 1
            """, (food_id,)).fetchone()

            if food is None:
                continue

            subtotal = food["price"] * quantity

            cart_items.append({
                "food_id": food["food_id"],
                "name": food["name"],
                "price": food["price"],
                "quantity": quantity,
                "subtotal": subtotal
            })

            total += subtotal

        if not cart_items:
            return redirect(url_for("view_cart"))

        pickup_date = request.args.get(
            "pickup_date",
            date.today().isoformat()
        )

        try:
            selected_date = date.fromisoformat(pickup_date)

            if selected_date < date.today():
                raise ValueError

        except ValueError:
            return redirect(url_for("checkout"))

        slots = connection.execute("""
            SELECT *
            FROM pickup_slots
            WHERE active = 1
            ORDER BY pickup_time
        """).fetchall()

        available_slots = []

        current_time = datetime.now().strftime("%H:%M")

        for slot in slots:

            booked = connection.execute("""
                SELECT COUNT(*)
                FROM orders
                WHERE slot_id = ?
                AND pickup_date = ?
                AND payment_status = 'paid'
                AND LOWER(order_status) != 'cancelled'
            """, (
                slot["slot_id"],
                pickup_date
            )).fetchone()[0]

            remaining = max(
                0,
                slot["capacity"] - booked
            )

            time_passed = (
                selected_date == date.today()
                and slot["pickup_time"] <= current_time
            )

            available_slots.append({
                "slot_id": slot["slot_id"],
                "pickup_time": slot["pickup_time"],

                "display_time": datetime.strptime(
                    slot["pickup_time"],
                    "%H:%M"
                ).strftime("%I:%M %p").lstrip("0"),

                "capacity": slot["capacity"],
                "remaining": remaining,
                "time_passed": time_passed
            })

    finally:
        connection.close()

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        total=total,
        pickup_date=pickup_date,
        today=date.today().isoformat(),
        slots=available_slots,
        checkout_message=session.pop(
            "checkout_message",
            None
        )
    )


# =====================================================
# PLACE ORDER AND SIMULATE PAYMENT
# =====================================================

@app.route("/place-order", methods=["POST"])
def place_order():

    if not session.get("user_id"):
        return redirect(url_for("login"))

    cart = session.get("cart", {})

    if not cart:
        return redirect(url_for("view_cart"))

    pickup_date = request.form.get("pickup_date", "")
    slot_id = request.form.get("slot_id", "")

    try:

        selected_date = date.fromisoformat(pickup_date)
        slot_id = int(slot_id)

        if selected_date < date.today():
            raise ValueError("Please select a valid pickup date.")

    except (ValueError, TypeError):

        session["checkout_message"] = (
            "Invalid pickup date or time."
        )

        return redirect(url_for("checkout"))

    connection = get_connection()

    try:

        connection.execute("BEGIN IMMEDIATE")

        slot = connection.execute("""
            SELECT *
            FROM pickup_slots
            WHERE slot_id = ? AND active = 1
        """, (slot_id,)).fetchone()

        if slot is None:
            raise ValueError(
                "Selected pickup slot is unavailable."
            )

        if (
            selected_date == date.today()
            and slot["pickup_time"] <= datetime.now().strftime("%H:%M")
        ):
            raise ValueError(
                "Please select a future pickup time."
            )

        booked = connection.execute("""
            SELECT COUNT(*)
            FROM orders
            WHERE slot_id = ?
            AND pickup_date = ?
            AND payment_status = 'paid'
            AND LOWER(order_status) != 'cancelled'
        """, (
            slot_id,
            pickup_date
        )).fetchone()[0]

        if booked >= slot["capacity"]:
            raise ValueError(
                "This pickup slot is fully booked."
            )

        order_items = []
        total = 0

        for food_id, quantity in cart.items():

            food = connection.execute("""
                SELECT *
                FROM food_items
                WHERE food_id = ? AND available = 1
            """, (food_id,)).fetchone()

            quantity = int(quantity)

            if food is None or quantity < 1 or quantity > 20:
                raise ValueError(
                    "An item in your cart is unavailable."
                )

            subtotal = food["price"] * quantity

            total += subtotal

            order_items.append({
                "food_id": food["food_id"],
                "quantity": quantity,
                "price": food["price"]
            })

        if not order_items:
            raise ValueError("Your cart is empty.")

        # Simulated payment for academic prototype

        cursor = connection.execute("""
            INSERT INTO orders
            (user_id, slot_id, total, payment_status,
             order_status, pickup_date)
            VALUES (?, ?, ?, 'paid', 'Paid', ?)
        """, (
            session["user_id"],
            slot_id,
            round(total, 2),
            pickup_date
        ))

        order_id = cursor.lastrowid

        # Save order items

        for item in order_items:

            connection.execute("""
                INSERT INTO order_items
                (order_id, food_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
            """, (
                order_id,
                item["food_id"],
                item["quantity"],
                item["price"]
            ))

        # Save simulated payment record

        connection.execute("""
            INSERT INTO payments
            (order_id, amount, payment_status, transaction_reference)
            VALUES (?, ?, 'success', ?)
        """, (
            order_id,
            round(total, 2),
            f"DEMO-{order_id}"
        ))

        # Initial order status history

        connection.execute("""
            INSERT INTO order_status_history
            (order_id, status, updated_by)
            VALUES (?, 'Paid', ?)
        """, (
            order_id,
            session["user_id"]
        ))

        connection.commit()

        session.pop("cart", None)

        return redirect(
            url_for(
                "order_confirmation",
                order_id=order_id
            )
        )

    except (ValueError, sqlite3.IntegrityError) as error:

        connection.rollback()

        session["checkout_message"] = str(error)

        return redirect(
            url_for(
                "checkout",
                pickup_date=pickup_date
            )
        )

    except Exception:

        connection.rollback()

        session["checkout_message"] = (
            "Something went wrong. Please try again."
        )

        return redirect(
            url_for(
                "checkout",
                pickup_date=pickup_date
            )
        )

    finally:
        connection.close()


# =====================================================
# ORDER CONFIRMATION
# =====================================================

@app.route("/order-confirmation/<int:order_id>")
def order_confirmation(order_id):

    if not session.get("user_id"):
        return redirect(url_for("login"))

    connection = get_connection()

    try:

        order = connection.execute("""
            SELECT
                orders.*,
                pickup_slots.pickup_time

            FROM orders

            JOIN pickup_slots
                ON orders.slot_id = pickup_slots.slot_id

            WHERE orders.order_id = ?
            AND orders.user_id = ?
        """, (
            order_id,
            session["user_id"]
        )).fetchone()

        if order is None:
            return redirect(url_for("menu"))

        items = connection.execute("""
            SELECT
                food_items.name,
                order_items.quantity,
                order_items.unit_price

            FROM order_items

            JOIN food_items
                ON order_items.food_id = food_items.food_id

            WHERE order_items.order_id = ?
        """, (order_id,)).fetchall()

    finally:
        connection.close()

    pickup_time = datetime.strptime(
        order["pickup_time"],
        "%H:%M"
    ).strftime("%I:%M %p").lstrip("0")

    return render_template(
        "order_confirmation.html",
        order=order,
        items=items,
        pickup_time=pickup_time
    )


# =====================================================
# CUSTOMER - MY ORDERS
# =====================================================

@app.route("/my-orders")
def my_orders():

    if not session.get("user_id"):
        return redirect(url_for("login"))

    connection = get_connection()

    formatted_orders = []

    try:

        orders = connection.execute("""
            SELECT
                orders.order_id,
                orders.total,
                orders.payment_status,
                orders.order_status,
                orders.pickup_date,
                orders.created_at,
                pickup_slots.pickup_time

            FROM orders

            JOIN pickup_slots
                ON orders.slot_id = pickup_slots.slot_id

            WHERE orders.user_id = ?

            ORDER BY orders.created_at DESC
        """, (session["user_id"],)).fetchall()

        for order in orders:

            order_data = dict(order)

            order_data["display_time"] = datetime.strptime(
                order["pickup_time"],
                "%H:%M"
            ).strftime("%I:%M %p").lstrip("0")

            items = connection.execute("""
                SELECT
                    food_items.name,
                    order_items.quantity,
                    order_items.unit_price

                FROM order_items

                JOIN food_items
                    ON order_items.food_id = food_items.food_id

                WHERE order_items.order_id = ?
            """, (order["order_id"],)).fetchall()

            order_data["order_items"] = items

            formatted_orders.append(order_data)

    finally:
        connection.close()

    return render_template(
        "my_orders.html",
        orders=formatted_orders
    )


# =====================================================
# ADMIN LOGOUT
# =====================================================

@app.route("/admin-logout")
def admin_logout():

    session.pop("admin_id", None)
    session.pop("admin_name", None)

    return redirect(url_for("admin_login"))


# =====================================================
# CUSTOMER LOGOUT
# =====================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


# =====================================================
# RUN FLASK APPLICATION
# =====================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )