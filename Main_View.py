import sqlite3
from datetime import datetime
import streamlit as st
import re
import os
import requests
import gzip           # Required - Database decompression
import requests 
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

# At the top of your file, after imports
@st.cache_resource(show_spinner=False)
def get_database_connection():
    db_path = 'reddit_data.db'
    
    if not os.path.exists(db_path):
        download_database(db_path)
    
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

def download_database(db_path):
    try:
        url = 'https://repladies-archive.s3.us-east-2.amazonaws.com/reddit_data.db.gz'
        
        # Create placeholders for messages
        info_placeholder = st.empty()
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        
        info_placeholder.info("""
        🔒 First-time Setup: Loading RepLadies Archive to Streamlit's secure cloud server.
        
        The archive is not downloaded to your personal device - it's securely stored on 
        Streamlit's servers.
        """)
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        
        # Download compressed file
        temp_gz_path = f"{db_path}.gz"
        start_time = datetime.now()
        
        with open(temp_gz_path, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    percentage = (downloaded / total_size) * 100
                    progress_bar.progress(downloaded / total_size)
                    
                    # Calculate estimated time remaining
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    if downloaded > 0:
                        download_rate = downloaded / elapsed_time  # bytes per second
                        remaining_bytes = total_size - downloaded
                        estimated_seconds = remaining_bytes / download_rate if download_rate > 0 else 0
                        
                        status_placeholder.info(
                            f"📥 Loading archive... {percentage:.1f}% "
                            f"(about {int(estimated_seconds/60)} minutes remaining)"
                        )
        
        status_placeholder.info("🗜️ Preparing archive...")
        progress_bar.progress(1.0)
        
        # Decompress the file
        with gzip.open(temp_gz_path, 'rb') as gz_file:
            with open(db_path, 'wb') as out_file:
                out_file.write(gz_file.read())
        
        # Clean up
        os.remove(temp_gz_path)
        info_placeholder.empty()
        status_placeholder.success("✅ Archive ready!")
        progress_bar.empty()
        
    except Exception as e:
        st.error(f"Error loading archive: {e}")
        for path in [db_path, f"{db_path}.gz"]:
            if os.path.exists(path):
                os.remove(path)
        raise e

# Replace your current connection with:
conn = get_database_connection()
cursor = conn.cursor()

# Helper function to convert UTC timestamp to a readable date
def format_date(utc_timestamp):
    try:
        utc_timestamp = int(utc_timestamp)
        return datetime.utcfromtimestamp(utc_timestamp).strftime('%B %d, %Y %I:%M %p')
    except ValueError:
        return "Invalid Date"

# Search functionality with FTS
def get_total_search_results(query, search_type, exact_match, start_timestamp=None, end_timestamp=None):
    total_posts = 0
    total_comments = 0
    
    normalized_query = normalize_text(query)
    query_words = normalized_query.split()
    fts_query = ' AND '.join(f'"{word}"' for word in query_words)

    # Build date filter
    date_filter = ""
    params = []
    if start_timestamp:
        date_filter += " AND created_utc >= ?"
        params.append(start_timestamp)
    if end_timestamp:
        date_filter += " AND created_utc <= ?"
        params.append(end_timestamp)

    try:
        if search_type in ["post_title", "post_body", "everything"]:
            if exact_match:
                where_clause = {
                    "post_title": "LOWER(title) LIKE ?",
                    "post_body": "LOWER(selftext) LIKE ?",
                    "everything": "LOWER(title || ' ' || selftext) LIKE ?"
                }.get(search_type, "LOWER(title || ' ' || selftext) LIKE ?")
                
                cursor.execute(f"""
                    SELECT COUNT(*) FROM submissions 
                    WHERE {where_clause} {date_filter}
                """, (f"%{normalized_query}%", *params))
            else:
                match_clause = {
                    "post_title": "title MATCH ?",
                    "post_body": "selftext MATCH ?",
                    "everything": "fts_submissions MATCH ?"
                }.get(search_type, "fts_submissions MATCH ?")
                
                cursor.execute(f"""
                    SELECT COUNT(*) FROM submissions 
                    WHERE id IN (
                        SELECT id FROM fts_submissions 
                        WHERE {match_clause}
                    ) {date_filter}
                """, (fts_query, *params))
            total_posts = cursor.fetchone()[0]

        if search_type in ["comments", "everything"]:
            if exact_match:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM comments 
                    WHERE LOWER(body) LIKE ? {date_filter}
                """, (f"%{normalized_query}%", *params))
            else:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM comments 
                    WHERE id IN (
                        SELECT id FROM fts_comments 
                        WHERE fts_comments MATCH ?
                    ) {date_filter}
                """, (fts_query, *params))
            total_comments = cursor.fetchone()[0]

        return total_posts + total_comments
    except sqlite3.DatabaseError as e:
        st.error(f"Error fetching search results: {e}")
        return 0

