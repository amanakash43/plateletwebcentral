import pandas as pd
import sqlite3
import os
import argparse
import sys
from sqlalchemy import create_engine

DB_URL = "sqlite:///plateletweb_central.db"   
GENE_TABLE = "genes"           
INTERACTION_TABLE = "interactions"

def main():
    # create sqlalchemy engine
    engine = create_engine(DB_URL, echo=False)
    with engine.connect() as conn:
        print(f"\nPreview of '{GENE_TABLE}':")
        preview_genes = pd.read_sql_query(
            f"SELECT * FROM {GENE_TABLE} LIMIT 5;", conn
        )
        print(preview_genes)

        print(f"\nPreview of '{INTERACTION_TABLE}':")
        preview_inter = pd.read_sql_query(
            f"SELECT * FROM {INTERACTION_TABLE} LIMIT 5;", conn
        )
        print(preview_inter)


if __name__ == "__main__":
    main()
