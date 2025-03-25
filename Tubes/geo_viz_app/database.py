import mysql.connector
from mysql.connector import Error
import os
import csv
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Load environment variables
load_dotenv()

# Database Configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'geospatial_db')

def create_database():
    connection = None
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # Create database if it doesn't exist
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"Database '{DB_NAME}' created successfully.")
            
            # Switch to the database
            cursor.execute(f"USE {DB_NAME}")
            
            # Create user table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(80) NOT NULL UNIQUE,
                email VARCHAR(120) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_admin BOOLEAN DEFAULT FALSE
            )
            """)
            print("User table created successfully.")
            
            # Create location table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS location (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nama_sekolah VARCHAR(100) NOT NULL,
                npsn VARCHAR(20),
                bp VARCHAR(100),
                status VARCHAR(50),
                latitude FLOAT,
                longitude FLOAT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by INT,
                FOREIGN KEY (created_by) REFERENCES user(id) ON DELETE SET NULL
            )
            """)
            print("Location table created successfully.")
            
            # Generate a hashed password
            hashed_password = generate_password_hash('admin123')
            
            # Check if admin user exists
            cursor.execute("SELECT * FROM user WHERE username = 'admin'")
            if not cursor.fetchone():
                # Insert admin user with hashed password
                cursor.execute("""
                INSERT INTO user (username, email, password_hash, is_admin) 
                VALUES (%s, %s, %s, %s)
                """, ('admin', 'admin@example.com', hashed_password, True))
                
                connection.commit()
                print("Admin user added successfully.")
            else:
                print("Admin user already exists.")

    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed.")

def import_csv_data(csv_file_path, admin_id=1):
    """
    Import location data from a CSV file into the location table
    Expected CSV format: nama_sekolah,npsn,bp,status,latitude,longitude
    """
    connection = None
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # Read CSV file and insert data
            with open(csv_file_path, 'r', encoding='utf-8') as file:
                csv_reader = csv.reader(file)
                next(csv_reader)  # Skip header row if it exists
                
                # Prepare for batch insert
                locations = []
                for row in csv_reader:
                    # Check if row has enough columns
                    if len(row) >= 6:
                        nama_sekolah = row[0]
                        npsn = row[1]
                        bp = row[2]
                        status = row[3]
                        
                        # Handle potential non-numeric values for lat/long
                        try:
                            latitude = float(row[4]) if row[4] else None
                            longitude = float(row[5]) if row[5] else None
                        except ValueError:
                            print(f"Invalid coordinates for {nama_sekolah}, skipping.")
                            continue
                        
                        locations.append((nama_sekolah, npsn, bp, status, latitude, longitude, admin_id))
                    else:
                        print(f"Row doesn't have enough columns: {row}")
                
                # Insert data in batches
                if locations:
                    cursor.executemany("""
                    INSERT INTO location 
                    (nama_sekolah, npsn, bp, status, latitude, longitude, created_by) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, locations)
                    
                    connection.commit()
                    print(f"Successfully imported {cursor.rowcount} locations from CSV.")
                else:
                    print("No valid data found in CSV file.")
    
    except Error as e:
        print(f"Error importing CSV data: {e}")
    except FileNotFoundError:
        print(f"CSV file not found: {csv_file_path}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed.")

if __name__ == "__main__":
    create_database()
    
    # Import CSV data after database setup
    csv_file_path = os.getenv('CSV_FILE_PATH', 'locations.csv')
    if os.path.exists(csv_file_path):
        print(f"Importing location data from {csv_file_path}")
        import_csv_data(csv_file_path)
    else:
        print(f"CSV file not found at {csv_file_path}. Add CSV_FILE_PATH to your .env file or place a 'locations.csv' file in the current directory.")