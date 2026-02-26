import os

import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def init_database():
    # Database connection parameters
    db_params = {
        "host": os.getenv("POSTGRES_HOST"),
        "port": 5432,
        "database": os.getenv("POSTGRES_DB"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
    }

    # SQL Schema definition
    commands = (
        """
        CREATE TABLE IF NOT EXISTS itks (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS itk_phases (
            id SERIAL PRIMARY KEY,
            itk_id INT REFERENCES itks(id) ON DELETE CASCADE,
            name VARCHAR(50) NOT NULL,
            order_index INT NOT NULL,
            duration_days INT DEFAULT 0,
            target_settings JSONB NOT NULL,
            UNIQUE(itk_id, order_index)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS devices (
            id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(100),
            last_seen TIMESTAMP,
            current_itk_id INT REFERENCES itks(id),
            current_phase_id INT REFERENCES itk_phases(id),
            mode VARCHAR(20) DEFAULT 'MANUAL' -- 'MANUAL' or 'AUTO'
        )
        """,
    )

    conn = None
    try:
        print("Connecting to PostgreSQL...")
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()

        # Execute each command
        for command in commands:
            cur.execute(command)

        cur.close()
        conn.commit()
        print("Database schema initialized successfully.")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error while initializing database: {error}")
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    init_database()
