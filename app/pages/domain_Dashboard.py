import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px
import os

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

st.set_page_config(layout="wide", page_title="Domain Statistics Dashboard")

# --- Styling ---
st.markdown("""
    <style>
        /* General theme */
        .appview-container, .main, .block-container {
            background-color: #1E1E2F !important;
            color: white;
        }

        /* Style for main buttons */
        .stButton>button {
            background-color: #8C54FF;
            color: white;
            border-radius: 8px;
            padding: 0.5em 1em;
            border: none;
        }

        .stButton>button:hover {
            background-color: #A875FF;
            color: white;
        }

        .stDataFrame div {
            color: white !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("Domain Statistics Dashboard")

# --- Session State ---
if "selected_button" not in st.session_state:
    st.session_state.selected_button = None

# --- Top-level buttons ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("Webhosters"):
        st.session_state.selected_button = "webhoster"
with col2:
    if st.button("Hosting Countries"):
        st.session_state.selected_button = "hosting_country"
with col3:
    if st.button("Registrars"):
        st.session_state.selected_button = "registrar"
with col4:
    if st.button("Registrant Countries"):
        st.session_state.selected_button = "registrant_country"

# --- Chart Renderer ---
def show_top_10(query, label, name_col, value_col):
    try:
        result = pd.read_sql(query, engine)
        if result.empty:
            st.warning(f"No data found for {label}.")
            return

        result[name_col] = result[name_col].apply(
            lambda x: x if len(str(x)) <= 30 else str(x)[:27] + '...'
        )

        st.subheader(label)
        st.markdown('<span style="color:white; font-weight:bold;">Select Chart Type</span>',
                    unsafe_allow_html=True)

        safe_key = label.lower().replace(" ", "_").replace("-", "_")
        chart_type_key = f"chart_type_{safe_key}"
        if chart_type_key not in st.session_state:
            st.session_state[chart_type_key] = "Bar Chart"

        colb1, colb2, spacer = st.columns([1, 1, 8])
        with colb1:
            if st.button("Bar Chart", key=f"bar_{safe_key}"):
                st.session_state[chart_type_key] = "Bar Chart"
        with colb2:
            if st.button("Pie Chart", key=f"pie_{safe_key}"):
                st.session_state[chart_type_key] = "Pie Chart"

        chart_type = st.session_state[chart_type_key]

        if chart_type == "Bar Chart":
            fig = px.bar(
                result,
                x=value_col,
                y=name_col,
                orientation='h',
                text_auto=True,
                color=value_col,
                template="plotly_dark"
            )
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color="white"),
                yaxis_title=name_col.replace("_", " ").title(),
                xaxis_title="Domain Count",
                height=500,
                margin=dict(l=100, r=20, t=40, b=20),
                legend=dict(font=dict(color='white'))
            )
        else:
            fig = px.pie(
                result,
                names=name_col,
                values=value_col,
                template="plotly_dark",
                hole=0.4
            )
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color="white"),
                height=500,
                legend=dict(font=dict(color='white'))
            )
            fig.update_traces(textinfo='percent+label')

        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(result, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading data: {e}")

# --- Button logic ---
if st.session_state.selected_button == "webhoster":
    show_top_10("""
        SELECT 
            COALESCE(webhoster, 'Other') AS webhoster, 
            COUNT(*) AS domain_count
        FROM domains
        GROUP BY webhoster
        ORDER BY domain_count DESC
        LIMIT 10;
    """, "Top 10 Webhosters", "webhoster", "domain_count")

elif st.session_state.selected_button == "hosting_country":
    show_top_10("""
        SELECT 
            COALESCE(hosting_country, 'Other') AS hosting_country, 
            COUNT(*) AS domain_count
        FROM domains
        GROUP BY hosting_country
        ORDER BY domain_count DESC
        LIMIT 10;
    """, "Top 10 Hosting Countries", "hosting_country", "domain_count")

elif st.session_state.selected_button == "registrar":
    show_top_10("""
        SELECT 
            COALESCE(domain_registrar_name, 'Other') AS registrar, 
            COUNT(*) AS domain_count
        FROM domains
        GROUP BY domain_registrar_name
        ORDER BY domain_count DESC
        LIMIT 10;
    """, "Top 10 Registrars", "registrar", "domain_count")

elif st.session_state.selected_button == "registrant_country":
    show_top_10("""
        SELECT 
            COALESCE(registrant_country, 'Other') AS registrant_country, 
            COUNT(*) AS domain_count
        FROM domains
        GROUP BY registrant_country
        ORDER BY domain_count DESC
        LIMIT 10;
    """, "Top 10 Registrant Countries", "registrant_country", "domain_count")
