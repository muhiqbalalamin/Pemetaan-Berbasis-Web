import mysql.connector
from mysql.connector import Error
import pymysql
from dotenv import load_dotenv
from math import radians, sin, cos, sqrt, atan2
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pandas as pd
import os
from datetime import datetime
import csv

# Load environment variables
load_dotenv()

# Database Configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'geospatial_db')

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')  # Added default secret key
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Print connection information for debugging
print(f"Connecting to database: {DB_HOST}/{DB_NAME} with user {DB_USER}")

# Add this to your app configuration
CATEGORY_RADIUS = {
    'SD': 3.0,  # Elementary schools - 3 km radius
    'SMP': 2.0,  # Junior high schools - 2 km radius
    'SMA': 1.0,  # Senior high schools - 1 km radius
    'SMK': 1.0,  # Vocational high schools - 1 km radius
}

# Default radius if category not found
DEFAULT_RADIUS = 2.0

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        result = check_password_hash(self.password_hash, password)
        print(f"Password check for {self.username}: {result}")
        return result
    
    def __repr__(self):
        return f'<User {self.username}>'

class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_sekolah = db.Column(db.String(100), nullable=False)
    npsn = db.Column(db.String(20), nullable=True)
    bp = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    def __repr__(self):
        return f'<Location {self.nama_sekolah}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nama_sekolah': self.nama_sekolah,
            'npsn': self.npsn,
            'bp': self.bp,
            'status': self.status,
            'latitude': self.latitude,
            'longitude': self.longitude
        }

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    print(f"Loading user {user_id}: {'Found' if user else 'Not found'}")
    return user

# Initial data import function
def import_initial_data():
    # Check if data already exists
    if Location.query.count() > 0:
        print("Database already contains location data. Skipping initial import.")
        return
    
    # Sample data based on your table structure
    initial_data = [
        {
            'nama_sekolah': 'SMA Negeri 1',
            'npsn': '12345678',
            'bp': 'SMA',
            'status': 'Negeri',
            'latitude': -6.2088,
            'longitude': 106.8456
        }
    ]
    
    # Add records to database
    try:
        for data in initial_data:
            location = Location(
                nama_sekolah=data['nama_sekolah'],
                npsn=data['npsn'],
                bp=data['bp'],
                status=data['status'],
                latitude=data['latitude'],
                longitude=data['longitude']
            )
            db.session.add(location)
        
        db.session.commit()
        print("Initial location data imported successfully.")
    except Exception as e:
        db.session.rollback()
        print(f"Error importing initial location data: {str(e)}")

# Create a test admin user if none exists
def create_test_user():
    # Check if any users exist
    if User.query.count() > 0:
        print("Users already exist in database. Skipping test user creation.")
        users = User.query.all()
        for user in users:
            print(f"Existing user: {user.username}, {user.email}")
        return
    
    # Create test admin user
    test_user = User(
        username="admin",
        email="admin@example.com",
        is_admin=True
    )
    test_user.set_password("admin123")
    
    try:
        db.session.add(test_user)
        db.session.commit()
        print(f"Test admin user created successfully: admin/admin123")
    except Exception as e:
        db.session.rollback()
        print(f"Error creating test user: {str(e)}")

# CSV Import Function
def import_csv_to_db(filepath, user_id=None):
    try:
        df = pd.read_csv(filepath)
        required_columns = ['nama_sekolah', 'latitude', 'longitude']
            
        # Validate CSV has required columns
        if not all(col in df.columns for col in required_columns):
            return False, "CSV file must contain 'nama_sekolah', 'latitude', and 'longitude' columns"
        
        # Add records to database
        for _, row in df.iterrows():
            location = Location(
                nama_sekolah=row['nama_sekolah'],
                npsn=row.get('npsn', ''),
                bp=row.get('bp', ''),
                status=row.get('status', ''),
                latitude=float(row['latitude']),
                longitude=float(row['longitude']),
                created_by=user_id
            )
            db.session.add(location)
        
        db.session.commit()
        return True, f"Successfully imported {len(df)} locations."
    except Exception as e:
        db.session.rollback()
        return False, f"Error importing CSV: {str(e)}"

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/map')
def map_view():
    return render_template('map.html')

