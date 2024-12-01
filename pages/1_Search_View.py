import streamlit as st
import requests
from database import execute_query
from queries import SEARCH_POSTS, SEARCH_COMMENTS, SORT_ORDERS
from utils import format_date, DARK_THEME_CSS

st.set_page_config(
    page_title="Search RepLadies Archive",
    page_icon="👜",
    layout="wide"
)

st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

st.title("Search RepLadies Archive")

# Add API endpoint constants
API_BASE_URL = "https://m6njm571hh.execute-api.us-east-2.amazonaws.com"

def search_api_comments(query: str, sort: str, page: int = 1, limit: int = 20):
    """Search comments using the new API"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/search/comments",
            params={
                "query": query,
                "sort": sort,
                "page": page,
                "limit": limit
            },
            timeout=15  # Increased from 10 to 15 seconds
        )
        
        if response.status_code != 200:
            st.error(f"API Error ({response.status_code}): {response.text}")
            return None
            
        return response.json()
        
    except requests.Timeout:
        st.error("Search took too long. Please try a more specific search term.")
        return None
    except requests.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None

# Sidebar controls
with st.sidebar:
    st.header("Search Options")
    
    search_method = st.radio(
        "Search Method",
        ["Standard", "Fast Search (Beta)"],
        help="Fast Search uses an optimized API but only searches comments"
    )
    
    if search_method == "Standard":
        search_type = st.radio(
            "Search in:", 
            ["post_title", "post_body", "comments", "everything"],
            format_func=lambda x: {
                "post_title": "Post Titles",
                "post_body": "Post Body Text",
                "comments": "Comments Only",
                "everything": "Everything ℹ️"
            }[x]
        )
    
    exact_match = st.toggle("Exact match", value=False)
    highlight_enabled = st.toggle("Highlight search terms", value=True)
    
    sort_by = st.selectbox(
        "Sort results by", 
        ["most_upvotes", "newest", "oldest", "most_comments"],
        format_func=lambda x: {
            "most_upvotes": "Most Upvotes",
            "newest": "Newest",
            "oldest": "Oldest",
            "most_comments": "Most Comments"
        }[x]
    )
    
    # Date range picker
    st.subheader("Date Range")
    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")

# Main search interface
search_query = st.text_input("Enter your search terms", key="search_box")

if search_query:
    try:
        if search_method == "Fast Search (Beta)":
            with st.spinner("Searching comments..."):
                results = search_api_comments(
                    query=search_query,
                    sort=sort_by,
                    page=st.session_state.get('page', 1)
                )
                
                if results and results.get('results'):
                    st.header(f"Comments ({results['total_results']} total)")
                    
                    # Progress through results
                    current_start = ((results['page'] - 1) * results['limit']) + 1
                    current_end = min(current_start + len(results['results']) - 1, results['total_results'])
                    st.caption(f"Showing results {current_start} - {current_end} of {results['total_results']}")
                    
                    for comment in results['results']:
                        with st.container():
                            st.markdown(
                                f"""
                                <div style='padding: 8px; border-left: 2px solid #ccc;'>
                                    <strong>u/{comment['author']}</strong><br>
                                    <i>Score: {comment['score']} | Posted on: {comment['formatted_date']}</i>
                                    <p>{comment['body']}</p>
                                    <a href="/Post_View?post_id={comment['submission_id']}&comment_id={comment['id']}">
                                        View Full Discussion
                                    </a>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                            st.divider()
                    
                    # Enhanced pagination
                    pages_section = st.container()
                    with pages_section:
                        cols = st.columns([1, 2, 1])
                        with cols[0]:
                            if results['page'] > 1:
                                if st.button("← Previous"):
                                    st.session_state.page = results['page'] - 1
                                    st.rerun()
                        with cols[1]:
                            st.write(f"Page {results['page']} of {results['total_pages']}")
                        with cols[2]:
                            if results['page'] < results['total_pages']:
                                if st.button("Next →"):
                                    st.session_state.page = results['page'] + 1
                                    st.rerun()
                else:
                    st.info("No results found")
                    
        else:
            # Build date filter if dates are selected
            date_filter = ""
            params = [search_query]  # First param is always the search query
            
            if start_date:
                date_filter += " AND created_utc >= %s"
                params.append(int(start_date.timestamp()))
            if end_date:
                date_filter += " AND created_utc <= %s"
                params.append(int(end_date.timestamp()))
            
            # Add pagination parameters
            posts_per_page = 20
            page = st.session_state.get('page', 1)
            params.extend([posts_per_page, (page - 1) * posts_per_page])
            
            # Execute search based on type
            if search_type in ["post_title", "post_body", "everything"]:
                posts = execute_query(
                    SEARCH_POSTS.format(
                        sort_order=SORT_ORDERS[sort_by],
                        date_filter=date_filter
                    ),
                    tuple(params)
                )
                
                if posts:
                    st.header("Posts")
                    for post in posts:
                        with st.container():
                            st.markdown(f"### {post['title']}")
                            st.markdown(
                                f"Posted by u/{post['author']} | "
                                f"Score: {post['score']} | "
                                f"Comments: {post['num_comments']} | "
                                f"Posted on: {format_date(post['created_utc'])}"
                            )
                            with st.expander("Show Content"):
                                st.write(post['selftext'])
                            st.divider()
            
            if search_type in ["comments", "everything"]:
                comments = execute_query(
                    SEARCH_COMMENTS.format(
                        sort_order=SORT_ORDERS[sort_by],
                        date_filter=date_filter
                    ),
                    tuple(params)
                )
                
                if comments:
                    st.header("Comments")
                    for comment in comments:
                        with st.container():
                            st.markdown(
                                f"""
                                <div style='padding: 8px; border-left: 2px solid #ccc;'>
                                    <strong>u/{comment['author']}</strong><br>
                                    <i>Score: {comment['score']} | Posted on: {format_date(comment['created_utc'])}</i>
                                    <p>{comment['body']}</p>
                                    <a href="/Post_View?post_id={comment['submission_id']}&comment_id={comment['id']}">
                                        View Full Discussion
                                    </a>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                            st.divider()
            
            # Pagination controls
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if page > 1:
                    if st.button("← Previous"):
                        st.session_state.page = page - 1
                        st.rerun()
            with col2:
                st.write(f"Page {page}")
            with col3:
                if len(posts) == posts_per_page or len(comments) == posts_per_page:
                    if st.button("Next →"):
                        st.session_state.page = page + 1
                        st.rerun()
                    
    except Exception as e:
        st.error(f"Search error: {str(e)}")
else:
    st.info("Enter search terms above to begin") 
