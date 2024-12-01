import streamlit as st
from datetime import datetime
import requests
from database import execute_query
from utils import format_date, DARK_THEME_CSS

# Set page config
st.set_page_config(
    page_title="Search View",
    page_icon="🔍",
    layout="wide"
)

st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

# API endpoint constants
API_BASE_URL = "https://m6njm571hh.execute-api.us-east-2.amazonaws.com"

# Search interface
st.title("Search RepLadies Archive")

# Main search input
search_query = st.text_input("Search terms", key="search_input")

# Sidebar controls
with st.sidebar:
    st.header("Search Options")
    
    search_method = st.radio(
        "Search Method",
        ["Standard", "Fast Search (Beta)"]
    )
    
    search_type = st.radio(
        "Search in:", 
        ["post_title", "post_body", "comments", "everything"]
    )
    
    sort_by = st.selectbox(
        "Sort by:",
        ["most_upvotes", "newest", "oldest"]
    )
    
    # Add date filters
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

# Search execution
if search_query:
    try:
        if search_method == "Fast Search (Beta)":
            if search_type in ["post_title", "post_body", "everything"]:
                with st.spinner("Searching posts..."):
                    results = search_api_posts(
                        query=search_query,
                        sort=sort_by,
                        search_type=search_type,
                        page=st.session_state.get('page', 1),
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    if results and results.get('results'):
                        st.header(f"Posts ({results['total_results']} total)")
                        
                        current_start = ((results['page'] - 1) * results['limit']) + 1
                        current_end = min(current_start + len(results['results']) - 1, results['total_results'])
                        st.caption(f"Showing results {current_start} - {current_end} of {results['total_results']}")
                        
                        for post in results['results']:
                            with st.container():
                                st.markdown(f"### {post['title']}")
                                st.markdown(
                                    f"Posted by u/{post['author']} | "
                                    f"Score: {post['score']} | "
                                    f"Comments: {post['num_comments']} | "
                                    f"Posted on: {post['formatted_date']}"
                                )
                                with st.expander("Show Content"):
                                    st.write(post['selftext'])
                                st.divider()
                    else:
                        st.info("No posts found matching your search.")

            # Add pagination
            if results and results.get('results'):
                col1, col2, col3 = st.columns([1, 2, 1])
                with col1:
                    if st.session_state.get('page', 1) > 1:
                        if st.button("← Previous"):
                            st.session_state.page = st.session_state.get('page', 1) - 1
                            st.rerun()
                with col2:
                    st.write(f"Page {st.session_state.get('page', 1)}")
                with col3:
                    if len(results['results']) == results['limit']:
                        if st.button("Next →"):
                            st.session_state.page = st.session_state.get('page', 1) + 1
                            st.rerun()
        else:
            # Your existing "Standard" search code here
            pass

    except Exception as e:
        st.error(f"Search error: {str(e)}")
else:
    st.info("Enter search terms above to begin") 
