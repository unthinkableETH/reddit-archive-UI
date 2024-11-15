import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st
from datetime import datetime
import re
import os
import time

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
        [data-testid="stSidebar"] {
            background-color: #262730;
        }
        
        /* Card backgrounds */
        [data-testid="stExpander"] {
            background-color: #262730;
        }
        
        /* Text colors */
        .stMarkdown {
            color: #FAFAFA;
        }
        
        /* All links should be blue */
        a {
            color: #4A9EFF !important;
        }
        a:hover {
            color: #7CB9FF !important;
            text-decoration: none;
        }
        
        /* Dividers */
        hr {
            border-color: #333333;
        }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_database_connection():
    retries = 3
    for attempt in range(retries):
        try:
            conn = psycopg2.connect(
                dbname=st.secrets["postgres"]["dbname"],
                user=st.secrets["postgres"]["user"],
                password=st.secrets["postgres"]["password"],
                host=st.secrets["postgres"]["host"],
                port=st.secrets["postgres"]["port"],
                connect_timeout=10
            )
            return conn
        except psycopg2.OperationalError as e:
            if attempt == retries - 1:
                st.error(f"Failed to connect to database after {retries} attempts: {e}")
                raise
            st.warning(f"Connection attempt {attempt + 1} failed, retrying...")
            time.sleep(2 ** attempt)

# Helper function to convert UTC timestamp to a readable date
def format_date(utc_timestamp):
    try:
        utc_timestamp = int(utc_timestamp)
        return datetime.utcfromtimestamp(utc_timestamp).strftime('%B %d, %Y %I:%M %p')
    except ValueError:
        return "Invalid Date"

# Helper function to normalize text for exact match
def normalize_text(text):
    return " ".join(text.lower().split())

def highlight_search_terms(text, search_terms):
    """Highlight search terms in text with yellow background"""
    if not text or not search_terms:
        return text
    
    # Escape HTML special characters first
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    
    # Create a pattern that matches any of the search terms (case insensitive)
    pattern = '|'.join(map(re.escape, search_terms))
    if not pattern:
        return text
    
    def highlight_match(match):
        return f'<span style="background-color: #ffd700;">{match.group(0)}</span>'
    
    return re.sub(f'({pattern})', highlight_match, text, flags=re.IGNORECASE)

def get_total_search_results(query, search_type, exact_match, start_timestamp=None, end_timestamp=None):
    """Get total number of results for pagination"""
    conn = get_database_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        date_filter = ""
        params = []
        if start_timestamp:
            date_filter += " AND created_utc >= %s"
            params.append(start_timestamp)
        if end_timestamp:
            date_filter += " AND created_utc <= %s"
            params.append(end_timestamp)

        total = 0
        if exact_match:
            normalized_query = normalize_text(query)
            if search_type in ["post_title", "post_body", "everything"]:
                where_clause = {
                    "post_title": "LOWER(title) LIKE LOWER(%s)",
                    "post_body": "LOWER(selftext) LIKE LOWER(%s)",
                    "everything": "LOWER(title || ' ' || selftext) LIKE LOWER(%s)"
                }.get(search_type)
                cursor.execute(f"""
                    SELECT COUNT(*) as count
                    FROM submissions 
                    WHERE {where_clause} {date_filter}
                """, (f"%{normalized_query}%", *params))
                total += cursor.fetchone()['count']

            if search_type in ["comments", "everything"]:
                cursor.execute(f"""
                    SELECT COUNT(*) as count
                    FROM comments 
                    WHERE LOWER(body) LIKE LOWER(%s) {date_filter}
                """, (f"%{normalized_query}%", *params))
                total += cursor.fetchone()['count']
        else:
            search_terms = ' & '.join(query.split())
            if search_type in ["post_title", "post_body", "everything"]:
                cursor.execute(f"""
                    SELECT COUNT(*) as count
                    FROM submissions 
                    WHERE search_vector @@ to_tsquery('english', %s) {date_filter}
                """, (search_terms, *params))
                total += cursor.fetchone()['count']

            if search_type in ["comments", "everything"]:
                cursor.execute(f"""
                    SELECT COUNT(*) as count
                    FROM comments 
                    WHERE search_vector @@ to_tsquery('english', %s) {date_filter}
                """, (search_terms, *params))
                total += cursor.fetchone()['count']

        return total

