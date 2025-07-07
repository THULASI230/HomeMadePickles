from flask import Flask, render_template, request, redirect, url_for, session
import boto3
import smtplib
import logging
from email.mime.text import MIMEText
from datetime import datetime
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import os

# -------------------- Config --------------------

app = Flask(__name__)
app.secret_key = 'simple_secure_key_9472'

# AWS Configuration
AWS_REGION = 'ap-south-1'
DYNAMODB_TABLE = 'PickleOrders'

# Email settings
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USER = 'tthulasireddy2305@gmail.com'
EMAIL_PASSWORD = 'eihw cajl zhqf qmyo'

# -------------------- Logger Setup --------------------

log_folder = 'logs'
os.makedirs(log_folder, exist_ok=True)
log_file = os.path.join(log_folder, 'app.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# -------------------- AWS Setup --------------------

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
orders_table = dynamodb.Table(DYNAMODB_TABLE)
users_table = dynamodb.Table('users')

sns = boto3.client('sns', region_name=AWS_REGION)

# -------------------- Helper Functions --------------------

def send_order_email(to_email, order_summary):
    try:
        msg = MIMEText(order_summary)
        msg['Subject'] = 'Your Order Confirmation'
        msg['From'] = EMAIL_USER
        msg['To'] = to_email

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)

        logger.info("Order email sent to %s", to_email)
    except Exception as e:
        logger.error("Failed to send email: %s", e)

def save_order_to_dynamodb(order_data):
    try:
        orders_table.put_item(Item=order_data)
        logger.info("Order saved to DynamoDB: %s", order_data['order_id'])
    except Exception as e:
        logger.error("DynamoDB error: %s", e)

# -------------------- Routes --------------------

@app.route('/')
def home():
    return render_template("home.html")

@app.route('/signup.html', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        response = users_table.get_item(Key={'username': username})
        if 'Item' in response:
            return render_template('signup.html', error="Username already exists.")

        hashed_password = generate_password_hash(password)
        users_table.put_item(Item={
            'username': username,
            'email': email,
            'password': hashed_password
        })
        return redirect(url_for('login'))

    return render_template("signup.html")

@app.route('/login.html', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('name')
        password = request.form.get('password')

        response = users_table.get_item(Key={'username': username})
        user = response.get('Item')

        if user and check_password_hash(user['password'], password):
            session['username'] = username
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="❌ Invalid credentials")

    return render_template("login.html")


@app.route('/index.html')
def index():
    return render_template("index.html")

@app.route('/veg-pickles.html')
def veg_pickles():
    return render_template("veg-pickles.html")

@app.route('/nonveg-pickles.html')
def nonveg_pickles():
    return render_template("nonveg-pickles.html")

@app.route('/snacks.html')
def snacks():
    return render_template("snacks.html")

@app.route('/cart.html')
def cart():
    cart = session.get('cart', [])
    total = sum(item['price'] * item['quantity'] for item in cart)
    return render_template("cart.html", cart=cart, total=total)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product = request.form.get('product')
    price = float(request.form.get('price'))
    quantity = int(request.form.get('quantity', 1))

    cart = session.get('cart', [])

    for item in cart:
        if item['product'] == product:
            item['quantity'] += quantity
            break
    else:
        cart.append({'product': product, 'price': price, 'quantity': quantity})

    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/clear_cart', methods=['POST'])
def clear_cart():
    session.pop('cart', None)
    return redirect(url_for('cart'))

@app.route('/checkout.html', methods=['GET', 'POST'])
def checkout():
    cart = session.get('cart', [])
    if not cart:
        return redirect(url_for('cart'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        address = request.form['address']
        order_id = str(uuid.uuid4())
        order_time = datetime.now().isoformat()
        total = sum(item['price'] * item['quantity'] for item in cart)

        order_data = {
            'order_id': order_id,
            'name': name,
            'email': email,
            'address': address,
            'order_time': order_time,
            'items': cart,
            'total': total
        }

        save_order_to_dynamodb(order_data)

        summary = f"Order ID: {order_id}\nName: {name}\nTotal: ₹{total}\n\nThank you for your order!"
        send_order_email(email, summary)

        session.pop('cart', None)
        return render_template('order_success.html')

    total = sum(item['price'] * item['quantity'] for item in cart)
    return render_template("checkout.html", cart=cart, total=total)

@app.route('/contact.html', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        logger.info(f"Contact Message from {name}: {message}")
        return render_template("contact.html", success=True)
    return render_template("contact.html")

@app.route('/about.html')
def about():
    return render_template("about.html")

# -------------------- Error Pages --------------------

@app.errorhandler(404)
def not_found_error(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('500.html'), 500

# -------------------- Run --------------------

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)