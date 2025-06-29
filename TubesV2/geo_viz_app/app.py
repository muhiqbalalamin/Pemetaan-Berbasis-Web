import mysql.connector
from mysql.connector import Error
import pymysql
from dotenv import load_dotenv
from math import radians, sin, cos, sqrt, atan2
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, Blueprint
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pandas as pd
import os
from datetime import datetime
import csv
from sqlalchemy import func
import random
from collections import defaultdict

# Load environment variables
load_dotenv()

# Database Configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'geospatial_db')

# Initialize Flask app
app = Flask(__name__,
            static_folder='app/static')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')  # Added default secret key
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Print connection information for debugging
print(f"Connecting to database: {DB_HOST}/{DB_NAME} with user {DB_USER}")

# Add this to your app configuration
CATEGORY_RADIUS = {
    'SD': 1.0,  # Jarak maks untuk SD dalam Km
    'SMP': 2.0,  # Jarak maks untuk SMP dalam Km
    'SMA': 3.0,  # Jarak maks untuk SMA dalam Km
    'SMK': 3.0,  # Jarak maks untuk SMK dalam Km
}

# Default radius if category not found
DEFAULT_RADIUS = 2.0 #radius kalau ga ada sekolah yang terdeteksi

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
    id          = db.Column(db.Integer, primary_key=True)
    nama_sekolah= db.Column(db.String(100), nullable=False)
    npsn        = db.Column(db.String(20), unique=True)
    bp          = db.Column(db.String(100))
    status      = db.Column(db.String(50))
    latitude    = db.Column(db.Float)
    longitude   = db.Column(db.Float)
    akreditasi  = db.Column(db.String(10))
    biaya_masuk = db.Column(db.String(200))
    SPP         = db.Column(db.String(200))        # pastikan atributnya juga SPP (kebetulan huruf besar)
    telepon     = db.Column(db.String(15))
    email       = db.Column(db.String(200))
    fasilitas   = db.Column(db.String(200))
    created_by  = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_by  = db.Column(db.Integer, db.ForeignKey('user.id'))

    pendaftar_records = db.relationship('Pendaftar', back_populates='location', lazy=True, cascade='all, delete-orphan')
    
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
            'longitude': self.longitude,
            'akreditasi' : self.akreditasi,
            'biaya_masuk' : self.biaya_masuk,
            'SPP' : self.SPP,
            'telepon' : self.telepon,
            'email' : self.email,
            'fasilitas' : self.fasilitas
        }

class Pendaftar(db.Model):
    __tablename__ = 'data_pendaftar'
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    tahun = db.Column(db.Integer, nullable=False)
    pendaftar = db.Column(db.Integer, nullable=False)

    location = db.relationship('Location', back_populates='pendaftar_records')

    def __repr__(self):
        return f'<Pendaftar location_id={self.location_id} tahun={self.tahun} pendaftar={self.pendaftar}>'

    def to_dict(self):
        return {
            'id': self.id,
            'location_id': self.location_id,
            'tahun': self.tahun,
            'pendaftar': self.pendaftar
        }

