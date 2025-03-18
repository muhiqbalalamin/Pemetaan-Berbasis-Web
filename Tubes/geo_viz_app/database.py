import mysql.connector
from mysql.connector import Error
import os
import csv
import requests
from dotenv import load_dotenv

# Load environment variables (create a .env file with your credentials)
load_dotenv()

# Database Configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'geospatial_db')

def download_csv_from_github(url, file_name):
    response = requests.get(url)
    if response.status_code == 200:
        with open(file_name, 'wb') as file:
            file.write(response.content)
        print(f"CSV file downloaded successfully: {file_name}")
    else:
        print(f"Failed to download CSV file. Status code: {response.status_code}")
        return None
    return file_name

def create_database():
    connection = None
    try:
        # Connect to MySQL server
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
                FOREIGN KEY (created_by) REFERENCES user(id)
            )
            """)
            print("Location table created successfully.")
            
            # Insert admin user
            cursor.execute("""
            INSERT IGNORE INTO user (username, email, is_admin) 
            VALUES ('admin', 'admin@example.com', TRUE)
            """)
            
            # Download CSV file from GitHub
            csv_url = "https://github.com/muhiqbalalamin/Pemetaan-Berbasis-Web/blob/2f70866124a299afed5b465fd760a68f4a6c34f5/Data.csv"  # Ganti dengan URL CSV GitHub
            csv_file = "Data.csv"  # Nama file CSV yang disimpan di lokal
            downloaded_file = download_csv_from_github(csv_url, csv_file)

            if downloaded_file:
                # Insert data from CSV
                with open(downloaded_file, newline='', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    next(reader)  # Skip header row jika ada
                    
                    data_to_insert = []
                    for row in reader:
                        # Pastikan jumlah kolom sesuai (6 kolom)
                        if len(row) == 6:
                            try:
                                # Split latitude and longitude which are in the same column
                                lat_long = row[4].split(',')  # Memisahkan kolom latitude,longitude
                                
                                # Pastikan ada dua elemen setelah pemisahan
                                if len(lat_long) == 2:
                                    latitude = float(lat_long[0].strip())  # Mengambil latitude
                                    longitude = float(lat_long[1].strip())  # Mengambil longitude

                                    # Menambahkan data ke dalam list
                                    data_to_insert.append((
                                        row[0],    # nama_sekolah
                                        row[1],    # npsn
                                        row[2],    # bp
                                        row[3],    # status
                                        latitude,  # latitude
                                        longitude  # longitude
                                    ))
                                else:
                                    print(f"Skipping invalid row (latitude,longitude not properly formatted): {row}")
                            except ValueError:
                                print(f"Skipping invalid row (non-numeric value): {row}")
                        else:
                            print(f"Skipping invalid row (incorrect number of columns): {row}")

                    # Masukkan data ke dalam tabel location
                    cursor.executemany("""
                    INSERT IGNORE INTO location (nama_sekolah, npsn, bp, status, latitude, longitude) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """, data_to_insert)
                
                connection.commit()
                print(f"Data from {downloaded_file} inserted successfully.")
                
                # Show the data
                cursor.execute("SELECT * FROM location LIMIT 5")
                records = cursor.fetchall()
                print("\nSample school data:")
                for record in records:
                    print(record)

    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed.")

if __name__ == "__main__":
    create_database()
