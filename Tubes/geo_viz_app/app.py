# app.py
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
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
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_secret_key_here')
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
        return check_password_hash(self.password_hash, password)
    
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
    return User.query.get(int(user_id))

# Initial data import function
def import_initial_data():
    # Check if data already exists
    if Location.query.count() > 0:
        print("Database already contains data. Skipping initial import.")
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
        },
        {
            'nama_sekolah': 'SMA Negeri 2',
            'npsn': '23456789',
            'bp': 'SMP',
            'status': 'Swasta',
            'latitude': -6.1751,
            'longitude': 106.8650
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
        print("Initial data imported successfully.")
    except Exception as e:
        db.session.rollback()
        print(f"Error importing initial data: {str(e)}")

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
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        
        flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return render_template('register.html')
        
        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        import_initial_data()  # Import initial data
    app.run(debug=True)