# Helper function to normalize text for exact match (case insensitive, ignore extra spaces)
def normalize_text(text):
    # Remove extra spaces and convert to lowercase
    return " ".join(text.lower().split())

# Add these functions near the top with other helper functions
def get_date_bounds():
    # Get earliest and latest dates from both posts and comments
    cursor.execute("""
        SELECT 
            MIN(created_utc) as min_date,
            MAX(created_utc) as max_date
        FROM (
            SELECT created_utc FROM submissions
            UNION ALL
            SELECT created_utc FROM comments
        )
    """)
    result = cursor.fetchone()
    
    # Convert to datetime objects
    min_date = datetime.utcfromtimestamp(result[0])
    max_date = datetime.utcfromtimestamp(result[1])
    
    return min_date.date(), max_date.date()

# Add this helper function near the other helper functions
def get_sort_order(sort_by):
    """Convert sort_by parameter to SQL ORDER BY clause"""
    sort_orders = {
        "most_upvotes": "score DESC",
        "newest": "created_utc DESC",
        "oldest": "created_utc ASC",
        "most_comments": "num_comments DESC"
    }
    return sort_orders.get(sort_by, "score DESC")  # Default to most_upvotes if invalid sort_by

# Update the search_reddit function to use proper sorting
def search_reddit(query, search_type, exact_match, offset, limit, sort_by="newest", start_date=None, end_date=None):
    normalized_query = normalize_text(query)
    query_words = normalized_query.split()
    fts_query = ' AND '.join(f'"{word}"' for word in query_words)
    posts = []
    comments = []
    
    # Convert datetime to Unix timestamp for SQLite
    start_timestamp = int(start_date.timestamp()) if start_date else None
    end_timestamp = int(end_date.timestamp()) if end_date else None
    
    date_filter = ""
    params = []
    
    if start_timestamp:
        date_filter += " AND created_utc >= ?"
        params.append(start_timestamp)
    if end_timestamp:
        date_filter += " AND created_utc <= ?"
        params.append(end_timestamp)

    # For posts, use the full sort_order
    post_sort = get_sort_order(sort_by)
    
    # For comments, use the comment_sort from sidebar
    comment_sort = {
        "most_upvotes": "score DESC",
        "newest": "created_utc DESC",
        "oldest": "created_utc ASC"
    }.get(st.session_state.get('comment_sort', 'most_upvotes'), "score DESC")

    # Handle post searches
    if search_type in ["post_title", "post_body", "everything"]:
        if exact_match:
            where_clause = {
                "post_title": "LOWER(title) LIKE ?",
                "post_body": "LOWER(selftext) LIKE ?",
                "everything": "LOWER(title || ' ' || selftext) LIKE ?"
            }.get(search_type, "LOWER(title || ' ' || selftext) LIKE ?")
            
            cursor.execute(f"""
                SELECT title, selftext, author, created_utc, id, score, num_comments, subreddit
                FROM submissions 
                WHERE {where_clause} {date_filter}
                ORDER BY {post_sort}
                LIMIT ? OFFSET ?
                """, (f"%{normalized_query}%", *params, limit, offset))
        else:
            match_clause = {
                "post_title": "title MATCH ?",
                "post_body": "selftext MATCH ?",
                "everything": "fts_submissions MATCH ?"
            }.get(search_type, "fts_submissions MATCH ?")
            
            cursor.execute(f"""
                SELECT s.title, s.selftext, s.author, s.created_utc, s.id, s.score, s.num_comments, s.subreddit
                FROM submissions s
                WHERE s.id IN (
                    SELECT id FROM fts_submissions 
                    WHERE {match_clause}
                ) {date_filter}
                ORDER BY {post_sort}
                LIMIT ? OFFSET ?
                """, (fts_query, *params, limit, offset))
        posts = cursor.fetchall()

    # Handle comment searches
    if search_type in ["comments", "everything"]:
        if exact_match:
            cursor.execute(f"""
                SELECT id, link_id, parent_id, author, body, created_utc, score, subreddit
                FROM comments 
                WHERE LOWER(body) LIKE ? {date_filter}
                ORDER BY {comment_sort}
                LIMIT ? OFFSET ?
                """, (f"%{normalized_query}%", *params, limit, offset))
        else:
            cursor.execute(f"""
                SELECT c.id, c.link_id, c.parent_id, c.author, c.body, c.created_utc, c.score, c.subreddit
                FROM comments c
                WHERE c.id IN (
                    SELECT id FROM fts_comments 
                    WHERE fts_comments MATCH ?
                ) {date_filter}
                ORDER BY {comment_sort}
                LIMIT ? OFFSET ?
                """, (fts_query, *params, limit, offset))
        comments = cursor.fetchall()

    return posts, comments

