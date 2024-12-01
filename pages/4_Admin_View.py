import streamlit as st
from database import execute_query
from utils import DARK_THEME_CSS

st.set_page_config(
    page_title="Admin View",
    page_icon="🛠️",
    layout="wide"
)

st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

st.title("Admin View")

# Password protection
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

if not st.session_state.admin_authenticated:
    with st.form("admin_login"):
        password = st.text_input("Admin Password", type="password")
        if st.form_submit_button("Login"):
            if password == st.secrets["admin_password"]:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password")
    st.stop()

# Admin Tools
st.header("Database Information")

def check_indexes():
    """Check existing indexes on the submissions table"""
    query = """
    SELECT 
        schemaname as schema,
        tablename as table,
        indexname as index,
        indexdef as definition
    FROM pg_indexes
    WHERE tablename = 'submissions'
    ORDER BY indexname;
    """
    try:
        results = execute_query(query)
        if not results:
            st.warning("No indexes found on submissions table")
            return
            
        for idx in results:
            with st.expander(f"Index: {idx['index']}"):
                st.code(idx['definition'], language="sql")
    except Exception as e:
        st.error(f"Error checking indexes: {str(e)}")

def check_table_stats():
    """Check table statistics"""
    query = """
    SELECT 
        relname as table_name,
        n_live_tup as row_count,
        pg_size_pretty(pg_total_relation_size(quote_ident(relname))) as total_size
    FROM pg_stat_user_tables
    WHERE schemaname = 'public'
    ORDER BY n_live_tup DESC;
    """
    try:
        results = execute_query(query)
        if results:
            st.dataframe(results)
    except Exception as e:
        st.error(f"Error checking table stats: {str(e)}")

# Database Stats Section
col1, col2 = st.columns(2)

with col1:
    st.subheader("Table Statistics")
    if st.button("Check Table Stats"):
        check_table_stats()

with col2:
    st.subheader("Database Indexes")
    if st.button("Check Indexes"):
        check_indexes()

# Index Management
st.header("Index Management")

with st.expander("Add Text Search Indexes"):
    st.warning("⚠️ Creating indexes may take several minutes and temporarily slow down the database")
    if st.button("Create Text Search Indexes"):
        try:
            queries = [
                """
                CREATE INDEX IF NOT EXISTS submissions_selftext_tsv_idx 
                ON submissions USING gin(to_tsvector('english', selftext));
                """,
                """
                CREATE INDEX IF NOT EXISTS submissions_title_tsv_idx 
                ON submissions USING gin(to_tsvector('english', title));
                """
            ]
            
            for query in queries:
                with st.spinner("Creating indexes... This may take a few minutes"):
                    execute_query(query)
            st.success("Indexes created successfully!")
            
        except Exception as e:
            st.error(f"Error creating indexes: {str(e)}")

