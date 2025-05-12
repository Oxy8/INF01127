import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Determine the socket path
socket_path = os.path.join("/home/estevan/Ambientes/tf_engenharia_de_software/pgsocket")

# Construct the connection string
DATABASE_URL = f"postgresql://@/test_db?host=/home/estevan/Ambientes/tf_engenharia_de_software/pgsocket"

def create_and_populate():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Create table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL
        );
    """)

    # Insert data
    cur.execute("INSERT INTO users (name) VALUES ('Alice')")
    cur.execute("INSERT INTO users (name) VALUES ('Bob')")
    cur.execute("INSERT INTO users (name) VALUES ('Charlie')")

    conn.commit()
    cur.close()
    conn.close()
    print("Table populated successfully.")

if __name__ == "__main__":
    create_and_populate()
