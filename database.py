import psycopg2
import streamlit as st
from psycopg2.extras import RealDictCursor

@st.cache_resource
def get_database_connection():
    conn = psycopg2.connect(
        dbname=st.secrets["postgres"]["dbname"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"],
        host=st.secrets["postgres"]["host"],
        port=st.secrets["postgres"]["port"],
        connect_timeout=10,
        cursor_factory=RealDictCursor
    )
    conn.set_session(autocommit=True)
    return conn

def execute_query(query, params=None):
    """Execute a query and return results"""
    conn = get_database_connection()
    with conn.cursor() as cur:
        try:
            cur.execute(query, params)
            results = cur.fetchall()
            return results
        except Exception as e:
            st.error(f"Query execution failed: {str(e)}")
            raise e

def execute_query_single(query, params=None):
    """Execute a query and return a single result"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(query, params)
                return cur.fetchone()
            except Exception as e:
                st.error(f"Query execution failed: {str(e)}")
                raise e
