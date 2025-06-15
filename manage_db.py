from flask import Flask
from models import db, User, Store, Product, Supplier, InventoryRequest, UserLogin
from werkzeug.security import generate_password_hash
import click

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smart_shelf.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

@click.group()
def cli():
    """Database management commands for Smart Shelf"""
    pass

@cli.command()
def init():
    """Initialize the database"""
    with app.app_context():
        db.create_all()
        click.echo('Database initialized!')

@cli.command()
def create_admin():
    """Create an admin user"""
    with app.app_context():
        admin = User.query.filter_by(email='admin@example.com').first()
        if admin:
            click.echo('Admin user already exists!')
            return
        
        admin = User(
            email='admin@example.com',
            first_name='Admin',
            last_name='User',
            role='admin'
        )
        admin.password = generate_password_hash('admin123')
        db.session.add(admin)
        db.session.commit()
        click.echo('Admin user created successfully!')

@cli.command()
def list_users():
    """List all users"""
    with app.app_context():
        users = User.query.all()
        click.echo('\nUsers:')
        click.echo('----------------------------------------')
        for user in users:
            click.echo(f'ID: {user.id}')
            click.echo(f'Email: {user.email}')
            click.echo(f'Name: {user.first_name} {user.last_name}')
            click.echo(f'Role: {user.role}')
            click.echo(f'Store ID: {user.store_id}')
            click.echo('----------------------------------------')

@cli.command()
def list_stores():
    """List all stores"""
    with app.app_context():
        stores = Store.query.all()
        click.echo('\nStores:')
        click.echo('----------------------------------------')
        for store in stores:
            click.echo(f'ID: {store.id}')
            click.echo(f'Name: {store.name}')
            click.echo(f'Address: {store.address}')
            click.echo(f'Phone: {store.phone}')
            click.echo(f'Users Count: {len(store.users)}')
            click.echo(f'Products Count: {len(store.products)}')
            click.echo('----------------------------------------')

@cli.command()
def list_products():
    """List all products"""
    with app.app_context():
        products = Product.query.all()
        click.echo('\nProducts:')
        click.echo('----------------------------------------')
        for product in products:
            click.echo(f'ID: {product.id}')
            click.echo(f'Name: {product.name}')
            click.echo(f'SKU: {product.sku}')
            click.echo(f'Quantity: {product.quantity}')
            click.echo(f'Min Threshold: {product.min_threshold}')
            click.echo(f'Price: {product.price:.2f} PLN')
            click.echo(f'Store ID: {product.store_id}')
            click.echo(f'Supplier ID: {product.supplier_id}')
            click.echo('----------------------------------------')

@cli.command()
def list_suppliers():
    """List all suppliers"""
    with app.app_context():
        suppliers = Supplier.query.all()
        click.echo('\nSuppliers:')
        click.echo('----------------------------------------')
        for supplier in suppliers:
            click.echo(f'ID: {supplier.id}')
            click.echo(f'Name: {supplier.name}')
            click.echo(f'Email: {supplier.email}')
            click.echo(f'Phone: {supplier.phone}')
            click.echo(f'Address: {supplier.address}')
            click.echo(f'Store ID: {supplier.store_id}')
            click.echo(f'Products Count: {len(supplier.products)}')
            click.echo('----------------------------------------')

@cli.command()
def list_inventory_requests():
    """List all inventory requests"""
    with app.app_context():
        requests = InventoryRequest.query.all()
        click.echo('\nInventory Requests:')
        click.echo('----------------------------------------')
        for req in requests:
            click.echo(f'ID: {req.id}')
            click.echo(f'Product ID: {req.product_id}')
            click.echo(f'User ID: {req.user_id}')
            click.echo(f'Quantity: {req.quantity}')
            click.echo(f'Status: {req.status}')
            click.echo(f'Notes: {req.notes}')
            click.echo(f'Created: {req.created_at}')
            click.echo('----------------------------------------')

@cli.command()
@click.option('--email', prompt=True, help='User email')
@click.option('--password', prompt=True, hide_input=True, help='User password')
@click.option('--first-name', prompt=True, help='User first name')
@click.option('--last-name', prompt=True, help='User last name')
@click.option('--role', default='user', help='User role (admin/user)')
def create_user(email, password, first_name, last_name, role):
    """Create a new user"""
    with app.app_context():
        if User.query.filter_by(email=email).first():
            click.echo('User with this email already exists!')
            return
        
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        user.password = generate_password_hash(password)
        db.session.add(user)
        db.session.commit()
        click.echo('User created successfully!')

@cli.command()
def reset_db():
    """Reset the database (WARNING: This will delete all data!)"""
    if click.confirm('Are you sure you want to reset the database? This will delete all data!'):
        with app.app_context():
            db.drop_all()
            db.create_all()
            click.echo('Database reset successfully!')

@cli.command()
@click.option('--user-id', type=int, help='Show login history for specific user ID')
def login_history(user_id):
    """Show user login history"""
    with app.app_context():
        query = UserLogin.query
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        logins = query.order_by(UserLogin.login_at.desc()).all()
        
        click.echo('\nLogin History:')
        click.echo('----------------------------------------')
        for login in logins:
            user = User.query.get(login.user_id)
            click.echo(f'User: {user.email} ({user.first_name} {user.last_name})')
            click.echo(f'Login Time: {login.login_at}')
            click.echo(f'IP Address: {login.ip_address}')
            click.echo(f'User Agent: {login.user_agent}')
            click.echo('----------------------------------------')

@cli.command()
def show_users():
    """Show detailed user information including last login"""
    with app.app_context():
        users = User.query.all()
        click.echo('\nDetailed User Information:')
        click.echo('----------------------------------------')
        for user in users:
            click.echo(f'ID: {user.id}')
            click.echo(f'Email: {user.email}')
            click.echo(f'Name: {user.first_name} {user.last_name}')
            click.echo(f'Role: {user.role}')
            click.echo(f'Store ID: {user.store_id}')
            click.echo(f'Created: {user.created_at}')
            click.echo(f'Last Login: {user.last_login}')
            click.echo(f'Active: {user.is_active}')
            click.echo(f'Login Count: {user.login_history.count()}')
            click.echo('----------------------------------------')

if __name__ == '__main__':
    cli() 