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
    page_title="Post View",
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
        
        /* All links */
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

# Reuse your database connection and helper functions
@st.cache_resource
def get_database_connection():
    db_path = 'reddit_data.db'
    if not os.path.exists(db_path):
        with st.spinner("First time setup: Downloading database... This may take a few minutes..."):
            download_from_s3(db_path)
    
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

def download_from_s3(db_path):
    s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
    try:
        s3.download_file('repladies-archive', 'reddit_data.db', db_path)
    except Exception as e:
        st.error(f"Error downloading database: {e}")
        raise e

def format_date(utc_timestamp):
    try:
        utc_timestamp = int(utc_timestamp)
        return datetime.utcfromtimestamp(utc_timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return "Invalid Date"

# Get post and comment IDs from URL parameters
params = st.query_params
post_id = params.get("post_id")
highlight_comment_id = params.get("comment_id")

if not post_id:
    st.title("Post View")
    st.error("No post ID provided in the URL.")
    st.markdown("""
    ### How to Access Post View
    This page shows detailed views of posts and their comments. To view a post:

    1. Go to the [main page](/)
    2. Search for comments using the search box
    3. Click "View Full Post and Comments" on any comment in the search results
    """)
    st.stop()

# Sidebar controls
st.sidebar.header("Post View")
st.sidebar.subheader("Comment Controls")
comment_sort = st.sidebar.selectbox(
    "Sort comments by",
    ["most_upvotes", "newest", "oldest"],
    format_func=lambda x: {
        "most_upvotes": "Most Upvotes",
        "newest": "Newest",
        "oldest": "Oldest"
    }[x],
    index=0
)

bring_to_top = st.sidebar.toggle("Bring highlighted comment to top", value=True)
highlight_comment = st.sidebar.toggle("Highlight search result comment", value=True)

# Fetch post and comments
conn = get_database_connection()
cursor = conn.cursor()

def fetch_post(post_id):
    cursor.execute("""
        SELECT title, selftext, author, created_utc, id, score, num_comments, subreddit
        FROM submissions 
        WHERE id = ?
    """, (post_id,))
    return cursor.fetchone()

def fetch_comments_with_hierarchy(post_id, sort_order="most_upvotes"):
    order_clause = {
        "most_upvotes": "score DESC",
        "newest": "created_utc DESC",
        "oldest": "created_utc ASC"
    }.get(sort_order, "score DESC")

    try:
        cursor.execute(f"""
            SELECT id, link_id, parent_id, author, body, created_utc, score, subreddit 
            FROM comments 
            WHERE link_id = ? 
            ORDER BY {order_clause}
        """, (f't3_{post_id}',))
        comments = cursor.fetchall()

        comment_dict = {comment[0]: comment for comment in comments}
        nested_comments = []

        def add_nested_comments(comment, level=0):
            nested_comments.append((comment, level))
            for reply_id, reply in comment_dict.items():
                if reply[2] == f't1_{comment[0]}':
                    add_nested_comments(reply, level + 1)

        for comment in comments:
            if comment[2] == f't3_{post_id}':
                add_nested_comments(comment)

        return nested_comments
    except sqlite3.DatabaseError as e:
        st.error(f"Error fetching comments for post {post_id}: {e}")
        return []

# Display post and comments
post = fetch_post(post_id)
if post:
    # Display post details
    st.title(post[0])  # Title
    st.write(post[1])  # Selftext
    formatted_date = format_date(post[3])
    st.write(f"Score: {post[5]} | Comments: {post[6]} | Posted on: {formatted_date}")
    st.markdown(f'Posted by <a href="/Profile_View?username={post[2]}">u/{post[2]}</a> in r/{post[7]}', unsafe_allow_html=True)
    st.markdown("---")

    # Fetch and display comments
    nested_comments = fetch_comments_with_hierarchy(post_id, sort_order=comment_sort)
    
    # After displaying the highlighted chain, keep track of displayed comments
    displayed_comment_ids = set()

    if highlight_comment_id and highlight_comment and bring_to_top:
        # Create a lookup dictionary for quick access
        comment_lookup = {comment[0]: (comment, level) for comment, level in nested_comments}
        
        # Get the highlighted comment
        highlighted_comment = comment_lookup.get(highlight_comment_id)
        if highlighted_comment:
            highlighted_chain = []
            seen_comments = set()
            
            # Get the direct parent chain
            current_comment = highlighted_comment
            while current_comment:
                comment, level = current_comment
                
                # Add to chain if not already seen
                if comment[0] not in seen_comments:
                    highlighted_chain.insert(0, (comment, level))
                    seen_comments.add(comment[0])
                
                # Get parent ID
                parent_id = comment[2].replace('t1_', '') if comment[2].startswith('t1_') else None
                
                # Stop if we reach the top-level comment (parent is the post)
                if comment[2].startswith('t3_'):
                    break
                    
                # Get parent comment
                current_comment = comment_lookup.get(parent_id)
                if not current_comment:
                    break

            # Get all children and sub-children of the highlighted comment
            def get_all_children(comment_id, base_level):
                children = []
                for comment, level in nested_comments:
                    if comment[2] == f't1_{comment_id}' and comment[0] not in seen_comments:
                        children.append((comment, level))
                        seen_comments.add(comment[0])
                        # Recursively get all sub-children
                        children.extend(get_all_children(comment[0], level + 1))
                return children

            # Add all children of the highlighted comment
            children = get_all_children(highlight_comment_id, highlighted_comment[1] + 1)
            highlighted_chain.extend(children)

            # Display the highlighted chain
            if highlighted_chain:
                st.markdown("### Highlighted Comment Thread:")
                for comment, level in highlighted_chain:
                    left_margin = min(level * 20, 200)
                    style = f"margin-left: {left_margin}px; padding: 8px; border-left: 2px solid #ccc;"
                    
                    # Only highlight the specific comment that was searched for
                    is_highlighted = comment[0] == highlight_comment_id
                    
                    if is_highlighted:
                        # Replace newlines with <br> tags and wrap the entire text in the styled paragraph
                        formatted_body = comment[4].replace('\n', '<br>')
                        st.markdown(
                            f"""
                            <div style='{style}'>
                                <strong>Level {level} - <a href="/Profile_View?username={comment[3]}">u/{comment[3]}</a></strong> - 
                                <i>Score: {comment[6]} | Posted on: {format_date(comment[5])}</i><br>
                                <p style="color: red; text-decoration: underline;">{formatted_body}</p>
                            </div>
                            """, unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f"""
                            <div style='{style}'>
                                <strong>Level {level} - <a href="/Profile_View?username={comment[3]}">u/{comment[3]}</a></strong> - 
                                <i>Score: {comment[6]} | Posted on: {format_date(comment[5])}</i><br>
                                <p>{comment[4]}</p>
                            </div>
                            """, unsafe_allow_html=True
                        )
                    st.markdown("---")
            
            st.markdown("### All Comments:")

        # Use seen_comments set to skip duplicates in main comment display
        displayed_comment_ids = seen_comments

    # Display all comments
    st.markdown("### All Comments:")
    for comment, level in nested_comments:
        # Calculate indentation based on comment level
        left_margin = min(level * 20, 200)
        
        # Check if this is the highlighted comment
        is_highlighted = comment[0] == highlight_comment_id and highlight_comment
        
        # Build the style string
        style = f"margin-left: {left_margin}px; padding: 8px; border-left: 2px solid #ccc;"
        
        # Apply highlighting to the entire comment div if it's the highlighted comment
        if is_highlighted:
            # Replace newlines with <br> tags and wrap the entire text in the styled paragraph
            formatted_body = comment[4].replace('\n', '<br>')
            st.markdown(
                f"""
                <div style='{style}'>
                    <strong>Level {level} - <a href="/Profile_View?username={comment[3]}">u/{comment[3]}</a></strong> - 
                    <i>Score: {comment[6]} | Posted on: {format_date(comment[5])}</i><br>
                    <p style="color: red; text-decoration: underline;">{formatted_body}</p>
                </div>
                """, unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"""
                <div style='{style}'>
                    <strong>Level {level} - <a href="/Profile_View?username={comment[3]}">u/{comment[3]}</a></strong> - 
                    <i>Score: {comment[6]} | Posted on: {format_date(comment[5])}</i><br>
                    <p>{comment[4]}</p>
                </div>
                """, unsafe_allow_html=True
            )
        st.markdown("---")

else:
    st.error("Post not found")