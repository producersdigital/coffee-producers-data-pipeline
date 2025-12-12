import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

# Load environment variables from project root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(project_root, '.env'), override=True)

def create_connection():
    """Create a connection to the DigitalOcean MySQL database."""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', 25060)),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            ssl_ca=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config/certificates/ca-certificate.crt'),
            autocommit=True
        )
        
        if connection.is_connected():
            print("Successfully connected to MySQL database")
            return connection
            
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return None

def test_connection():
    """Test the database connection."""
    connection = create_connection()
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print(f"MySQL Server version: {version[0]}")
        cursor.close()
        connection.close()
        print("Connection closed")
    else:
        print("Failed to connect to database")

if __name__ == "__main__":
    test_connection()