import json
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def sync_itks():
    db_params = {
        "host": os.getenv("POSTGRES_HOST"),
        "port": os.getenv("POSTGRES_PORT", 5432),
        "database": os.getenv("POSTGRES_DB"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
    }

    itk_folder = Path("./itk")
    if not itk_folder.exists():
        print(f"Error: Directory {itk_folder} not found.")
        return

    try:
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()

        for json_file in itk_folder.glob("*.json"):
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
                itk_name = data.get("name")
                phases = data.get("phases", [])

                print(f"🔄 Syncing: {itk_name}...")

                # 1. Upsert ITK
                cur.execute(
                    "INSERT INTO itks (name) VALUES (%s) "
                    "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
                    "RETURNING id",
                    (itk_name,),
                )
                itk_id = cur.fetchone()[0]

                # 2. Upsert Phases (Update if itk_id + order_index exists)
                active_orders = []
                for phase in phases:
                    active_orders.append(phase["order"])
                    cur.execute(
                        """
                        INSERT INTO itk_phases (
                            itk_id, name, order_index, duration_days, target_settings)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (itk_id, order_index) DO UPDATE SET
                            name = EXCLUDED.name,
                            duration_days = EXCLUDED.duration_days,
                            target_settings = EXCLUDED.target_settings
                        """,
                        (
                            itk_id,
                            phase["name"],
                            phase["order"],
                            phase["duration"],
                            json.dumps(phase["settings"]),
                        ),
                    )

        conn.commit()
        print("🚀 ITK Library synchronized successfully.")

    except Exception as error:
        print(f"❌ Sync Error: {error}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    sync_itks()
