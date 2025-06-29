import mysql.connector
from mysql.connector import Error
import os
import csv
import random
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
            
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"Database '{DB_NAME}' created successfully.")
            
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
                updated_by INT,
                FOREIGN KEY (created_by) REFERENCES user(id) ON DELETE SET NULL,
                FOREIGN KEY (updated_by) REFERENCES user(id) ON DELETE SET NULL
            )
            """)
            print("Location table created successfully.")
            
            # Tambahkan constraint UNIQUE ke npsn jika belum ada
            try:
                cursor.execute("ALTER TABLE location ADD UNIQUE (npsn)")
                print("Unique constraint added to npsn column.")
            except Error as e:
                if "Duplicate" in str(e) or "already exists" in str(e):
                    print("Unique constraint on npsn already exists.")
                else:
                    raise e

            # Create saved_schools table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_schools (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                location_id INT,
                npsn VARCHAR(20),
                saved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
                FOREIGN KEY (location_id) REFERENCES location(id) ON DELETE CASCADE,
                UNIQUE KEY unique_user_location (user_id, location_id)
            )
            """)
            print("Saved_schools table created successfully.")

            # Generate a hashed password
            hashed_password = generate_password_hash('admin123')
            
            # Check if admin user exists
            cursor.execute("SELECT * FROM user WHERE username = 'admin'")
            if not cursor.fetchone():
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

def add_column_if_not_exists(cursor, table_name, column_name, column_definition):
    cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE '{column_name}'")
    result = cursor.fetchone()
    if not result:
        print(f"Kolom '{column_name}' tidak ditemukan. Menambahkan kolom...")
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
        print(f"Kolom '{column_name}' berhasil ditambahkan.")
    else:
        print(f"Kolom '{column_name}' sudah ada.")

def import_csv_data(csv_file_path, admin_id=1):
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

            # Pastikan kolom tambahan ada
            add_column_if_not_exists(cursor, 'location', 'akreditasi', 'VARCHAR(10)')
            add_column_if_not_exists(cursor, 'location', 'telepon', 'VARCHAR(15)')
            add_column_if_not_exists(cursor, 'location', 'biaya_masuk', 'VARCHAR(200)')
            add_column_if_not_exists(cursor, 'location', 'SPP', 'VARCHAR(200)')
            add_column_if_not_exists(cursor, 'location', 'email', 'VARCHAR(200)')
            add_column_if_not_exists(cursor, 'location', 'fasilitas', 'VARCHAR(200)')
            add_column_if_not_exists(cursor, 'location', 'updated_by', 'INT')

            updated_count = 0
            inserted_count = 0

            with open(csv_file_path, 'r', encoding='utf-8') as file:
                csv_reader = csv.reader(file)
                header = next(csv_reader)  # skip header

                for row in csv_reader:
                    if len(row) < 12:
                        print(f"Skipping incomplete row: {row}")
                        continue

                    nama_sekolah = row[0].strip()
                    npsn = row[1].strip()
                    bp = row[2].strip()
                    status = row[3].strip()
                    latitude = float(row[4]) if row[4] else None
                    longitude = float(row[5]) if row[5] else None
                    akreditasi = row[6].strip()
                    biaya_masuk = row[7].strip()
                    SPP = row[8].strip()
                    telepon = row[9].strip()
                    email = row[10].strip()
                    fasilitas = row[11].strip()

                    if not npsn:
                        print(f"Skipping row with empty NPSN: {nama_sekolah}")
                        continue

                    # Insert or update in one query
                    cursor.execute("""
                        INSERT INTO location (
                            nama_sekolah, npsn, bp, status, latitude, longitude,
                            akreditasi, biaya_masuk, SPP, telepon, email, fasilitas, created_by, updated_by
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            nama_sekolah = VALUES(nama_sekolah),
                            bp = VALUES(bp),
                            status = VALUES(status),
                            latitude = VALUES(latitude),
                            longitude = VALUES(longitude),
                            akreditasi = VALUES(akreditasi),
                            biaya_masuk = VALUES(biaya_masuk),
                            SPP = VALUES(SPP),
                            telepon = VALUES(telepon),
                            email = VALUES(email),
                            fasilitas = VALUES(fasilitas),
                            updated_by = VALUES(updated_by)
                    """, (
                        nama_sekolah, npsn, bp, status, latitude, longitude,
                        akreditasi, biaya_masuk, SPP, telepon, email, fasilitas, admin_id, admin_id
                    ))

                    if cursor.rowcount == 1:
                        inserted_count += 1
                    elif cursor.rowcount == 2:
                        updated_count += 1

                connection.commit()
                print(f"Import selesai: {inserted_count} data baru, {updated_count} data diperbarui.")

    except Error as e:
        print(f"Error importing CSV data: {e}")
    except FileNotFoundError:
        print(f"CSV file not found: {csv_file_path}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed.")

def create_data_pendaftar_table():
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )

        if connection.is_connected():
            cursor = connection.cursor()

            # Buat tabel jika belum ada
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_pendaftar (
                id INT AUTO_INCREMENT PRIMARY KEY,
                location_id INT,
                tahun INT,
                pendaftar INT,
                FOREIGN KEY (location_id) REFERENCES location(id) ON DELETE CASCADE
            )
            """)
            print("Tabel 'data_pendaftar' berhasil dibuat atau sudah ada.")

            # Ambil semua id dari tabel location
            cursor.execute("SELECT id FROM location")
            location_ids = [row[0] for row in cursor.fetchall()]

            print(f"Menambahkan data acak untuk {len(location_ids)} lokasi...")

            # Tahun dan nilai acak
            # for tahun in range(2022, 2026):  # 2022 - 2025
            #    for location_id in location_ids:
            #        pendaftar = random.randint(120, 240)
            #        cursor.execute("""
            #           INSERT INTO data_pendaftar (location_id, tahun, pendaftar)
            #            VALUES (%s, %s, %s)
            #        """, (location_id, tahun, pendaftar))

            #connection.commit()
            #print(f"Berhasil menambahkan data acak tahun 2022-2025 untuk {len(location_ids)} lokasi.")

    except Error as e:
        print(f"Error saat membuat atau mengisi tabel data_pendaftar: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed.")
            
if __name__ == "__main__":
    create_database()

    csv_file_path = os.getenv('CSV_FILE_PATH', 'locations.csv')
    if os.path.exists(csv_file_path):
        print(f"Importing location data from {csv_file_path}")
        import_csv_data(csv_file_path)
    else:
        print(f"CSV file not found at {csv_file_path}.")
        
    create_data_pendaftar_table()
