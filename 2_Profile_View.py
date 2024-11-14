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
    page_title="Profile View",
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

def search_users(partial_name):
    # Search for users in both submissions and comments
    cursor.execute("""
        SELECT DISTINCT author 
        FROM (
            SELECT author FROM submissions WHERE author LIKE ?
            UNION
            SELECT author FROM comments WHERE author LIKE ?
        )
        ORDER BY author
        LIMIT 10
    """, (f"%{partial_name}%", f"%{partial_name}%"))
    return [row[0] for row in cursor.fetchall()]

def get_user_posts(username, sort_by="newest"):
    order_by = {
        "newest": "created_utc DESC",
        "oldest": "created_utc ASC",
        "most_comments": "num_comments DESC",
        "most_upvotes": "score DESC"
    }.get(sort_by, "created_utc DESC")
    
    cursor.execute(f"""
        SELECT title, selftext, created_utc, id, score, num_comments, subreddit
        FROM submissions 
        WHERE author = ?
        ORDER BY {order_by}
    """, (username,))
    return cursor.fetchall()

def get_user_comments(username, sort_by="newest"):
    order_by = {
        "newest": "created_utc DESC",
        "oldest": "created_utc ASC",
        "most_upvotes": "score DESC"
    }.get(sort_by, "created_utc DESC")
    
    cursor.execute(f"""
        SELECT id, link_id, parent_id, body, created_utc, score, subreddit
        FROM comments 
        WHERE author = ?
        ORDER BY {order_by}
    """, (username,))
    return cursor.fetchall()

def get_post_url(link_id, comment_id):
    post_id = link_id.split('_')[1] if '_' in link_id else link_id
    return f"/Post_View?post_id={post_id}&comment_id={comment_id}"

# Fetch post and comments
conn = get_database_connection()
cursor = conn.cursor()

# Get username from URL parameters or search
params = st.query_params
username = params.get("username", "")

# Search interface
st.title("Profile View")
search_query = st.text_input("Search for a user:", value=username)

if search_query:
    matching_users = search_users(search_query)
    if matching_users:
        if len(matching_users) == 1:
            username = matching_users[0]
        else:
            username = st.selectbox("Select a user:", matching_users)

if username:
    st.write(f"## u/{username}'s Profile")
    
    # Sorting controls
    col1, col2 = st.columns(2)
    with col1:
        post_sort = st.selectbox(
            "Sort posts by",
            ["newest", "oldest", "most_upvotes", "most_comments"],
            format_func=lambda x: {
                "newest": "Newest",
                "oldest": "Oldest",
                "most_upvotes": "Most Upvotes",
                "most_comments": "Most Comments"
            }[x]
        )
    with col2:
        comment_sort = st.selectbox(
            "Sort comments by",
            ["newest", "oldest", "most_upvotes"],
            format_func=lambda x: {
                "newest": "Newest",
                "oldest": "Oldest",
                "most_upvotes": "Most Upvotes"
            }[x]
        )

    # Create tabs for posts and comments
    posts_tab, comments_tab = st.tabs(["Posts", "Comments"])
    
    with posts_tab:
        posts = get_user_posts(username, post_sort)
        if posts:
            st.write(f"### Posts ({len(posts)})")
            for post in posts:
                st.markdown(f"#### {post[0]}")  # Title
                st.write(post[1])  # Selftext
                formatted_date = format_date(post[2])
                st.write(f"Score: {post[4]} | Comments: {post[5]} | Posted on: {formatted_date} in r/{post[6]}")
                
                with st.expander("View Comments"):
                    cursor.execute("""
                        SELECT id, parent_id, body, author, created_utc, score
                        FROM comments 
                        WHERE link_id = ? 
                        ORDER BY score DESC
                    """, (f't3_{post[3]}',))
                    comments = cursor.fetchall()
                    if comments:
                        for comment in comments:
                            st.markdown(
                                f"""
                                <div style='padding: 8px; border-left: 2px solid #ccc;'>
                                    <strong><a href="/Profile_View?username={comment[3]}">{comment[3]}</a></strong> - 
                                    <i>Score: {comment[5]} | Posted on: {format_date(comment[4])}</i><br>
                                    <p>{comment[2]}</p>
                                </div>
                                """, 
                                unsafe_allow_html=True
                            )
                st.markdown("---")
        else:
            st.info("No posts found")
    
    with comments_tab:
        comments = get_user_comments(username, comment_sort)
        if comments:
            st.write(f"### Comments ({len(comments)})")
            for comment in comments:
                formatted_date = format_date(comment[4])
                
                # Check if we have a valid post ID
                has_valid_post = False
                if comment[1]:  # link_id exists
                    post_id = comment[1].split('_')[1] if '_' in comment[1] else comment[1]
                    cursor.execute("SELECT id FROM submissions WHERE id = ?", (post_id,))
                    has_valid_post = cursor.fetchone() is not None
                
                st.markdown(
                    f"""
                    <div style='padding: 8px; border-left: 2px solid #ccc;'>
                        <i>Score: {comment[5]} | Posted on: {formatted_date} in r/{comment[6]}</i><br>
                        <p>{comment[3]}</p>
                        {f'<a href="{get_post_url(comment[1], comment[0])}" target="_blank">View Full Post and Comments</a>' if has_valid_post else ''}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                st.markdown("---")
        else:
            st.info("No comments found")
else:
    st.info("Enter a username to view their profile") 