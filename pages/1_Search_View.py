import streamlit as st
import requests
from utils import format_date, DARK_THEME_CSS
from datetime import datetime

st.set_page_config(
    page_title="Search RepLadies Archive",
    page_icon="👜",
    layout="wide"
)

st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

st.title("Search RepLadies Archive")

# API endpoint constants
API_BASE_URL = "https://m6njm571hh.execute-api.us-east-2.amazonaws.com"

def search_api_posts(query: str, sort: str, search_type: str = "title_body", page: int = 1, limit: int = 20, start_date=None, end_date=None):
    """Search posts using the API"""
    try:
        params = {
            "query": query,
            "sort": sort,
            "search_type": search_type,
            "page": page,
            "limit": limit
        }
        
        # Add date parameters if provided
        if start_date:
            params["start_date"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["end_date"] = end_date.strftime("%Y-%m-%d")
            
        response = requests.get(
            f"{API_BASE_URL}/api/search/posts",
            params=params,
            timeout=15
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

def search_api_comments(query: str, sort: str, page: int = 1, limit: int = 20):
    """Search comments using the API"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/search/comments",
            params={
                "query": query,
                "sort": sort,
                "page": page,
                "limit": limit
            },
            timeout=15
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
        ["Fast Search (Beta)"],
        help="Optimized search using our API"
    )
    
    search_type = st.radio(
        "Search in:", 
        ["post_title", "post_body", "comments", "everything"],
        format_func=lambda x: {
            "post_title": "Post Titles Only",
            "post_body": "Post Content Only",
            "comments": "Comments Only",
            "everything": "Everything (Posts + Comments)"
        }[x]
    )
    
    # Only show most_comments option for post searches
    available_sort_options = (
        ["most_upvotes", "newest", "oldest", "most_comments"]
        if search_type in ["post_title", "post_body", "everything"]
        else ["most_upvotes", "newest", "oldest"]
    )
    
    sort_by = st.selectbox(
        "Sort by:",
        available_sort_options,
        format_func=lambda x: {
            "most_upvotes": "Most Upvotes",
            "newest": "Newest First",
            "oldest": "Oldest First",
            "most_comments": "Most Comments"
        }[x]
    )
    
    # Date range picker
    st.subheader("Date Range")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "From",
            value=None,
            min_value=datetime(2015, 1, 1).date(),
            max_value=datetime.now().date()
        )
    with col2:
        end_date = st.date_input(
            "To",
            value=None,
            min_value=datetime(2015, 1, 1).date(),
            max_value=datetime.now().date()
        )

# Main search interface
search_query = st.text_input("Enter your search terms", key="search_box")

if search_query:
    try:
        post_results = None
        comment_results = None
        
        # Handle post searches
        if search_type in ["post_title", "post_body", "everything"]:
            api_search_type = {
                "post_title": "title",
                "post_body": "body",
                "everything": "title_body"
            }[search_type]
            
            with st.spinner("Searching posts..."):
                post_results = search_api_posts(
                    query=search_query,
                    sort=sort_by,
                    search_type=api_search_type,
                    page=st.session_state.get('page', 1),
                    start_date=start_date,
                    end_date=end_date
                )
                
                if post_results and post_results.get('results'):
                    st.header(f"Posts ({post_results['total_results']} total)")
                    st.caption(f"Sorted by: {sort_by}")
                    
                    current_start = ((post_results['page'] - 1) * post_results['limit']) + 1
                    current_end = min(current_start + len(post_results['results']) - 1, post_results['total_results'])
                    st.caption(f"Showing results {current_start} - {current_end} of {post_results['total_results']}")
                    
                    for post in post_results['results']:
                        with st.container():
                            st.markdown(f"### {post['title']}")
                            st.markdown(
                                f"Posted by u/{post['author']} | "
                                f"Score: {post.get('score', 'N/A')} | "  # Handle possible NULL values
                                f"Comments: {post.get('num_comments', 'N/A')} | "  # Handle possible NULL values
                                f"Posted on: {post['formatted_date']}"
                            )
                            with st.expander("Show Content"):
                                st.write(post['selftext'])
                            st.divider()
                else:
                    st.info("No posts found matching your search.")

        # Handle comment searches
        if search_type in ["comments", "everything"]:
            with st.spinner("Searching comments..."):
                comment_results = search_api_comments(
                    query=search_query,
                    sort=sort_by,
                    page=st.session_state.get('page', 1)
                )
                
                if comment_results and comment_results.get('results'):
                    st.header(f"Comments ({comment_results['total_results']} total)")
                    
                    current_start = ((comment_results['page'] - 1) * comment_results['limit']) + 1
                    current_end = min(current_start + len(comment_results['results']) - 1, comment_results['total_results'])
                    st.caption(f"Showing results {current_start} - {current_end} of {comment_results['total_results']}")
                    
                    for comment in comment_results['results']:
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
                else:
                    st.info("No comments found matching your search.")

        # Pagination controls
        if (post_results and post_results.get('results')) or (comment_results and comment_results.get('results')):
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.session_state.get('page', 1) > 1:
                    if st.button("← Previous"):
                        st.session_state.page = st.session_state.get('page', 1) - 1
                        st.rerun()
            with col2:
                st.write(f"Page {st.session_state.get('page', 1)}")
            with col3:
                if ((post_results and len(post_results['results']) == post_results['limit']) or 
                    (comment_results and len(comment_results['results']) == comment_results['limit'])):
                    if st.button("Next →"):
                        st.session_state.page = st.session_state.get('page', 1) + 1
                        st.rerun()

    except Exception as e:
        st.error(f"Search error: {str(e)}")
else:
    st.info("Enter search terms above to begin") 
