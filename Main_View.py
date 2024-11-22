import streamlit as st
from database import execute_query
from queries import GET_POSTS, SORT_ORDERS
from utils import format_date, DARK_THEME_CSS

def debug_table_structure():
    query = """
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'comments';
    """
    columns = execute_query(query)
    st.write("Debug - Comments table columns:", columns)

st.set_page_config(
    page_title="RepLadies Archive",
    page_icon="👜",
    layout="wide"
)

st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

st.title("RepLadies Reddit Archive")

debug_table_structure()

# Navigation using containers
col1, col2, col3 = st.columns(3)

with col1:
    with st.container():
        st.markdown("### 🔍 Search Archive")
        st.write("Search through posts and comments")
        st.link_button("Go to Search", "/Search_View")

with col2:
    with st.container():
        st.markdown("### 👤 User Profiles")
        st.write("View user activity and history")
        st.link_button("Go to Profiles", "/Profile_View")

with col3:
    with st.container():
        st.markdown("### 📊 Statistics")
        st.write("View archive statistics")
        st.link_button("Go to Stats", "/Stats_View")

# Popular posts section
st.header("Popular Posts")

try:
    posts = execute_query(GET_POSTS.format(
        sort_order=SORT_ORDERS["most_upvotes"]
    ), (10, 0))  # Limit 10, offset 0
    
    for post in posts:
        with st.container():
            col1, col2 = st.columns([4, 1])
            
            with col1:
                st.markdown(f"### {post['title']}")
                st.markdown(
                    f"Posted by u/{post['author']} in r/{post['subreddit']} | "
                    f"Score: {post['score']} | "
                    f"Comments: {post['num_comments']} | "
                    f"Posted on: {format_date(post['created_utc'])}"
                )
            
            with col2:
                st.link_button("View Discussion", f"/Post_View?post_id={post['id']}")
            
            with st.expander("Show Content"):
                st.write(post['selftext'])
            
            st.divider()
            
except Exception as e:
    st.error(f"Error loading popular posts: {str(e)}")