class SavedSchool(db.Model):
    __tablename__ = 'saved_schools'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    npsn = db.Column(db.String(20), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Define unique constraint to prevent duplicate saves
    __table_args__ = (db.UniqueConstraint('user_id', 'location_id', name='unique_user_location'),)
    
    # Relationships
    user = db.relationship('User', backref='saved_schools')
    location = db.relationship('Location', backref='saved_by_users')
    
    def __repr__(self):
        return f'<SavedSchool user_id={self.user_id} location_id={self.location_id}>'

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
from sqlalchemy.exc import IntegrityError

def import_csv_to_db(filepath, user_id=None):
    try:
        # Baca semua kolom sebagai string, isi NaN jadi ''
        df = pd.read_csv(filepath, dtype=str).fillna('')
        print("Columns:", df.columns.tolist())
        print("First row:", df.iloc[0].to_dict())

        
        # Kolom minimal wajib ada
        required = ['nama_sekolah', 'latitude', 'longitude', 'npsn']
        if not all(col in df.columns for col in required):
            return False, "CSV harus punya kolom: " + ", ".join(required)
        
        inserted = 0
        updated = 0

        for _, row in df.iterrows():
            npsn         = row['npsn'].strip()
            nama         = row['nama_sekolah'].strip()
            bp           = row.get('bp', '').strip()
            status       = row.get('status', '').strip()
            latitude     = float(row['latitude']) if row['latitude'] else None
            longitude    = float(row['longitude']) if row['longitude'] else None
            akreditasi   = row.get('akreditasi', '').strip()
            biaya_masuk  = row.get('biaya_masuk', '').strip()
            spp          = row.get('SPP', '').strip()
            telepon      = row.get('telepon', '').strip()
            email        = row.get('email', '').strip()
            fasilitas    = row.get('fasilitas', '').strip()

            # Cari existing berdasarkan npsn (jika npsn kosong, anggap record baru)
            npsn = row['npsn'].strip()
            # Pastikan tipe npsn untuk query sesuai dengan model
            print(f"– Raw NPSN string: ‘{repr(npsn)}’")
            existing = None
            if npsn:
                # Jika di model kamu npsn bertipe Integer, ubah ke int:
                # npsn_query = int(npsn) if npsn.isdigit() else npsn
                # existing = Location.query.filter_by(npsn=npsn_query).first()

                # Jika di model npsn bertipe String, pakai langsung:
                existing = Location.query.filter_by(npsn=npsn).first()

                print(f"Lookup NPSN={npsn} →", "Found!" if existing else "Not found")

            if existing:
                # Update existing
                existing.nama_sekolah = nama
                existing.bp           = bp
                existing.status       = status
                existing.latitude     = latitude
                existing.longitude    = longitude
                existing.akreditasi   = akreditasi
                existing.biaya_masuk  = biaya_masuk
                existing.SPP          = spp
                existing.telepon      = telepon
                existing.email        = email
                existing.fasilitas    = fasilitas
                existing.updated_by   = user_id
                updated += 1
            else:
                # Insert new
                new_loc = Location(
                    nama_sekolah = nama,
                    npsn         = npsn,
                    bp           = bp,
                    status       = status,
                    latitude     = latitude,
                    longitude    = longitude,
                    akreditasi   = akreditasi,
                    biaya_masuk  = biaya_masuk,
                    SPP          = spp,
                    telepon      = telepon,
                    email        = email,
                    fasilitas    = fasilitas,
                    created_by   = user_id
                )
                db.session.add(new_loc)
                inserted += 1

        db.session.commit()
        return True, f"Import selesai: {inserted} data baru, {updated} data diperbarui."
    
    except IntegrityError as e:
        db.session.rollback()
        return False, f"Integrity Error: {str(e)}"
    
    except Exception as e:
        db.session.rollback()
        return False, f"Error importing CSV: {str(e)}"

def import_pendaftar_csv_to_db(filepath, user_id=None):
    """Import pendaftar (registration) data from CSV to database"""
    try:
        # Read CSV file
        df = pd.read_csv(filepath, dtype=str)
        df = df.dropna(how='all')  # Hapus baris kosong total
        df = df.fillna('')
        print("Pendaftar CSV Columns:", df.columns.tolist())
        print("First row:", df.iloc[0].to_dict())

        # Required columns for pendaftar data
        required = ['npsn', 'tahun', 'pendaftar']
        if not all(col in df.columns for col in required):
            return False, "CSV harus memiliki kolom: " + ", ".join(required)
        
        inserted = 0
        updated = 0
        errors = []

        for index, row in df.iterrows():
            try:
                npsn = row['npsn'].strip()
                tahun = int(row['tahun']) if row['tahun'] else None
                pendaftar_count = int(row['pendaftar']) if row['pendaftar'] else None
                
                if not npsn or not tahun or pendaftar_count is None:
                    errors.append(f"Row {index + 2}: Missing required data")
                    continue
                
                # Find the location by NPSN
                location = Location.query.filter_by(npsn=npsn).first()
                if not location:
                    errors.append(f"Row {index + 2}: School with NPSN {npsn} not found")
                    continue
                
                # Check if record already exists
                existing = Pendaftar.query.filter_by(
                    location_id=location.id, 
                    tahun=tahun
                ).first()
                
                if existing:
                    # Update existing record
                    existing.pendaftar = pendaftar_count
                    updated += 1
                else:
                    # Insert new record
                    new_pendaftar = Pendaftar(
                        location_id=location.id,
                        tahun=tahun,
                        pendaftar=pendaftar_count
                    )
                    db.session.add(new_pendaftar)
                    inserted += 1
                    
            except ValueError as ve:
                errors.append(f"Row {index + 2}: Invalid data format - {str(ve)}")
                continue
            except Exception as e:
                errors.append(f"Row {index + 2}: Error - {str(e)}")
                continue

        db.session.commit()
        
        message = f"Import selesai: {inserted} data baru, {updated} data diperbarui."
        if errors:
            message += f" {len(errors)} error(s): " + "; ".join(errors[:5])  # Show first 5 errors
            if len(errors) > 5:
                message += f" ... dan {len(errors) - 5} error lainnya."
        
        return True, message
    
    except Exception as e:
        db.session.rollback()
        return False, f"Error importing pendaftar CSV: {str(e)}"


@app.route('/upload-pendaftar', methods=['POST'])
@login_required
def upload_pendaftar():
    """Handle pendaftar data upload"""
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('upload_csv'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('upload_csv'))
    
    if file and file.filename.endswith('.csv'):
        filepath = os.path.join('uploads', f"pendaftar_{file.filename}")
        os.makedirs('uploads', exist_ok=True)
        file.save(filepath)
        
        success, message = import_pendaftar_csv_to_db(filepath, current_user.id)
        flash(message)
        
        # Remove the file after processing
        os.remove(filepath)
        
        if success:
            return redirect(url_for('statistics'))  # Redirect to statistics page to see the data
        else:
            return redirect(url_for('upload_csv'))
    else:
        flash('File must be a CSV')
        return redirect(url_for('upload_csv'))

# Routes
@app.route('/')
def index():
    return render_template('index.html', background_image=os.getenv('DASHBOARD_BG'))

@app.route('/map')
def map_view():
    return render_template('map.html')

@app.route('/api/locations')
def get_locations():
    # Get filter parameters
    status = request.args.get('status', '')
    bp = request.args.get('bp', '')
    search = request.args.get('search', '')
    saved_only = request.args.get('saved_only')
    
    # Build query
    query = Location.query
    
    if saved_only and current_user.is_authenticated:
        query = query.join(SavedSchool, Location.id == SavedSchool.location_id)\
                    .filter(SavedSchool.user_id == current_user.id)
    
    if status:
        query = query.filter(Location.status == status)
    
    if bp:
        query = query.filter(Location.bp == bp)
    
    if search:
        query = query.filter(Location.nama_sekolah.contains(search) | 
                             Location.npsn.contains(search))
    
    locations = query.all()
    
    # Add saved status to each location if user is authenticated
    location_data = []
    for loc in locations:
        loc_dict = loc.to_dict()
        if current_user.is_authenticated:
            is_saved = SavedSchool.query.filter_by(
                user_id=current_user.id, 
                location_id=loc.id
            ).first() is not None
            loc_dict['is_saved'] = is_saved
        else:
            loc_dict['is_saved'] = False
        location_data.append(loc_dict)
    
    return jsonify(location_data)

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

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        identifier = request.form.get('identifier')
        
        # Check if identifier is a username or email
        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
        
        if user:
            # Store user ID in session for the reset password page
            session['reset_user_id'] = user.id
            return redirect(url_for('reset_password'))
        else:
            flash('No user found with that username or email')
            return redirect(url_for('forgot_password'))
    
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    # Check if user ID is in session
    user_id = session.get('reset_user_id')
    if not user_id:
        flash('Please provide your username or email first')
        return redirect(url_for('forgot_password'))
    
    user = User.query.get(user_id)
    if not user:
        flash('User not found')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match. Please try again.')
            return redirect(url_for('reset_password'))
        
        # Update user's password - use scrypt as per your database
        user.set_password(password)
        db.session.commit()
        
        # Clear the session variable
        session.pop('reset_user_id', None)
        
        flash('Your password has been updated! You can now log in with your new password.')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html')

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
    
    return render_template('upload.html', background_image=os.getenv('DEFAULT_BG'))

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
                                  radius_config=CATEGORY_RADIUS, background_image=os.getenv('DEFAULT_BG'))
        
        except Exception as e:
            flash(f'Error: {str(e)}')
            return redirect(url_for('nearby_schools'))
    
    return render_template('nearby_schools_form.html', background_image=os.getenv('DEFAULT_BG'))

