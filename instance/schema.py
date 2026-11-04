import sqlite3
from pathlib import Path

DB_FILE = Path("plateletweb_central.db")
OUT_FILE = Path("sqlite_schema_summary.txt")

with sqlite3.connect(DB_FILE) as conn, OUT_FILE.open("w", encoding="utf-8") as out:
    cursor = conn.cursor()

    # Get tables and views
    cursor.execute("""
        SELECT type, name, sql
        FROM sqlite_schema
        WHERE type IN ('table', 'view')
          AND name NOT LIKE 'sqlite_%'
        ORDER BY type, name;
    """)

    objects = cursor.fetchall()

    for obj_type, name, create_sql in objects:
        out.write(f"\n\n{obj_type.upper()}: {name}\n")
        out.write("=" * (len(obj_type) + len(name) + 2) + "\n")

        out.write("\nCREATE statement:\n")
        out.write((create_sql or "No CREATE statement found.") + "\n")

        if obj_type == "table":
            out.write("\nColumns:\n")

            cursor.execute(f'PRAGMA table_info("{name}")')
            columns = cursor.fetchall()

            for col in columns:
                cid, col_name, col_type, not_null, default_value, primary_key = col
                out.write(
                    f"  {col_name} | {col_type} | "
                    f"nullable={not not_null} | "
                    f"default={default_value} | "
                    f"primary_key={bool(primary_key)}\n"
                )

print(f"Done. Schema saved to: {OUT_FILE}")