@app.route('/api/locations')
def get_locations():
    # Get filter parameters
    status = request.args.get('status', '')
    bp = request.args.get('bp', '')
    search = request.args.get('search', '')
    
    # Build query
    query = Location.query
    
    if status:
        query = query.filter(Location.status == status)
    
    if bp:
        query = query.filter(Location.bp == bp)
    
    if search:
        query = query.filter(Location.nama_sekolah.contains(search) | 
                             Location.npsn.contains(search))
    
    locations = query.all()
    return jsonify([loc.to_dict() for loc in locations])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        print(f"Login attempt for username: {username}")
        
        user = User.query.filter_by(username=username).first()
        
        if user:
            print(f"User found: ID={user.id}, Email={user.email}")
            if user.check_password(password):
                print(f"Password verified for {username}")
                login_user(user)
                next_page = request.args.get('next')
                print(f"Login successful, redirecting to: {next_page or 'index'}")
                flash(f'Welcome back, {username}!')
                return redirect(next_page or url_for('index'))
            else:
                print(f"Password verification failed for {username}")
        else:
            print(f"No user found with username: {username}")
        
        flash('Invalid username or password')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        admin_code = request.form.get('admin_code')  # Get admin code if provided
        
        print(f"Registration attempt for: {username}, {email}")
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            print(f"Username {username} already exists")
            flash('Username already exists')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            print(f"Email {email} already exists")
            flash('Email already exists')
            return render_template('register.html')
        
        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)
        
        # Check admin code if provided
        admin_code_valid = os.getenv('ADMIN_REGISTRATION_CODE', 'admin_secret_code')
        if admin_code and admin_code == admin_code_valid:
            user.is_admin = True
            print(f"Admin registration for: {username}")
        
        try:
            db.session.add(user)
            db.session.commit()
            print(f"User registered successfully: {username}, Admin: {user.is_admin}")
            print(f"Expected admin code: {admin_code_valid}, Received: {admin_code}")

            
            # Verify user was created
            created_user = User.query.filter_by(username=username).first()
            if created_user:
                print(f"User creation verified: ID={created_user.id}, Email={created_user.email}, Admin={created_user.is_admin}")
            else:
                print("WARNING: User creation verification failed!")
                
            flash('Registration successful. Please log in.')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            print(f"Error during registration: {str(e)}")
            flash('An error occurred during registration')
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    username = current_user.username
    logout_user()
    print(f"User {username} logged out")
    flash('You have been logged out.')
    return redirect(url_for('index'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_csv():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if file and file.filename.endswith('.csv'):
            filepath = os.path.join('uploads', file.filename)
            os.makedirs('uploads', exist_ok=True)
            file.save(filepath)
            
            success, message = import_csv_to_db(filepath, current_user.id)
            flash(message)
            
            # Remove the file after processing
            os.remove(filepath)
            
            if success:
                return redirect(url_for('map_view'))
        else:
            flash('File must be a CSV')
    
    return render_template('upload.html')

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin:
        flash('You do not have permission to access this page')
        return redirect(url_for('index'))
    
    users = User.query.all()
    locations = Location.query.all()
    return render_template('admin.html', users=users, locations=locations)

# Database connection test route
@app.route('/test-db')
def test_db():
    try:
        result = db.session.execute(db.text('SELECT 1')).fetchone()
        if result:
            user_count = User.query.count()
            location_count = Location.query.count()
            return jsonify({
                'status': 'success',
                'message': 'Database connection successful',
                'users': user_count,
                'locations': location_count
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Database connection failed'
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Database error: {str(e)}'
        })

@app.route('/nearby-schools', methods=['GET', 'POST'])
def nearby_schools():
    if request.method == 'POST':
        try:
            user_lat = float(request.form.get('latitude'))
            user_lng = float(request.form.get('longitude'))
            custom_radius = request.form.get('custom_radius') #buat ngeliat sesuai jarak yang dipengen aja
            
            # Get all schools
            all_locations = Location.query.all()
            nearby_schools = []
            
            for location in all_locations:
                # Get the appropriate radius based on school category
                category_radius = CATEGORY_RADIUS.get(location.bp, DEFAULT_RADIUS)
                
                # If custom radius is provided, use it instead
                if custom_radius:
                    effective_radius = float(custom_radius)
                else:
                    effective_radius = category_radius
                
                # Calculate distance
                distance = calculate_distance(user_lat, user_lng, location.latitude, location.longitude)
                
                # Check if school is within radius
                if distance <= effective_radius:
                    # Get basic school info
                    school_info = location.to_dict()
                    
                    # Add distance information
                    school_info['distance'] = round(distance, 2)
                    school_info['within_default_radius'] = distance <= category_radius
                    
                    # Calculate temporary passing grade based on proximity (inverse relationship)
                    # The closer to the school, the higher the passing grade percentage
                    passing_grade = max(0, min(100, (1 - (distance / effective_radius)) * 100))
                    school_info['passing_grade'] = round(passing_grade, 1)  # Round to 1 decimal place
                    
                    nearby_schools.append(school_info)
            
            # Sort schools by distance
            nearby_schools.sort(key=lambda x: x['distance'])
            
            return render_template('nearby_schools.html', 
                                  schools=nearby_schools, 
                                  user_lat=user_lat, 
                                  user_lng=user_lng,
                                  radius_config=CATEGORY_RADIUS)
        
        except Exception as e:
            flash(f'Error: {str(e)}')
            return redirect(url_for('nearby_schools'))
    
    return render_template('nearby_schools_form.html')

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in kilometers using the Haversine formula"""
    # Radius of the Earth in kilometers
    R = 6371.0
    
    # Convert latitude and longitude from degrees to radians
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)
    
    # Differences in coordinates
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    # Haversine formula
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c
    
    return distance

# Main execution block
if __name__ == '__main__':
    with app.app_context():
        try:
            # Check database connection
            result = db.session.execute(db.text('SELECT 1')).fetchone()
            if result:
                print("Database connection successful")
            else:
                print("Database connection test returned no result")
                
            # Create tables if they don't exist
            db.create_all()
            print("Database tables created or confirmed")
            
            # Create test user
            create_test_user()
            
            # Import initial data
            import_initial_data()
            
            # Print tables information
            tables = db.session.execute(db.text('SHOW TABLES')).fetchall()
            print(f"Database tables: {[t[0] for t in tables]}")
            
            users = User.query.all()
            print(f"Users in database: {len(users)}")
            for user in users:
                print(f"  - {user.username} (ID: {user.id}, Admin: {user.is_admin})")
                
            locations = Location.query.all()
            print(f"Locations in database: {len(locations)}")
            
        except Exception as e:
            print(f"ERROR during initialization: {str(e)}")
    
    # Run the Flask application
    app.run(debug=True)