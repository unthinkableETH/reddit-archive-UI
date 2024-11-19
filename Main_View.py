import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st
from datetime import datetime
import re
import os
import time
from functools import lru_cache

# Constants
POSTS_PER_PAGE = 20
COMMENTS_PER_POST = 50
CACHE_TTL = 3600  # 1 hour

# Must be the first Streamlit command
st.set_page_config(
    page_title="RepLadies Reddit Archive",
    page_icon="👜",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "RepLadies Reddit Archive"
    }
)

# Dark theme styling
st.markdown("""
    <style>
        /* Main background */
        .stApp {
            background-color: #0E1117;
        }
        
        /* Sidebar */
        .css-1d391kg {
            background-color: #1E1E1E;
        }
        
        /* Text colors */
        .stMarkdown, .stText {
            color: #FFFFFF;
        }
        
        /* Links */
        a {
            color: #FF4B4B;
            text-decoration: none;
        }
        
        a:hover {
            color: #FF7171;
            text-decoration: underline;
        }
        
        /* Buttons */
        .stButton>button {
            background-color: #FF4B4B;
            color: white;
        }
        
        .stButton>button:hover {
            background-color: #FF7171;
        }
    </style>
""", unsafe_allow_html=True)

# Helper Functions
def get_sort_order(sort_by):
    """Convert sort selection to SQL ORDER BY clause"""
    sort_mapping = {
        "newest": "created_utc DESC",
        "oldest": "created_utc ASC",
        "most_upvotes": "score DESC",
        "most_comments": "num_comments DESC"
    }
    return sort_mapping.get(sort_by, "created_utc DESC")