def fetch_posts(offset, limit, sort_by="newest"):
    order_by = {
        "newest": "created_utc DESC",
        "oldest": "created_utc ASC",
        "most_comments": "num_comments DESC",
        "most_upvotes": "score DESC"
    }.get(sort_by, "created_utc DESC")
    
    cursor.execute(f"""
        SELECT id, author, title, selftext, created_utc, num_comments, score, subreddit
        FROM submissions
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
    """, (limit, offset))
    return cursor.fetchall()

def fetch_comments_for_post(post_id, sort_by="most_upvotes"):
    order_by = {
        "most_upvotes": "score DESC",
        "newest": "created_utc DESC",
        "oldest": "created_utc ASC"
    }.get(sort_by, "score DESC")
    
    cursor.execute(f"""
        SELECT id, parent_id, body, author, created_utc, score
        FROM comments 
        WHERE link_id = ? 
        ORDER BY {order_by}
    """, (f't3_{post_id}',))
    return cursor.fetchall()

def display_comments(comments, search_terms=None):
    comment_dict = {}
    top_level_comments = []
    
    # First pass: create dictionary of all comments
    for comment in comments:
        comment_dict[comment[0]] = {
            'data': comment,
            'replies': [],
            'level': 0
        }
    
    # Second pass: build the hierarchy
    for comment in comments:
        parent_id = comment[1]
        if parent_id.startswith('t3_'):  # Top-level comment
            top_level_comments.append(comment[0])
        elif parent_id.startswith('t1_'):  # Reply to another comment
            parent_id = parent_id[3:]  # Remove 't1_' prefix
            if parent_id in comment_dict:
                comment_dict[parent_id]['replies'].append(comment[0])
                comment_dict[comment[0]]['level'] = comment_dict[parent_id]['level'] + 1
    
    # Function to recursively display comments
    def display_comment_tree(comment_id, level=0):
        comment = comment_dict[comment_id]['data']
        replies = comment_dict[comment_id]['replies']
        
        # Calculate indentation
        left_margin = min(level * 20, 200)  # Max indent of 200px
        
        # Format the comment text
        body = comment[2]
        if search_terms:
            body = highlight_search_terms(body, search_terms)
        
        st.markdown(
            f"""
            <div style='margin-left: {left_margin}px; padding: 8px; border-left: 2px solid #ccc;'>
                <strong><a href="/Profile_View?username={comment[3]}">u/{comment[3]}</a></strong> - 
                <i>Score: {comment[5]} | Posted on: {format_date(comment[4])}</i><br>
                <p>{body}</p>
            </div>
            """, unsafe_allow_html=True
        )
        
        # Display replies
        for reply_id in replies:
            display_comment_tree(reply_id, level + 1)
    
    # Display all top-level comments and their replies
    for comment_id in top_level_comments:
        display_comment_tree(comment_id)

