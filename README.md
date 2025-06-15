# Smart Shelf - Inventory Management System

A Flask-based inventory management system for small businesses and restaurants.

## Features

- User authentication (login/signup)
- Store setup and configuration
- Dashboard with key metrics
- Inventory management
- Product management
- Low stock alerts
- Supplier communication

## Setup Instructions

1. Clone the repository:
```bash
git clone <repository-url>
cd smart-shelf
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the root directory with:
```
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your-secret-key
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

5. Initialize the database:
```bash
flask shell
>>> from app import db
>>> db.create_all()
>>> exit()
```

6. Run the application:
```bash
flask run
```

The application will be available at `http://localhost:5000`

## Tech Stack

- Backend: Python (Flask)
- Database: SQLite
- Frontend: HTML, Tailwind CSS
- Authentication: Flask-Login
- Email: SMTP (via smtplib)

## Project Structure

```
smartshelf/
├── app.py                 # Main Flask application
├── models.py             # Database models
├── templates/           # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── signup.html
│   ├── setup.html
│   ├── dashboard.html
│   ├── inventory.html
│   └── add_product.html
└── static/             # Static files
    └── style.css
``` 