@st.cache_data(ttl=3600)
def get_date_bounds():
    """Get the earliest and latest dates from the database"""
    conn = get_database_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            SELECT 
                MIN(created_utc) as min_date,
                MAX(created_utc) as max_date
            FROM submissions
        """)
        result = cursor.fetchone()
        
        min_date = datetime.fromtimestamp(result['min_date']).date()
        max_date = datetime.fromtimestamp(result['max_date']).date()
        
        return min_date, max_date

def format_date(timestamp):
    """Format Unix timestamp to readable date"""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

def normalize_text(text):
    """Normalize text for search"""
    return re.sub(r'[^\w\s]', '', text.lower())

def highlight_search_terms(text, search_terms):
    """Highlight search terms in text"""
    highlighted = text
    for term in search_terms:
        pattern = re.compile(f'({term})', re.IGNORECASE)
        highlighted = pattern.sub(r'<span style="background-color: #FFD700; color: black;">\1</span>', highlighted)
    return highlighted

def display_comments(comments, search_terms=None):
    """Display comments in a threaded format"""
    if not comments:
        st.write("No comments found.")
        return

    for comment in comments:
        body = comment['body']
        if search_terms:
            body = highlight_search_terms(body, search_terms)
        
        st.markdown(
            f"""<div style='padding: 8px; border-left: 2px solid #ccc;'>
                <strong>u/{comment['author']}</strong> - 
                <i>Score: {comment['score']} | Posted on: {format_date(comment['created_utc'])}</i><br>
                <p>{body}</p>
            </div>""", 
            unsafe_allow_html=True
        )
    @st.cache_resource(ttl=CACHE_TTL)
def get_database_connection():
    conn = psycopg2.connect(
        dbname=st.secrets["postgres"]["dbname"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"],
        host=st.secrets["postgres"]["host"],
        port=st.secrets["postgres"]["port"],
        connect_timeout=10
    )
    conn.set_session(autocommit=True)
    return conn

@st.cache_data(ttl=CACHE_TTL)
def fetch_paginated_data(page_num, sort_by="newest", search_query=None):
    """Fetch one page worth of data in a single query"""
    offset = (page_num - 1) * POSTS_PER_PAGE
    conn = get_database_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Get total post count
            cursor.execute("SELECT COUNT(*) FROM submissions")
            total_posts = cursor.fetchone()['count']
            
            # Fetch posts with their comment counts
            order_by = get_sort_order(sort_by)
            cursor.execute(f"""
                SELECT id, title, selftext, author, created_utc, score, num_comments
                FROM submissions
                ORDER BY {order_by}
                LIMIT %s OFFSET %s
            """, (POSTS_PER_PAGE, offset))
            
            posts = cursor.fetchall()
            
            if not posts:
                return [], {}, total_posts
            
            # Fetch comments for all posts in this page
            post_ids = [post['id'] for post in posts]
            cursor.execute("""
                WITH ranked_comments AS (
                    SELECT 
                        id, body, author, created_utc, score, submission_id, parent_id,
                        ROW_NUMBER() OVER (PARTITION BY submission_id ORDER BY score DESC) as row_num
                    FROM comments
                    WHERE submission_id = ANY(%s)
                )
                SELECT *
                FROM ranked_comments
                WHERE row_num <= %s
            """, (post_ids, COMMENTS_PER_POST))
            
            # Organize comments by post
            comments = cursor.fetchall()
            post_comments = {post_id: [] for post_id in post_ids}
            for comment in comments:
                post_comments[comment['submission_id']].append(comment)
            
            return posts, post_comments, total_posts
            
    except Exception as e:
        st.error(f"Database error: {type(e).__name__}")
        return [], {}, 0

@st.cache_data(ttl=CACHE_TTL)
def search_reddit_optimized(query, search_type, exact_match, page_num, sort_by, start_date=None, end_date=None):
    """Optimized search function"""
    offset = (page_num - 1) * POSTS_PER_PAGE
    conn = get_database_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Build search conditions
            search_conditions = []
            params = []
            
            if search_type == "title":
                search_conditions.append("LOWER(title) LIKE LOWER(%s)")
                params.append(f"%{query}%" if not exact_match else query)
            elif search_type == "content":
                search_conditions.append("LOWER(selftext) LIKE LOWER(%s)")
                params.append(f"%{query}%" if not exact_match else query)
            else:  # both
                search_conditions.append("(LOWER(title) LIKE LOWER(%s) OR LOWER(selftext) LIKE LOWER(%s))")
                params.extend([f"%{query}%" if not exact_match else query] * 2)
            
            # Add date range conditions if provided
            if start_date:
                search_conditions.append("created_utc >= %s")
                params.append(int(start_date.timestamp()))
            if end_date:
                search_conditions.append("created_utc <= %s")
                params.append(int(end_date.timestamp()))
            
            where_clause = " AND ".join(search_conditions)
            order_by = get_sort_order(sort_by)
            
            # Get total count for pagination
            count_query = f"SELECT COUNT(*) FROM submissions WHERE {where_clause}"
            cursor.execute(count_query, params)
            total_results = cursor.fetchone()['count']
            
            # Fetch matching posts
            query = f"""
                SELECT id, title, selftext, author, created_utc, score, num_comments
                FROM submissions
                WHERE {where_clause}
                ORDER BY {order_by}
                LIMIT %s OFFSET %s
            """
            cursor.execute(query, params + [POSTS_PER_PAGE, offset])
            posts = cursor.fetchall()
            
            if not posts:
                return [], {}, total_results
            
            # Fetch comments for matching posts
            post_ids = [post['id'] for post in posts]
            cursor.execute("""
                WITH ranked_comments AS (
                    SELECT 
                        id, body, author, created_utc, score, submission_id, parent_id,
                        ROW_NUMBER() OVER (PARTITION BY submission_id ORDER BY score DESC) as row_num
                    FROM comments
                    WHERE submission_id = ANY(%s)
                )
                SELECT *
                FROM ranked_comments
                WHERE row_num <= %s
            """, (post_ids, COMMENTS_PER_POST))
            
            comments = cursor.fetchall()
            post_comments = {post_id: [] for post_id in post_ids}
            for comment in comments:
                post_comments[comment['submission_id']].append(comment)
            
            return posts, post_comments, total_results
            
    except Exception as e:
        st.error(f"Database error: {type(e).__name__}")
        return [], {}, 0
    # Main page layout
st.title("RepLadies Reddit Archive")

# Sidebar controls
with st.sidebar:
    # Search controls
    search_query = st.text_input("Enter search term", key="search")
    
    if search_query:
        search_type = st.radio(
            "Search in",
            ["title", "content", "both"],
            format_func=lambda x: x.capitalize(),
            key="search_type"
        )
        
        exact_match = st.checkbox("Exact match", key="exact_match")
        highlight_enabled = st.checkbox("Highlight matches", value=True, key="highlight")
    
    # Sorting controls
    sort_by = st.selectbox(
        "Sort posts by",
        ["most_upvotes", "most_comments", "newest", "oldest"],
        format_func=lambda x: {
            "most_upvotes": "Most Upvotes",
            "most_comments": "Most Comments",
            "newest": "Newest",
            "oldest": "Oldest"
        }[x],
        key="sort_posts"
    )
    
    comment_sort = st.selectbox(
        "Sort comments by", 
        ["most_upvotes", "newest", "oldest"],
        format_func=lambda x: {
            "most_upvotes": "Most Upvotes",
            "newest": "Newest",
            "oldest": "Oldest"
        }[x],
        key="comment_sort"
    )
    
    # Date range picker for search
    if search_query:
        min_date, max_date = get_date_bounds()
        
        st.subheader("Date Range Filter")
        start_date = st.date_input(
            "Start Date",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
            key="start_date"
        )
        end_date = st.date_input(
            "End Date",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
            key="end_date"
        )
        
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

# Pagination
page_num = st.session_state.get('page_num', 1)

# Fetch data
if search_query:
    posts, post_comments, total_results = search_reddit_optimized(
        search_query,
        search_type,
        exact_match,
        page_num,
        sort_by,
        start_datetime if 'start_datetime' in locals() else None,
        end_datetime if 'end_datetime' in locals() else None
    )
    search_terms = normalize_text(search_query).split() if highlight_enabled else []
else:
    posts, post_comments, total_results = fetch_paginated_data(page_num, sort_by)
    search_terms = []

# Calculate pagination
total_pages = (total_results - 1) // POSTS_PER_PAGE + 1

# Display results
if total_results == 0:
    st.markdown("<h2 style='text-align: center; color: red; font-weight: bold;'>No results found</h2>", unsafe_allow_html=True)
else:
    st.write(f"Page {page_num} of {total_pages}")
    
    for post in posts:
        with st.container():
            st.subheader(post['title'])
            st.write(post['selftext'])
            st.write(f"Score: {post['score']} | Comments: {post['num_comments']}")
            st.markdown(
                f'Posted by <a href="/Profile_View?username={post["author"]}">u/{post["author"]}</a> on {format_date(post["created_utc"])}',
                unsafe_allow_html=True
            )

            with st.expander("View Comments"):
                if post['id'] in post_comments:
                    display_comments(post_comments[post['id']], search_terms)
            st.markdown("---")

# Pagination controls
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if page_num > 1:
        if st.button("← Previous"):
            st.session_state.page_num = page_num - 1
            st.experimental_rerun()
with col2:
    st.write(f"Page {page_num} of {total_pages}")
with col3:
    if page_num < total_pages:
        if st.button("Next →"):
            st.session_state.page_num = page_num + 1
            st.experimental_rerun()