def highlight_search_terms(text, search_terms):
    if not search_terms:
        return text
    
    # Escape special regex characters in search terms
    escaped_terms = [re.escape(term) for term in search_terms]
    
    # Sort terms by length (longest first) to handle overlapping matches
    escaped_terms.sort(key=len, reverse=True)
    
    # Create pattern that matches whole words, case insensitive
    pattern = '|'.join(f'({term})' for term in escaped_terms)
    
    def replacer(match):
        return f'<span style="color: red; text-decoration: underline;">{match.group(0)}</span>'
    
    # Use regex substitution with word boundaries
    result = re.sub(pattern, replacer, text, flags=re.IGNORECASE)
    return result

# Update the helper function to get the full post URL
def get_post_url(link_id, comment_id):
    # link_id is in format 't3_postid', we need to extract just the postid
    post_id = link_id.split('_')[1] if '_' in link_id else link_id
    # Create the URL with both post and comment IDs
    return f"/Post_View?post_id={post_id}&comment_id={comment_id}"

# Update the main title
st.title("RepLadies Reddit Archive")

posts_per_page = 20
page_num = st.session_state.get("page_num", 1)  # Get page_num from session state
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

# Single sort_by selection for both search and regular viewing
sort_by = st.sidebar.selectbox(
    "Sort posts by", 
    ["most_upvotes", "newest", "oldest", "most_comments"],
    format_func=lambda x: {
        "most_upvotes": "Most Upvotes",
        "newest": "Newest",
        "oldest": "Oldest",
        "most_comments": "Most Comments"
    }[x],
    index=0  # Set most_upvotes as default
)

# Comment sorting - always show
comment_sort = st.sidebar.selectbox(
    "Sort comments by", 
    ["most_upvotes", "newest", "oldest"],
    format_func=lambda x: {
        "most_upvotes": "Most Upvotes",
        "newest": "Newest",
        "oldest": "Oldest"
    }[x],
    index=0,  # Set most_upvotes as default
    key='comment_sort'  # Store in session state
)

# Add the date range picker to the sidebar (after search options)
if search_query:
    # Get the date bounds
    min_date, max_date = get_date_bounds()
    
    # Add date range filters to sidebar
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
    
    # Convert dates to datetime with time
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

# Search or fetch posts
if search_query:
    # Create search terms from the query for highlighting
    normalized_query = normalize_text(search_query)
    search_terms = normalized_query.split()
    
    # Get timestamps for date filtering
    start_timestamp = int(start_datetime.timestamp()) if 'start_datetime' in locals() else None
    end_timestamp = int(end_datetime.timestamp()) if 'end_datetime' in locals() else None
    
    # Fetch the posts and comments for the current page with date filtering
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
    
    # Calculate total results for search with date filter
    total_results = get_total_search_results(
        search_query, 
        search_type, 
        exact_match,
        start_timestamp,
        end_timestamp
    )
else:
    search_terms = []  # Empty list when not searching
    posts = fetch_posts(offset, posts_per_page, sort_by)
    comments = []
    # For normal posts (no search query), calculate total results based on all posts
    cursor.execute("SELECT COUNT(*) FROM submissions")
    total_results = cursor.fetchone()[0]

# Calculate the total number of pages based on results
total_pages = (total_results - 1) // posts_per_page + 1

# Ensure the current page doesn't exceed the total pages
page_num = min(page_num, total_pages)

