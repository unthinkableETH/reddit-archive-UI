import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st
from datetime import datetime
import re
import os
import time

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

@st.cache_resource(show_spinner=False, ttl=3600)  # Cache for 1 hour
def get_database_connection():
    conn = psycopg2.connect(
        dbname=st.secrets["postgres"]["dbname"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"],
        host=st.secrets["postgres"]["host"],
        port=st.secrets["postgres"]["port"],
        connect_timeout=30,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
        application_name='repladies_streamlit_profile'
    )
    return conn

def clean_reddit_id(reddit_id, keep_prefix=False):
    """Standardize Reddit ID format"""
    if not reddit_id:
        return None
    if reddit_id.startswith(('t1_', 't3_')):
        return reddit_id if keep_prefix else reddit_id.split('_')[1]
    return reddit_id

def get_post_url(submission_id, comment_id):
    """Generate URL for viewing a post with optional highlighted comment"""
    post_id = clean_reddit_id(submission_id)
    return f"/Post_View?post_id={post_id}&comment_id={comment_id}"

def format_date(utc_timestamp):
    try:
        utc_timestamp = int(utc_timestamp)
        return datetime.utcfromtimestamp(utc_timestamp).strftime('%B %d, %Y %I:%M %p')
    except ValueError:
        return "Invalid Date"

def search_users(cursor, partial_name):
    cursor.execute("""
        SELECT DISTINCT author 
        FROM (
            SELECT author FROM submissions WHERE author ILIKE %s
            UNION
            SELECT author FROM comments WHERE author ILIKE %s
        ) as authors
        ORDER BY author
        LIMIT 10
    """, (f"%{partial_name}%", f"%{partial_name}%"))
    return [row['author'] for row in cursor.fetchall()]

def get_user_posts(cursor, username, sort_by="newest"):
    try:
        order_by = {
            "newest": "created_utc DESC",
            "oldest": "created_utc ASC",
            "most_comments": "num_comments DESC",
            "most_upvotes": "score DESC"
        }.get(sort_by, "created_utc DESC")
        
        cursor.execute(f"""
            SELECT title, selftext, created_utc, id, score, num_comments, subreddit, author
            FROM submissions 
            WHERE author = %s
            ORDER BY {order_by}
        """, (username,))
        return cursor.fetchall()
    except psycopg2.Error as e:
        st.error(f"Database error in get_user_posts: {e}")
        return []

def get_user_comments(cursor, username, sort_by="newest"):
    try:
        order_by = {
            "newest": "created_utc DESC",
            "oldest": "created_utc ASC",
            "most_upvotes": "score DESC"
        }.get(sort_by, "created_utc DESC")
        
        cursor.execute(f"""
            SELECT id, submission_id, parent_id, body, created_utc, score, subreddit, author
            FROM comments 
            WHERE author = %s
            ORDER BY {order_by}
        """, (username,))
        return cursor.fetchall()
    except psycopg2.Error as e:
        st.error(f"Database error in get_user_comments: {e}")
        return []

def display_comment(comment, formatted_date):
    st.markdown(
        f"""<div style='padding: 8px; border-left: 2px solid #ccc;'>
            <strong><a href="/Profile_View?username={comment['author']}">u/{comment['author']}</a></strong> - 
            <i>Score: {comment['score']} | Posted on: {formatted_date} in r/{comment['subreddit']}</i><br>
            <p>{comment['body']}</p>
        </div>""", 
        unsafe_allow_html=True
    )
    st.markdown("---")

try:
    conn = get_database_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        # Get username from URL parameters or search
        params = st.query_params
        username = params.get("username", "")

        # Search interface
        st.title("Profile View")
        search_query = st.text_input("Search for a user:", value=username)

        if search_query:
            matching_users = search_users(cursor, search_query)
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
                posts = get_user_posts(cursor, username, post_sort)
                if posts:
                    st.write(f"### Posts ({len(posts)})")
                    for post in posts:
                        st.markdown(f"#### {post['title']}")
                        st.write(post['selftext'])
                        formatted_date = format_date(post['created_utc'])
                        st.markdown(
                            f'Score: {post["score"]} | Comments: {post["num_comments"]} | Posted on {formatted_date} in r/{post["subreddit"]}',
                            unsafe_allow_html=True
                        )
                        
                        with st.expander("View Comments"):
                            cursor.execute("""
                                SELECT id, parent_id, body, author, created_utc, score, subreddit
                                FROM comments 
                                WHERE submission_id = %s 
                                ORDER BY score DESC
                            """, (f't3_{post["id"]}',))
                            comments = cursor.fetchall()
                            if comments:
                                for comment in comments:
                                    display_comment(comment, format_date(comment['created_utc']))
                        st.markdown("---")
                else:
                    st.info("No posts found")
            
            with comments_tab:
                comments = get_user_comments(cursor, username, comment_sort)
                if comments:
                    st.write(f"### Comments ({len(comments)})")
                    for comment in comments:
                        formatted_date = format_date(comment['created_utc'])
                        
                        # Check if we have a valid post ID
                        has_valid_post = False
                        if comment['submission_id']:
                            post_id = clean_reddit_id(comment['submission_id'])
                            cursor.execute("SELECT id FROM submissions WHERE id = %s", (post_id,))
                            has_valid_post = cursor.fetchone() is not None
                        
                        st.markdown(
                            f"""<div style='padding: 8px; border-left: 2px solid #ccc;'>
                                <i>Score: {comment['score']} | Posted on: {formatted_date} in r/{comment['subreddit']}</i><br>
                                <p>{comment['body']}</p>
                                {f'<a href="{get_post_url(comment["submission_id"], comment["id"])}" target="_blank">View Full Post and Comments</a>' if has_valid_post else ''}
                            </div>""",
                            unsafe_allow_html=True
                        )
                        st.markdown("---")
                else:
                    st.info("No comments found")
        else:
            st.info("Enter a username to view their profile")

except psycopg2.Error as e:
    st.error(f"Database error: {e}")
except Exception as e:
    st.error(f"An unexpected error occurred: {e}")

