from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    role = db.Column(db.String(20), default='user')  # admin, user
    last_login = db.Column(db.DateTime)
    
    # Relationships
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'))
    store = db.relationship('Store', back_populates='users')
    inventory_requests = db.relationship('InventoryRequest', back_populates='user')
    login_history = db.relationship('UserLogin', back_populates='user', lazy='dynamic')

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class UserLogin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    login_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))  # IPv6 can be up to 45 chars
    user_agent = db.Column(db.String(200))
    
    # Relationship
    user = db.relationship('User', back_populates='login_history')

class Store(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    vat_number = db.Column(db.String(50))
    email = db.Column(db.String(120))
    operating_hours = db.Column(db.Text)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default="Open")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = db.relationship('User', back_populates='store')
    products = db.relationship('Product', back_populates='store')
    suppliers = db.relationship('Supplier', back_populates='store')
    categories = db.relationship('Category', back_populates='store', cascade='all, delete-orphan')
    orders = db.relationship('Order', back_populates='store')
    audit_logs = db.relationship('StoreAuditLog', back_populates='store')

class StoreAuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    store = db.relationship('Store', back_populates='audit_logs')
    user = db.relationship('User', backref=db.backref('store_audit_logs'))

    def __repr__(self):
        return f'<StoreAuditLog {self.action}>'

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Store relationship
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    store = db.relationship('Store', back_populates='categories')
    
    # Products relationship
    products = db.relationship('Product', back_populates='category', lazy='dynamic')

    def __str__(self):
        return self.name

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Store relationship
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    store = db.relationship('Store', back_populates='suppliers')
    
    # Products relationship
    products = db.relationship('Product', back_populates='supplier')
    
    # Orders relationship
    orders = db.relationship('Order', back_populates='supplier')

    def __str__(self):
        return self.name

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    sku = db.Column(db.String(50), unique=True)
    quantity = db.Column(db.Integer, default=0)
    min_threshold = db.Column(db.Integer, default=5)
    price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Store relationship
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    store = db.relationship('Store', back_populates='products')
    
    # Supplier relationship
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    supplier = db.relationship('Supplier', back_populates='products')
    
    # Category relationship
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    category = db.relationship('Category', back_populates='products')
    
    # Inventory requests relationship
    inventory_requests = db.relationship('InventoryRequest', back_populates='product')
    
    # Orders relationship
    orders = db.relationship('Order', back_populates='product')

    @property
    def is_low_stock(self):
        """Returns True if quantity is less than or equal to min_threshold"""
        if self.quantity is None or self.min_threshold is None:
            return False
        return self.quantity <= self.min_threshold

    def __str__(self):
        return self.name

class Order(db.Model):
    __table_args__ = (
        db.Index('idx_store_status_date', 'store_id', 'status', 'order_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False, index=True)
    quantity_ordered = db.Column(db.Integer, nullable=False)
    total_cost = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)  # pending, confirmed, shipped, delivered, cancelled
    order_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    notes = db.Column(db.Text)

    # Relationships with eager loading for better performance
    store = db.relationship('Store', back_populates='orders', lazy='joined')
    product = db.relationship('Product', back_populates='orders', lazy='joined')
    supplier = db.relationship('Supplier', back_populates='orders', lazy='joined')

    def __repr__(self):
        return f'<Order {self.id} - {self.product.name}>'

class InventoryRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, completed
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    product = db.relationship('Product', back_populates='inventory_requests')
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', back_populates='inventory_requests') 