# Handle case when there are no results
if total_results == 0:
    st.markdown("<h2 style='text-align: center; color: red; font-weight: bold;'>No results found</h2>", unsafe_allow_html=True)
else:
    # Display page info at the top
    st.write(f"Page {page_num} of {total_pages}")
    
    # Display posts and comments
    if search_query:
        # Always display posts first if we have them
        if posts:
            st.subheader("Posts:")
            for post in posts:
                # First escape HTML special characters
                title = post[0].replace("<", "&lt;").replace(">", "&gt;")
                selftext = post[1].replace("<", "&lt;").replace(">", "&gt;")
                
                if highlight_enabled:
                    title = highlight_search_terms(title, search_terms)
                    selftext = highlight_search_terms(selftext, search_terms)

                st.markdown(f"<h3>{title}</h3>", unsafe_allow_html=True)
                st.markdown(selftext, unsafe_allow_html=True)
                formatted_date = format_date(post[3])  # post[3] is created_utc
                st.write(f"Score: {post[5]} | Comments: {post[6]}")
                st.markdown(f'Posted by <a href="/Profile_View?username={post[2]}">u/{post[2]}</a> on {formatted_date} in r/{post[7]}', unsafe_allow_html=True)

                with st.expander("View Comments"):
                    post_comments = fetch_comments_for_post(post[4], comment_sort)
                    display_comments(post_comments, search_terms if highlight_enabled else None)
                st.markdown("---")

        # Then display loose comments if we have them
        if comments and search_type in ["comments", "everything"]:
            st.subheader("Search Results in Comments:")
            for comment in comments:
                body = comment[4]
                if highlight_enabled:
                    body = highlight_search_terms(body, search_terms)
                formatted_date = format_date(comment[5])
                
                # Check if we have a valid post ID from the link_id
                has_valid_post = False
                if comment[1]:  # link_id exists
                    post_id = comment[1].split('_')[1] if '_' in comment[1] else comment[1]
                    cursor.execute("SELECT id FROM submissions WHERE id = ?", (post_id,))
                    has_valid_post = cursor.fetchone() is not None

                st.markdown(
                    f"""<div style='padding: 8px; border-left: 2px solid #ccc;'>
                        <strong><a href="/Profile_View?username={comment[3]}">u/{comment[3]}</a></strong> - 
                        <i>Score: {comment[6]} | Posted on: {formatted_date} in r/{comment[7]}</i><br>
                        <p>{body}</p>
                        {f'<a href="{get_post_url(comment[1], comment[0])}" target="_blank">View Full Post and Comments</a>' if has_valid_post else ''}
                    </div>""", 
                    unsafe_allow_html=True
                )
                st.markdown("---")

        # Show error message for the end of the results
        if page_num == total_pages:
            st.markdown("<h2 style='text-align: center; color: red; font-weight: bold;'>You have reached the end of the results.</h2>", unsafe_allow_html=True)

    else:
        # Regular post display (no search)
        for post in posts:
            st.subheader(post[2])  # Post title
            st.write(post[3])      # Post selftext
            formatted_date = format_date(post[4])  # post[4] is created_utc
            st.write(f"Score: {post[6]} | Comments: {post[5]}")
            st.markdown(f'Posted by <a href="/Profile_View?username={post[1]}">u/{post[1]}</a> on {formatted_date} in r/{post[7]}', unsafe_allow_html=True)

            with st.expander("View Comments"):
                post_comments = fetch_comments_for_post(post[0], comment_sort)
                display_comments(post_comments, search_terms)
            st.markdown("---")

    # Pagination control in sidebar
    st.sidebar.write(f"Page {page_num} of {total_pages}")
    
    if page_num < total_pages:
        if st.sidebar.button("Next page"):
            st.session_state.page_num = page_num + 1
            st.experimental_rerun()  # Rerun the app to update the page

    if page_num > 1:
        if st.sidebar.button("Previous page"):
            st.session_state.page_num = page_num - 1
            st.experimental_rerun()  # Rerun the app to update the page