from sqlalchemy import func, desc
from sqlalchemy.sql import over
from sqlalchemy.orm import aliased

@app.route('/statistics')
def statistics():
    total_schools = Location.query.count()
    negeri_schools = Location.query.filter_by(status='Negeri').count()
    swasta_schools = Location.query.filter_by(status='Swasta').count()

    # Breakdown status dan jenis
    school_types = db.session.query(
        Location.bp,
        Location.status,
        func.count(Location.id).label('count')
    ).group_by(Location.bp, Location.status).all()

    # Distribusi berdasarkan bp
    school_bp_distribution = db.session.query(
        Location.bp,
        func.count(Location.id)
    ).group_by(Location.bp).all()

    # Subquery: Ranking berdasarkan bp dan tahun (per tingkat dan tahun)
    ranked_subquery = db.session.query(
        Location.id.label('location_id'),
        Location.nama_sekolah,
        Location.bp,
        Location.status,
        Pendaftar.tahun,
        Pendaftar.pendaftar,
        func.row_number().over(
            partition_by=(Location.bp, Pendaftar.tahun),
            order_by=desc(Pendaftar.pendaftar)
        ).label('rank')
    ).join(Pendaftar, Location.id == Pendaftar.location_id).subquery()

    # Ambil hanya yang rank <= 10 per bp dan tahun
    top_schools = db.session.query(ranked_subquery).filter(ranked_subquery.c.rank <= 10).order_by(
        ranked_subquery.c.bp,
        ranked_subquery.c.tahun,
        ranked_subquery.c.pendaftar.desc()
    ).all()

    return render_template(
        'statistics.html',
        total_schools=total_schools,
        negeri_percentage=round(negeri_schools / total_schools * 100, 2),
        swasta_percentage=round(swasta_schools / total_schools * 100, 2),
        school_types=school_types,
        school_bp_distribution=school_bp_distribution,
        top_schools=top_schools,
        background_image=os.getenv('DEFAULT_BG')
    )
    
