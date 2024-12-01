# In your sidebar
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

# Update your search function
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

# Update your search call
if search_query:
    if search_method == "Fast Search (Beta)":
        if search_type in ["post_title", "post_body", "everything"]:
            results = search_api_posts(
                query=search_query,
                sort=sort_by,
                search_type=search_type,
                page=st.session_state.get('page', 1),
                start_date=start_date,
                end_date=end_date
            )
            # Rest of your display code...
