import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, inspect, text
import os
import time

# --- DB Config ---
db_config = {
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'test'),
    'host': os.getenv('DB_HOST', 'db'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'domains_db')
}

engine = create_engine(
    f"postgresql://{db_config['user']}:{db_config['password']}@"
    f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
)

# --- Constants ---
table_name = "domains"
default_csv_path = "/db/Final_updated_domains.csv"

st.set_page_config(page_title="Upload CSV")

st.title("Upload CSV and Load into Database")

# --- Ensure DB ready and pre-fill if empty ---
try:
    with engine.connect() as conn:
        inspector = inspect(engine)
        if table_name in inspector.get_table_names():
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            row_count = result.scalar()
            if row_count > 0:
                st.info(f"Database already contains {row_count} rows in table '{table_name}'.")
            else:
                # Load from fallback CSV if exists
                if os.path.exists(default_csv_path):
                    st.warning("Database is empty. Auto-loading default CSV...")
                    df_default = pd.read_csv(default_csv_path)
                    df_default.to_sql(table_name, engine, if_exists="replace", index=False)
                    st.success(f"Loaded {len(df_default)} rows from default CSV into database.")
                else:
                    st.warning("Database is empty and no default CSV found.")
        else:
            # Table doesn't exist — load fallback if available
            if os.path.exists(default_csv_path):
                st.warning("Table does not exist. Auto-loading default CSV...")
                df_default = pd.read_csv(default_csv_path)
                df_default.to_sql(table_name, engine, if_exists="replace", index=False)
                st.success(f"Loaded {len(df_default)} rows from default CSV into database.")
            else:
                st.warning("Table does not exist and no default CSV found.")
except Exception as e:
    st.error(f"Error checking database state: {e}")

# --- File uploader UI ---
uploaded_file = st.file_uploader("Choose a CSV file to upload and load into database", type="csv")

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        st.write(f"Preview of uploaded file ({len(df)} rows):")
        st.dataframe(df.head(20))

        if st.button("Load into Database"):
            # Save a copy of the uploaded file to /db
            save_path = "/db/uploaded_file.csv"
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"Uploaded file saved to {save_path}")

            # Load into DB
            df.to_sql(table_name, engine, if_exists="replace", index=False)
            st.success(f"Successfully loaded {len(df)} rows into the database!")

            st.session_state.upload_complete = True

    except Exception as e:
        st.error(f"Error reading or uploading CSV: {e}")