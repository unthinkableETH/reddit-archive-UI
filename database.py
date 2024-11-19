import psycopg2
from psycopg2.pool import SimpleConnectionPool
import streamlit as st
from contextlib import contextmanager

@st.cache_resource
def create_connection_pool():
    """Create and cache a connection pool"""
    try:
        return SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dbname=st.secrets["postgres"]["dbname"],
            user=st.secrets["postgres"]["user"],
            password=st.secrets["postgres"]["password"],
            host=st.secrets["postgres"]["host"],
            port=st.secrets["postgres"]["port"],
            connect_timeout=10
        )
    except Exception as e:
        st.error(f"Failed to create connection pool: {str(e)}")
        raise e

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    pool = create_connection_pool()
    conn = pool.getconn()
    try:
        conn.set_session(autocommit=True)
        yield conn
    finally:
        pool.putconn(conn)

def execute_query(query, params=None):
    """Execute a query and return results"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(query, params)
                return cur.fetchall()
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