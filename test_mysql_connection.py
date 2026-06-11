"""Test MySQL database connection"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    import pymysql
    
    # Get MySQL configuration from .env
    config = {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD', ''),
        'database': os.getenv('MYSQL_DATABASE', ''),
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor,
        'connect_timeout': 10,
    }
    
    print(f"Connecting to MySQL...")
    print(f"Host: {config['host']}:{config['port']}")
    print(f"User: {config['user']}")
    print(f"Database: {config['database']}")
    print("-" * 50)
    
    # Connect to MySQL
    connection = pymysql.connect(**config)
    
    print("[OK] MySQL connection successful!")
    
    # Test query
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION() as version")
        result = cursor.fetchone()
        print(f"MySQL Version: {result['version']}")
        
        cursor.execute("SHOW DATABASES")
        databases = cursor.fetchall()
        print(f"\nAvailable databases ({len(databases)}):")
        for db in databases:
            print(f"  - {db['Database']}")
    
    connection.close()
    print("\n[OK] Connection test completed successfully!")
    
except ImportError:
    print("[ERROR] pymysql not installed. Run: pip install pymysql")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Connection failed: {e}")
    sys.exit(1)
