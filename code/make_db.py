import pandas as pd
import sqlite3
import os
import argparse
import sys
from sqlalchemy import create_engine

GENE_INFO_PATH = "../tmp/gene_info.txt"
NETWORK_PATH = "../tmp/interactions.txt"

DB_URL = "sqlite:///plateletweb_central.db"   
GENE_TABLE = "genes"           
INTERACTION_TABLE = "interactions"

def main():
    # create sqlalchemy engine
    engine = create_engine(DB_URL, echo=False)

    genes_df = pd.read_csv(GENE_INFO_PATH, sep="\t")
    inter_df = pd.read_csv(NETWORK_PATH, sep="\t")

    #  Write DataFrames to SQL tables
    #    - if_exists='replace' recreates the table each time (schema inferred from df)
    #    - index=False avoids adding the pandas index as a column
    genes_df.to_sql(GENE_TABLE, engine, if_exists="replace", index=False)
    print(f"Written {len(genes_df)} rows to table '{GENE_TABLE}'")

    inter_df.to_sql(INTERACTION_TABLE, engine, if_exists="replace", index=False)
    print(f"Written {len(inter_df)} rows to table '{INTERACTION_TABLE}'")

    # 4. Quick verification: read back a few rows
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
