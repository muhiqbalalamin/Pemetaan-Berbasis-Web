import mysql.connector
from mysql.connector import Error
import os
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

if __name__ == "__main__":
    create_database()