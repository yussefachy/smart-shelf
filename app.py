import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from models import db, User, Store, Product, Supplier, InventoryRequest, UserLogin, Order, Category, StoreAuditLog
from config import Config
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from datetime import datetime, timedelta
from flask_mail import Message, Mail
import logging
from logging.handlers import RotatingFileHandler

# Load environment variables from .env file
load_dotenv()

# Configure logging
if not os.path.exists('logs'):
    os.mkdir('logs')
file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)

# Configure application logger
logger = logging.getLogger('app')
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.info('Smart Shelf startup')

# Print environment variables at startup
print("Environment variables loaded:")
print(f"MAIL_SERVER: {os.getenv('MAIL_SERVER')}")
print(f"MAIL_PORT: {os.getenv('MAIL_PORT')}")
print(f"MAIL_USERNAME: {os.getenv('MAIL_USERNAME')}")
print(f"MAIL_PASSWORD: {'*' * len(os.getenv('MAIL_PASSWORD', ''))}")  # Hide password but show length

app = Flask(__name__)
app.config.from_object(Config)

# Add logging to Flask app
app.logger.addHandler(file_handler)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
mail = Mail(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def send_email(to_email, subject, body):
    # Log email configuration (without sensitive data)
    logger.info(f"Attempting to send email to {to_email} with subject: {subject}")
    logger.debug(f"Email configuration - MAIL_SERVER: {os.getenv('MAIL_SERVER')}, MAIL_PORT: {os.getenv('MAIL_PORT')}, MAIL_USERNAME: {os.getenv('MAIL_USERNAME')}")
    
    # Check if environment variables are set
    if not os.getenv('MAIL_SERVER') or not os.getenv('MAIL_PORT') or not os.getenv('MAIL_USERNAME') or not os.getenv('MAIL_PASSWORD'):
        logger.error("Missing email configuration in .env file")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = os.getenv('MAIL_USERNAME')
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Connect to SMTP server
        logger.info(f"Connecting to SMTP server {os.getenv('MAIL_SERVER')}:{os.getenv('MAIL_PORT')}")
        server = smtplib.SMTP(os.getenv('MAIL_SERVER'), int(os.getenv('MAIL_PORT')))
        server.ehlo()  # Identify yourself to the server
        logger.debug("Connected to SMTP server and sent EHLO")
        
        # Start TLS
        logger.debug("Starting TLS connection")
        server.starttls()
        server.ehlo()  # Re-identify yourself over TLS connection
        logger.debug("TLS connection established")
        
        # Login
        logger.debug(f"Attempting to login as {os.getenv('MAIL_USERNAME')}")
        server.login(os.getenv('MAIL_USERNAME'), os.getenv('MAIL_PASSWORD'))
        logger.debug("SMTP login successful")
        
        # Send email
        logger.info("Sending email message")
        server.send_message(msg)
        logger.info(f"Email sent successfully to {to_email}")
        
        # Quit
        server.quit()
        logger.debug("SMTP connection closed")
        
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        logger.exception("Full traceback of email sending error:")
        return False

# Create database tables
def init_db():
    with app.app_context():
        # Drop all tables
        db.drop_all()
        # Create all tables
        db.create_all()
        
        # Create admin user if it doesn't exist
        admin = User.query.filter_by(email='admin@example.com').first()
        if not admin:
            admin = User(
                email='admin@example.com',
                first_name='Admin',
                last_name='User',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            # Update last login time
            user.last_login = datetime.utcnow()
            
            # Record login history
            login_record = UserLogin(
                user=user,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(login_record)
            db.session.commit()
            
            login_user(user, remember=True)
            return redirect(url_for('dashboard'))
        
        flash('Invalid email or password')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email address already exists')
            return redirect(url_for('signup'))

        new_user = User(
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for('create_store'))

    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    if not current_user.store:
        flash('Please create a store first.')
        return redirect(url_for('create_store'))
    
    # Get all products for the current user's store
    products = Product.query.filter_by(store_id=current_user.store.id).all()
    
    # Get low stock products (where quantity is below min_threshold)
    low_stock_products = [p for p in products if p.quantity <= p.min_threshold]
    
    # Get recent inventory requests (last 5)
    inventory_requests = InventoryRequest.query.join(Product)\
        .filter(Product.store_id == current_user.store.id)\
        .order_by(InventoryRequest.created_at.desc())\
        .limit(5)\
        .all()
    
    # Get pending orders count
    pending_orders_count = Order.query.filter_by(
        store_id=current_user.store.id,
        status='pending'
    ).count()
    
    # Calculate total value of inventory
    total_inventory_value = sum(p.quantity * p.price for p in products)
    
    # Get total number of suppliers
    total_suppliers = Supplier.query.filter_by(store_id=current_user.store.id).count()
    
    # Get total number of products
    total_products = len(products)
    
    return render_template('dashboard.html',
                         products=products,
                         low_stock_products=low_stock_products,
                         inventory_requests=inventory_requests,
                         pending_orders_count=pending_orders_count,
                         total_inventory_value=total_inventory_value,
                         total_suppliers=total_suppliers,
                         total_products=total_products)

@app.route('/create-store', methods=['GET', 'POST'])
@login_required
def create_store():
    if request.method == 'POST':
        store = Store(
            name=request.form.get('name'),
            address=request.form.get('address'),
            phone=request.form.get('phone')
        )
        current_user.store = store
        db.session.add(store)
        db.session.commit()
        
        flash('Store created successfully!')
        return redirect(url_for('dashboard'))
    
    return render_template('create_store.html')

@app.route('/inventory')
@login_required
def inventory():
    if not current_user.store:
        flash('Please create or join a store first.')
        return redirect(url_for('create_store'))
    
    products = Product.query.filter_by(store_id=current_user.store.id).all()
    
    # Debug: Print product details
    for product in products:
        print(f"Product: {product.name}")
        print(f"Quantity: {product.quantity}")
        print(f"Min Threshold: {product.min_threshold}")
        print(f"Is Low Stock: {product.is_low_stock}")
        print("------------------------")
    
    return render_template('inventory.html', products=products)

@app.route('/add-product', methods=['GET', 'POST'])
@login_required
def add_product():
    if not current_user.store:
        flash('Please create or join a store first.')
        return redirect(url_for('create_store'))
    
    if request.method == 'POST':
        # Check if supplier exists, if not create one
        supplier = Supplier.query.filter_by(
            email=request.form.get('supplier_email'),
            store_id=current_user.store.id
        ).first()
        
        if not supplier:
            supplier = Supplier(
                email=request.form.get('supplier_email'),
                name=request.form.get('supplier_email').split('@')[0],  # Temporary name
                store_id=current_user.store.id
            )
            db.session.add(supplier)
        
        # Create new product
        product = Product(
            name=request.form.get('name'),
            quantity=int(request.form.get('quantity')),
            min_threshold=int(request.form.get('min_threshold')),
            price=float(request.form.get('price')),
            store_id=current_user.store.id,
            supplier=supplier
        )
        db.session.add(product)
        db.session.commit()
        
        flash('Product added successfully!')
        return redirect(url_for('inventory'))
    
    return render_template('add_product.html')

@app.route('/request-inventory/<int:product_id>', methods=['POST'])
@login_required
def request_inventory(product_id):
    product = Product.query.get_or_404(product_id)
    if product.store_id != current_user.store.id:
        flash('Access denied.')
        return redirect(url_for('inventory'))
    
    quantity = int(request.form.get('quantity', 0))
    if quantity <= 0:
        flash('Please enter a valid quantity.')
        return redirect(url_for('inventory'))
    
    inventory_request = InventoryRequest(
        product_id=product_id,
        user_id=current_user.id,
        quantity=quantity,
        notes=request.form.get('notes')
    )
    db.session.add(inventory_request)
    db.session.commit()
    
    flash('Inventory request submitted successfully!')
    return redirect(url_for('inventory'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/test-email')
def test_email():
    try:
        result = send_email(
            to_email=os.getenv('MAIL_USERNAME'),  # Send to yourself as a test
            subject='Test Email from Smart Shelf',
            body='This is a test email from your Smart Shelf application. If you receive this, your email configuration is working correctly!'
        )
        if result:
            return 'Test email sent successfully! Check your inbox.'
        else:
            return 'Failed to send test email. Check the console for errors.'
    except Exception as e:
        return f'Error sending test email: {str(e)}'

@app.route('/contact-supplier/<int:product_id>', methods=['GET', 'POST'])
@login_required
def contact_supplier(product_id):
    if not current_user.store:
        return redirect(url_for('setup'))
    
    product = Product.query.get_or_404(product_id)
    
    # Check if the product belongs to the current user's store
    if product.store_id != current_user.store.id:
        flash('You do not have permission to access this product.')
        return redirect(url_for('inventory'))
    
    if request.method == 'POST':
        message = request.form.get('message')
        quantity = request.form.get('quantity', type=int)
        
        if not message or not quantity or quantity < 1:
            flash('Please provide both a valid message and quantity.', 'error')
            return redirect(url_for('contact_supplier', product_id=product_id))
            
        try:
            # Create an inventory request for supplier order
            inventory_request = InventoryRequest(
                product_id=product.id,
                user_id=current_user.id,
                quantity=quantity,
                status='pending',  # Set as pending since we're waiting for supplier
                notes=f"Supplier order requested: {message}"
            )
            db.session.add(inventory_request)
            
            # Create a pending order
            order = Order(
                store_id=current_user.store.id,
                product_id=product.id,
                supplier_id=product.supplier_id,
                quantity_ordered=quantity,
                total_cost=quantity * product.price,
                status='pending',  # Set as pending since we're waiting for supplier
                notes=f"Order requested from supplier: {message}"
            )
            db.session.add(order)
            
            # Send email to supplier
            msg = Message(
                subject=f'Product Order Request: {product.name}',
                sender=current_user.email,
                recipients=[product.supplier.email]
            )
            msg.body = f"Order Details:\nProduct: {product.name}\nRequested Quantity: {quantity} units\n\nMessage:\n{message}"
            mail.send(msg)
            
            db.session.commit()
            flash('Message sent successfully to the supplier and order recorded!', 'success')
            return redirect(url_for('inventory'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error sending email: {str(e)}")
            flash('Failed to send message. Please try again later.', 'error')
            return redirect(url_for('contact_supplier', product_id=product_id))
    
    return render_template('contact_supplier.html', product=product)

@app.route('/order-more/<int:product_id>', methods=['GET', 'POST'])
@login_required
def order_more(product_id):
    if not current_user.store:
        return redirect(url_for('setup'))
    
    product = Product.query.get_or_404(product_id)
    
    # Check if the product belongs to the current user's store
    if product.store_id != current_user.store.id:
        flash('You do not have permission to access this product.')
        return redirect(url_for('inventory'))
    
    if request.method == 'POST':
        quantity = int(request.form.get('quantity', 0))
        
        if quantity <= 0:
            flash('Please enter a valid quantity.')
            return redirect(url_for('order_more', product_id=product.id))
        
        # Create an inventory request for manual addition
        inventory_request = InventoryRequest(
            product_id=product.id,
            user_id=current_user.id,
            quantity=quantity,
            status='completed',  # Mark as completed since we're adding stock immediately
            notes=f"Manual stock addition of {quantity} units"
        )
        db.session.add(inventory_request)
        
        # Create an order record
        order = Order(
            store_id=current_user.store.id,
            product_id=product.id,
            supplier_id=product.supplier_id,
            quantity_ordered=quantity,
            total_cost=quantity * product.price,
            status='delivered',  # Since we're directly adding to inventory
            notes=f"Manual inventory addition of {quantity} units"
        )
        db.session.add(order)
        
        # Update product quantity
        product.quantity += quantity
        product.last_updated = datetime.utcnow()
        
        # Check if there's a pending inventory request for this product
        pending_request = InventoryRequest.query.filter_by(
            product_id=product.id,
            status='pending'
        ).first()
        
        if pending_request:
            # If the added quantity satisfies the request, mark it as completed
            if product.quantity >= product.min_threshold:
                pending_request.status = 'completed'
                pending_request.notes = f"{pending_request.notes}\nCompleted: Received {quantity} units on {datetime.utcnow()}"
            else:
                pending_request.notes = f"{pending_request.notes}\nPartial: Received {quantity} units on {datetime.utcnow()}"
        
        db.session.commit()
        
        flash(f'Added {quantity} units of {product.name} to inventory. New quantity: {product.quantity}')
        return redirect(url_for('inventory'))
    
    return render_template('order_more.html', product=product)

@app.route('/order-history')
@login_required
def order_history():
    if not current_user.store:
        flash('Please create a store first.', 'warning')
        return redirect(url_for('create_store'))

    # Get filter parameters
    status = request.args.get('status')
    date_filter = request.args.get('date')
    search = request.args.get('search')

    # Base query
    query = Order.query.filter_by(store_id=current_user.store.id)

    # Apply status filter
    if status:
        query = query.filter(Order.status == status)

    # Apply date filter
    today = datetime.now().date()
    if date_filter == 'today':
        query = query.filter(db.func.date(Order.order_date) == today)
    elif date_filter == 'week':
        week_ago = today - timedelta(days=7)
        query = query.filter(db.func.date(Order.order_date) >= week_ago)
    elif date_filter == 'month':
        month_ago = today - timedelta(days=30)
        query = query.filter(db.func.date(Order.order_date) >= month_ago)
    elif date_filter == 'year':
        year_ago = today - timedelta(days=365)
        query = query.filter(db.func.date(Order.order_date) >= year_ago)

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.join(Product).join(Supplier).filter(
            db.or_(
                Product.name.ilike(search_term),
                Supplier.name.ilike(search_term),
                Order.notes.ilike(search_term)
            )
        )

    # Order by most recent first
    orders = query.order_by(Order.order_date.desc()).all()
    
    return render_template('order_history.html', orders=orders)

@app.route('/orders/<int:order_id>/status', methods=['POST'])
@login_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Check if the order belongs to the user's store
    if order.store_id != current_user.store.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    new_status = data.get('status')
    
    # Validate the status transition
    valid_transitions = {
        'pending': ['confirmed', 'cancelled'],
        'confirmed': ['shipped'],
        'shipped': ['delivered'],
        'delivered': [],  # Terminal state
        'cancelled': []   # Terminal state
    }
    
    if new_status not in valid_transitions.get(order.status, []):
        return jsonify({'error': 'Invalid status transition'}), 400
    
    # Update the order status
    order.status = new_status
    
    # If order is delivered, update the product quantity
    if new_status == 'delivered':
        order.product.quantity += order.quantity_ordered
        
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Order status updated successfully'})

@app.context_processor
def inject_low_stock_data():
    """Make low stock products data available to all templates."""
    if current_user.is_authenticated and current_user.store:
        products = Product.query.filter_by(store_id=current_user.store.id).all()
        low_stock_products = [p for p in products if p.quantity <= p.min_threshold]
        return {
            'low_stock_products': low_stock_products,
            'low_stock_count': len(low_stock_products)
        }
    return {
        'low_stock_products': [],
        'low_stock_count': 0
    }

@app.route('/reduce-inventory/<int:product_id>', methods=['POST'])
@login_required
def reduce_inventory(product_id):
    if not current_user.store:
        return jsonify({'error': 'No store found'}), 400
    
    product = Product.query.get_or_404(product_id)
    
    # Check if the product belongs to the current user's store
    if product.store_id != current_user.store.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        quantity = int(request.form.get('quantity', 0))
        if quantity <= 0:
            return jsonify({'error': 'Invalid quantity'}), 400
        
        if quantity > product.quantity:
            return jsonify({'error': 'Not enough stock'}), 400
        
        # Reduce product quantity
        product.quantity -= quantity
        product.last_updated = datetime.utcnow()
        
        # Create an order record for the reduction
        order = Order(
            store_id=current_user.store.id,
            product_id=product.id,
            supplier_id=product.supplier_id,
            quantity_ordered=-quantity,  # Negative to indicate reduction
            total_cost=quantity * product.price,
            status='completed',
            notes=f"Manual inventory reduction of {quantity} units"
        )
        db.session.add(order)
        
        # If this reduction puts us below threshold, create an inventory request
        if product.quantity <= product.min_threshold:
            inventory_request = InventoryRequest(
                product_id=product.id,
                user_id=current_user.id,
                quantity=product.min_threshold - product.quantity,
                status='pending',
                notes=f"Auto-generated request due to low stock (Current: {product.quantity}, Min: {product.min_threshold})"
            )
            db.session.add(inventory_request)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Removed {quantity} units. New quantity: {product.quantity}',
            'new_quantity': product.quantity,
            'is_low_stock': product.quantity <= product.min_threshold
        })
        
    except ValueError:
        return jsonify({'error': 'Invalid quantity format'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/categories')
@login_required
def categories():
    if not current_user.store:
        flash('Please create a store first.')
        return redirect(url_for('create_store'))
    
    categories = Category.query.filter_by(store_id=current_user.store.id).all()
    return render_template('categories.html', categories=categories)

@app.route('/add-category', methods=['GET', 'POST'])
@login_required
def add_category():
    if not current_user.store:
        flash('Please create a store first.')
        return redirect(url_for('create_store'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if not name:
            flash('Category name is required.')
            return redirect(url_for('add_category'))
        
        category = Category(
            name=name,
            description=description,
            store_id=current_user.store.id
        )
        db.session.add(category)
        db.session.commit()
        
        flash('Category added successfully!')
        return redirect(url_for('categories'))
    
    return render_template('add_category.html')

@app.route('/edit-category/<int:category_id>', methods=['GET', 'POST'])
@login_required
def edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    
    if category.store_id != current_user.store.id:
        flash('Access denied.')
        return redirect(url_for('categories'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if not name:
            flash('Category name is required.')
            return redirect(url_for('edit_category', category_id=category.id))
        
        category.name = name
        category.description = description
        db.session.commit()
        
        flash('Category updated successfully!')
        return redirect(url_for('categories'))
    
    return render_template('edit_category.html', category=category)

@app.route('/delete-category/<int:category_id>', methods=['POST'])
@login_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    
    if category.store_id != current_user.store.id:
        flash('Access denied.')
        return redirect(url_for('categories'))
    
    # Check if category has any products
    if category.products.count() > 0:
        flash('Cannot delete category that has products.')
        return redirect(url_for('categories'))
    
    db.session.delete(category)
    db.session.commit()
    
    flash('Category deleted successfully!')
    return redirect(url_for('categories'))

@app.route('/suppliers')
@login_required
def suppliers():
    if not current_user.store:
        flash('Please create a store first.', 'error')
        return redirect(url_for('create_store'))
    
    suppliers = Supplier.query.filter_by(store_id=current_user.store.id).order_by(Supplier.name).all()
    return render_template('suppliers.html', suppliers=suppliers)

@app.route('/suppliers/add', methods=['GET', 'POST'])
@login_required
def add_supplier():
    if not current_user.store:
        flash('Please create a store first.', 'error')
        return redirect(url_for('create_store'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        
        if not name or not email:
            flash('Name and email are required.', 'error')
            return redirect(url_for('add_supplier'))
        
        # Check if supplier with same email already exists for this store
        existing_supplier = Supplier.query.filter_by(
            store_id=current_user.store.id,
            email=email
        ).first()
        
        if existing_supplier:
            flash('A supplier with this email already exists.', 'error')
            return redirect(url_for('add_supplier'))
        
        supplier = Supplier(
            store_id=current_user.store.id,
            name=name,
            email=email,
            phone=phone,
            address=address
        )
        
        db.session.add(supplier)
        db.session.commit()
        
        flash('Supplier added successfully.', 'success')
        return redirect(url_for('suppliers'))
    
    return render_template('supplier_form.html')

@app.route('/suppliers/<int:supplier_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_supplier(supplier_id):
    if not current_user.store:
        flash('Please create a store first.', 'error')
        return redirect(url_for('create_store'))
    
    supplier = Supplier.query.filter_by(
        id=supplier_id,
        store_id=current_user.store.id
    ).first_or_404()
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        
        if not name or not email:
            flash('Name and email are required.', 'error')
            return redirect(url_for('edit_supplier', supplier_id=supplier_id))
        
        # Check if another supplier with same email exists for this store
        existing_supplier = Supplier.query.filter(
            Supplier.store_id == current_user.store.id,
            Supplier.email == email,
            Supplier.id != supplier_id
        ).first()
        
        if existing_supplier:
            flash('Another supplier with this email already exists.', 'error')
            return redirect(url_for('edit_supplier', supplier_id=supplier_id))
        
        supplier.name = name
        supplier.email = email
        supplier.phone = phone
        supplier.address = address
        
        db.session.commit()
        
        flash('Supplier updated successfully.', 'success')
        return redirect(url_for('suppliers'))
    
    return render_template('supplier_form.html', supplier=supplier)

@app.route('/suppliers/<int:supplier_id>/delete', methods=['POST'])
@login_required
def delete_supplier(supplier_id):
    if not current_user.store:
        flash('Please create a store first.', 'error')
        return redirect(url_for('create_store'))
    
    supplier = Supplier.query.filter_by(
        id=supplier_id,
        store_id=current_user.store.id
    ).first_or_404()
    
    # Check if supplier has any associated products
    products = Product.query.filter_by(supplier_id=supplier_id).first()
    if products:
        flash('Cannot delete supplier as they have associated products.', 'error')
        return redirect(url_for('suppliers'))
    
    # Check if supplier has any associated orders
    orders = Order.query.filter_by(supplier_id=supplier_id).first()
    if orders:
        flash('Cannot delete supplier as they have associated orders.', 'error')
        return redirect(url_for('suppliers'))
    
    db.session.delete(supplier)
    db.session.commit()
    
    flash('Supplier deleted successfully.', 'success')
    return redirect(url_for('suppliers'))

@app.route('/products')
@login_required
def products():
    if not current_user.store:
        flash('Please create a store first.')
        return redirect(url_for('create_store'))
    
    # Get all products for the current user's store
    products = Product.query.filter_by(store_id=current_user.store.id)\
        .order_by(Product.name)\
        .all()
    
    return render_template('products.html', products=products)

@app.route('/store', methods=['GET', 'POST'])
@login_required
def store_settings():
    if not current_user.store:
        flash('Please create a store first.', 'error')
        return redirect(url_for('create_store'))

    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'store_details':
            # Update store details
            store = current_user.store
            old_name = store.name
            
            # Update fields
            store.name = request.form.get('name')
            store.vat_number = request.form.get('vat_number')
            store.phone = request.form.get('phone')
            store.email = request.form.get('email')
            store.operating_hours = request.form.get('operating_hours')
            store.address = request.form.get('address')
            store.notes = request.form.get('notes')
            store.status = request.form.get('status')
            
            # Create audit log entry for changes
            changes = []
            if old_name != store.name:
                changes.append(f"Changed store name from '{old_name}' to '{store.name}'")
            
            if changes:
                audit_log = StoreAuditLog(
                    store=store,
                    user=current_user,
                    action=", ".join(changes)
                )
                db.session.add(audit_log)
            
            db.session.commit()
            flash('Store details updated successfully.', 'success')
            
        elif form_type == 'change_password':
            # Validate current password
            if not current_user.check_password(request.form.get('current_password')):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('store_settings'))
            
            # Validate new password
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('store_settings'))
            
            # Update password
            current_user.set_password(new_password)
            
            # Create audit log entry
            audit_log = StoreAuditLog(
                store=current_user.store,
                user=current_user,
                action="Changed password"
            )
            db.session.add(audit_log)
            db.session.commit()
            
            flash('Password updated successfully.', 'success')
    
    return render_template('store.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'profile_info':
            # Update profile information
            current_user.full_name = request.form.get('full_name')
            current_user.email = request.form.get('email')
            current_user.phone = request.form.get('phone')
            current_user.bio = request.form.get('bio')
            
            # Handle profile picture upload if implemented
            # if 'profile_picture' in request.files:
            #     file = request.files['profile_picture']
            #     if file and allowed_file(file.filename):
            #         filename = secure_filename(file.filename)
            #         file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            #         current_user.profile_picture = filename
            
            db.session.commit()
            flash('Profile updated successfully', 'success')
            return redirect(url_for('profile'))
            
        elif form_type == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if not current_user.check_password(current_password):
                flash('Current password is incorrect', 'error')
                return redirect(url_for('profile'))
                
            if new_password != confirm_password:
                flash('New passwords do not match', 'error')
                return redirect(url_for('profile'))
                
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password updated successfully', 'success')
            return redirect(url_for('profile'))
    
    return render_template('profile.html')

if __name__ == '__main__':
    import sys
    
    # Check if --recreate-db flag is present
    if '--recreate-db' in sys.argv:
        print("Recreating database...")
        init_db()
        print("Database recreated successfully!")
        sys.exit(0)
    
    init_db()
    app.run(debug=True) 