def get_date_bounds():
    """Get earliest and latest dates from both posts and comments"""
    conn = get_database_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""
            SELECT 
                MIN(created_utc) as min_date,
                MAX(created_utc) as max_date
            FROM (
                SELECT created_utc FROM submissions
                UNION ALL
                SELECT created_utc FROM comments
            ) dates
        """)
        result = cursor.fetchone()
        min_date = datetime.utcfromtimestamp(result['min_date'])
        max_date = datetime.utcfromtimestamp(result['max_date'])
        return min_date.date(), max_date.date()

def get_sort_order(sort_by):
    """Convert sort_by parameter to SQL ORDER BY clause"""
    sort_orders = {
        "most_upvotes": "score DESC",
        "newest": "created_utc DESC",
        "oldest": "created_utc ASC",
        "most_comments": "num_comments DESC"
    }
    return sort_orders.get(sort_by, "score DESC")

def search_reddit(query, search_type, exact_match, offset, limit, sort_by="newest", start_date=None, end_date=None):
    """Search posts and comments based on query and filters"""
    conn = get_database_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        posts = []
        comments = []
        
        date_filter = ""
        params = []
        if start_date:
            date_filter += " AND created_utc >= %s"
            params.append(int(start_date.timestamp()))
        if end_date:
            date_filter += " AND created_utc <= %s"
            params.append(int(end_date.timestamp()))

        if search_type in ["post_title", "post_body", "everything"]:
            if exact_match:
                where_clause = {
                    "post_title": "LOWER(title) LIKE LOWER(%s)",
                    "post_body": "LOWER(selftext) LIKE LOWER(%s)",
                    "everything": "LOWER(title || ' ' || selftext) LIKE LOWER(%s)"
                }.get(search_type)
                cursor.execute(f"""
                    SELECT * FROM submissions 
                    WHERE {where_clause} {date_filter}
                    ORDER BY {get_sort_order(sort_by)}
                    LIMIT %s OFFSET %s
                """, (f"%{query}%", *params, limit, offset))
            else:
                search_terms = ' & '.join(query.split())
                cursor.execute(f"""
                    SELECT *, ts_rank(search_vector, to_tsquery('english', %s)) as rank 
                    FROM submissions 
                    WHERE search_vector @@ to_tsquery('english', %s) {date_filter}
                    ORDER BY rank DESC, {get_sort_order(sort_by)}
                    LIMIT %s OFFSET %s
                """, (search_terms, search_terms, *params, limit, offset))
            posts = cursor.fetchall()

        if search_type in ["comments", "everything"]:
            if exact_match:
                cursor.execute(f"""
                    SELECT * FROM comments 
                    WHERE LOWER(body) LIKE LOWER(%s) {date_filter}
                    ORDER BY {get_sort_order(sort_by)}
                    LIMIT %s OFFSET %s
                """, (f"%{query}%", *params, limit, offset))
            else:
                search_terms = ' & '.join(query.split())
                cursor.execute(f"""
                    SELECT *, ts_rank(search_vector, to_tsquery('english', %s)) as rank 
                    FROM comments 
                    WHERE search_vector @@ to_tsquery('english', %s) {date_filter}
                    ORDER BY rank DESC, {get_sort_order(sort_by)}
                    LIMIT %s OFFSET %s
                """, (search_terms, search_terms, *params, limit, offset))
            comments = cursor.fetchall()

        return posts, comments

def fetch_posts(offset, limit, sort_by="newest"):
    """Fetch posts with pagination"""
    conn = get_database_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        order_by = get_sort_order(sort_by)
        cursor.execute(f"""
            SELECT id, title, selftext, author, created_utc,
                   score, num_comments, subreddit
            FROM submissions
            ORDER BY {order_by}
            LIMIT %s OFFSET %s
        """, (limit, offset))
        return cursor.fetchall()

def fetch_comments_for_post(post_id, sort_by="most_upvotes"):
    """Fetch all comments for a given post"""
    conn = get_database_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        order_by = get_sort_order(sort_by)
        cursor.execute(f"""
            SELECT id, body, author, created_utc, score, 
                   submission_id, parent_id, subreddit
            FROM comments 
            WHERE submission_id = %s 
            ORDER BY {order_by}
        """, (add_prefix(post_id, 't3'),))
        return cursor.fetchall()

def display_comments(comments, search_terms=None):
    """Display comments in a hierarchical structure"""
    if not comments:
        st.write("No comments yet.")
        return
        
    comment_dict = {}
    top_level_comments = []
    
    # First pass: create dictionary of all comments
    for comment in comments:
        comment_dict[clean_reddit_id(comment['id'])] = {
            'data': comment,
            'replies': [],
            'level': 0
        }
    
    # Second pass: build the hierarchy
    for comment in comments:
        parent_id = clean_reddit_id(comment['parent_id'])
        comment_id = clean_reddit_id(comment['id'])
        
        if comment['parent_id'].startswith('t3_'):  # Top-level comment
            top_level_comments.append(comment_id)
        elif parent_id in comment_dict:  # Reply to another comment
            comment_dict[parent_id]['replies'].append(comment_id)
            comment_dict[comment_id]['level'] = comment_dict[parent_id]['level'] + 1
    
    def display_comment_tree(comment_id, level=0):
        if comment_id not in comment_dict:
            return
            
        comment = comment_dict[comment_id]['data']
        replies = comment_dict[comment_id]['replies']
        level = comment_dict[comment_id]['level']
        
        body = comment['body']
        if search_terms:
            body = highlight_search_terms(body, search_terms)
        
        left_margin = min(level * 20, 200)
        
        st.markdown(
            f"""<div style='margin-left: {left_margin}px; padding: 8px; border-left: 2px solid #ccc;'>
                <strong><a href="/Profile_View?username={comment['author']}">u/{comment['author']}</a></strong> - 
                <i>Score: {comment['score']} | Posted on: {format_date(comment['created_utc'])}</i><br>
                <p>{body}</p>
            </div>""", 
            unsafe_allow_html=True
        )
        
        for reply_id in replies:
            display_comment_tree(reply_id)
    
    # Display all top-level comments and their replies
    for comment_id in top_level_comments:
        display_comment_tree(comment_id)

def get_post_url(link_id, comment_id):
    post_id = link_id.split('_')[1] if '_' in link_id else link_id
    return f"/Post_View?post_id={post_id}&comment_id={comment_id}"

def clean_reddit_id(reddit_id, keep_prefix=False):
    """Standardize Reddit ID format
    Example: 't3_abc123' -> 'abc123' (keep_prefix=False)
            't3_abc123' -> 't3_abc123' (keep_prefix=True)
    """
    if not reddit_id:
        return None
    if reddit_id.startswith(('t1_', 't3_')):
        return reddit_id if keep_prefix else reddit_id.split('_')[1]
    return reddit_id

def add_prefix(id_str, type_prefix):
    """Add Reddit type prefix if missing
    Example: 'abc123' -> 't3_abc123' (type_prefix='t3')
    """
    if not id_str:
        return None
    if id_str.startswith(('t1_', 't3_')):
        return id_str
    return f"{type_prefix}_{id_str}"

def validate_post_data(post):
    """Ensure post data has all required fields"""
    required_fields = ['id', 'title', 'selftext', 'author', 'created_utc', 
                      'score', 'num_comments', 'subreddit']
    return all(field in post for field in required_fields)

def validate_comment_data(comment):
    """Ensure comment data has all required fields"""
    required_fields = ['id', 'body', 'author', 'created_utc', 
                      'score', 'submission_id', 'parent_id']
    return all(field in comment for field in required_fields)

# Update the main title
st.title("RepLadies Reddit Archive")

posts_per_page = 20
page_num = st.session_state.get("page_num", 1)
offset = (page_num - 1) * posts_per_page

# Sidebar controls
st.sidebar.subheader("Controls")

# Search options
search_query = st.sidebar.text_input("Enter search term")
if search_query:
    search_type = st.sidebar.radio(
        "Search in:", 
        ["post_title", "post_body", "comments", "everything"],
        format_func=lambda x: {
            "post_title": "Post Titles",
            "post_body": "Post Body Text",
            "comments": "Comments Only",
            "everything": "Everything ℹ️"
        }[x],
        help="When searching 'Everything', posts will be displayed first, followed by comments"
    )
    exact_match = st.sidebar.toggle("Exact match", value=False)
    highlight_enabled = st.sidebar.toggle("Highlight search terms", value=True)

# Sort options
sort_by = st.sidebar.selectbox(
    "Sort posts by", 
    ["most_upvotes", "newest", "oldest", "most_comments"],
    format_func=lambda x: {
        "most_upvotes": "Most Upvotes",
        "newest": "Newest",
        "oldest": "Oldest",
        "most_comments": "Most Comments"
    }[x],
    index=0
)

comment_sort = st.sidebar.selectbox(
    "Sort comments by", 
    ["most_upvotes", "newest", "oldest"],
    format_func=lambda x: {
        "most_upvotes": "Most Upvotes",
        "newest": "Newest",
        "oldest": "Oldest"
    }[x],
    index=0,
    key='comment_sort'
)

# Date range picker
if search_query:
    min_date, max_date = get_date_bounds()
    
    st.sidebar.subheader("Date Range Filter")
    start_date = st.sidebar.date_input(
        "Start Date",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        key="start_date"
    )
    end_date = st.sidebar.date_input(
        "End Date",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        key="end_date"
    )
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

# Search or fetch posts
if search_query:
    normalized_query = normalize_text(search_query)
    search_terms = normalized_query.split() if highlight_enabled else []
    
    start_timestamp = int(start_datetime.timestamp()) if 'start_datetime' in locals() else None
    end_timestamp = int(end_datetime.timestamp()) if 'end_datetime' in locals() else None
    
    posts, comments = search_reddit(
        search_query, 
        search_type, 
        exact_match, 
        offset, 
        posts_per_page, 
        sort_by,
        start_datetime if 'start_datetime' in locals() else None,
        end_datetime if 'end_datetime' in locals() else None
    )
    
    total_results = get_total_search_results(
        search_query, 
        search_type, 
        exact_match,
        start_timestamp,
        end_timestamp
    )
else:
    search_terms = []
    posts = fetch_posts(offset, posts_per_page, sort_by)
    comments = []
    conn = get_database_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("SELECT COUNT(*) FROM submissions")
        total_results = cursor.fetchone()['count']

# Calculate pagination
total_pages = (total_results - 1) // posts_per_page + 1
page_num = min(page_num, total_pages)

# Display results
if total_results == 0:
    st.markdown("<h2 style='text-align: center; color: red; font-weight: bold;'>No results found</h2>", unsafe_allow_html=True)
else:
    st.write(f"Page {page_num} of {total_pages}")
    
    if search_query:
        if posts:
            st.subheader("Posts:")
            for post in posts:
                title = post['title'].replace("<", "&lt;").replace(">", "&gt;")
                selftext = post['selftext'].replace("<", "&lt;").replace(">", "&gt;")
                
                if highlight_enabled:
                    title = highlight_search_terms(title, search_terms)
                    selftext = highlight_search_terms(selftext, search_terms)

                st.markdown(f"<h3>{title}</h3>", unsafe_allow_html=True)
                st.markdown(selftext, unsafe_allow_html=True)
                st.write(f"Score: {post['score']} | Comments: {post['num_comments']}")
                st.markdown(
                    f'Posted by <a href="/Profile_View?username={post["author"]}">u/{post["author"]}</a> on {format_date(post["created_utc"])} in r/{post["subreddit"]}',
                    unsafe_allow_html=True
                )

                with st.expander("View Comments"):
                    post_comments = fetch_comments_for_post(post['id'], comment_sort)
                    display_comments(post_comments, search_terms if highlight_enabled else None)
                st.markdown("---")

        if comments and search_type in ["comments", "everything"]:
            st.subheader("Search Results in Comments:")
            for comment in comments:
                body = comment['body']
                if highlight_enabled:
                    body = highlight_search_terms(body, search_terms)
                
                has_valid_post = False
                if comment['submission_id']:
                    post_id = comment['submission_id'].split('_')[1]
                    conn = get_database_connection()
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute("SELECT id FROM submissions WHERE id = %s", (post_id,))
                        has_valid_post = cursor.fetchone() is not None

                st.markdown(
                    f"""<div style='padding: 8px; border-left: 2px solid #ccc;'>
                        <strong><a href="/Profile_View?username={comment['author']}">u/{comment['author']}</a></strong> - 
                        <i>Score: {comment['score']} | Posted on: {format_date(comment['created_utc'])} in r/{comment['subreddit']}</i><br>
                        <p>{body}</p>
                        {f'<a href="{get_post_url(comment["submission_id"], comment["id"])}" target="_blank">View Full Post and Comments</a>' if has_valid_post else ''}
                    </div>""", 
                    unsafe_allow_html=True
                )
                st.markdown("---")

    else:
        for post in posts:
            st.subheader(post['title'])
            st.write(post['selftext'])
            st.write(f"Score: {post['score']} | Comments: {post['num_comments']}")
            st.markdown(
                f'Posted by <a href="/Profile_View?username={post["author"]}">u/{post["author"]}</a> on {format_date(post["created_utc"])} in r/{post["subreddit"]}',
                unsafe_allow_html=True
            )

            with st.expander("View Comments"):
                post_comments = fetch_comments_for_post(post['id'], comment_sort)
                display_comments(post_comments, search_terms)
            st.markdown("---")

    if page_num == total_pages:
        st.markdown("<h2 style='text-align: center; color: red; font-weight: bold;'>You have reached the end of the results.</h2>", unsafe_allow_html=True)

    # Pagination controls
    st.sidebar.write(f"Page {page_num} of {total_pages}")
    
    if page_num < total_pages:
        if st.sidebar.button("Next page"):
            st.session_state.page_num = page_num + 1
            st.experimental_rerun()

    if page_num > 1:
        if st.sidebar.button("Previous page"):
            st.session_state.page_num = page_num - 1
            st.experimental_rerun()