# Route untuk distribusi pendaftar berdasarkan BP
@app.route('/registration-distribution-by-bp')
def registration_distribution_by_bp():
    tahun = request.args.get('tahun', type=int)  # Get year parameter from query string
    
    try:
        # Base query to join Location and Pendaftar tables
        base_query = db.session.query(
            Location.bp,
            func.sum(Pendaftar.pendaftar).label('total_pendaftar')
        ).join(Pendaftar, Location.id == Pendaftar.location_id)
        
        # Apply year filter if provided
        if tahun:
            base_query = base_query.filter(Pendaftar.tahun == tahun)
        
        # Group by school type and execute query
        bp_totals = base_query.group_by(Location.bp).all()
        
        # For debugging
        print(f"Query results for tahun={tahun}: {bp_totals}")
        
        # Always return a valid data point
        if not bp_totals:
            print("No data found, returning placeholder")
            return jsonify([{
                'name': 'Tidak Ada Data',
                'y': 100,
                'jumlah_pendaftar': 0
            }])
        
        # Calculate total registrations for percentage calculation
        total_all = sum([row.total_pendaftar for row in bp_totals])
        
        if total_all == 0:
            print("Total is zero, returning placeholder")
            return jsonify([{
                'name': 'Tidak Ada Data',
                'y': 100,
                'jumlah_pendaftar': 0
            }])
        
        # Format data for Highcharts
        chart_data = []
        for row in bp_totals:
            if row.bp:  # Make sure bp is not None
                chart_data.append({
                    'name': row.bp,
                    'y': float(round((row.total_pendaftar / total_all) * 100, 2)),
                    'jumlah_pendaftar': int(row.total_pendaftar)
                })
        
        # Make sure we have at least one valid data point
        if not chart_data:
            chart_data.append({
                'name': 'Tidak Ada Data',
                'y': 100.0,
                'jumlah_pendaftar': 0
            })
        
        print(f"Returning chart data: {chart_data}")
        return jsonify(chart_data)  # Return data as JSON
        
    except Exception as e:
        print(f"Error in registration-distribution-by-bp: {e}")
        # Return a valid data point on error
        return jsonify([{
            'name': 'Error',
            'y': 100.0,
            'jumlah_pendaftar': 0
        }])

# Route untuk mengambil daftar tahun yang tersedia
@app.route('/available-years')
def available_years():
    # Ambil daftar tahun yang unik dari tabel Pendaftar, urutkan secara ascending
    years = db.session.query(Pendaftar.tahun).distinct().order_by(Pendaftar.tahun).all()
    
    # Mengembalikan daftar tahun sebagai JSON
    return jsonify([y.tahun for y in years])


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

@app.route('/api/save-school', methods=['POST'])
@login_required
def save_school():
    try:
        data = request.get_json()
        location_id = data.get('location_id')
        npsn = data.get('npsn')
        
        if not location_id or not npsn:
            return jsonify({'success': False, 'message': 'Missing location_id or npsn'}), 400
        
        # Check if already saved
        existing = SavedSchool.query.filter_by(
            user_id=current_user.id, 
            location_id=location_id
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': 'School already saved'}), 409
        
        # Create new saved school record
        saved_school = SavedSchool(
            user_id=current_user.id,
            location_id=location_id,
            npsn=npsn
        )
        
        db.session.add(saved_school)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'School saved successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/unsave-school', methods=['POST'])
@login_required
def unsave_school():
    try:
        data = request.get_json()
        location_id = data.get('location_id')
        
        if not location_id:
            return jsonify({'success': False, 'message': 'Missing location_id'}), 400
        
        # Find and delete the saved school record
        saved_school = SavedSchool.query.filter_by(
            user_id=current_user.id, 
            location_id=location_id
        ).first()
        
        if not saved_school:
            return jsonify({'success': False, 'message': 'School not found in saved list'}), 404
        
        db.session.delete(saved_school)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'School removed from saved'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/check-saved-school/<int:location_id>')
@login_required
def check_saved_school(location_id):
    """Check if a school is saved by the current user"""
    saved = SavedSchool.query.filter_by(
        user_id=current_user.id, 
        location_id=location_id
    ).first()
    
    return jsonify({'is_saved': saved is not None})

@app.route('/api/saved-schools-count')
@login_required
def get_saved_schools_count():
    count = SavedSchool.query.filter_by(user_id=current_user.id).count()
    return jsonify({'count': count})

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