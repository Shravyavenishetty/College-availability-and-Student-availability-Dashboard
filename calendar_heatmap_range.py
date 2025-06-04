import pandas as pd
import streamlit as st
import calendar
import numpy as np
from datetime import datetime, date
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from dotenv import load_dotenv
import os
import plotly.express as px
import plotly.graph_objects as go

# Load environment variables from .env file
load_dotenv()

# Fetch Appwrite configuration from environment variables
APPWRITE_ENDPOINT = os.getenv("APPWRITE_ENDPOINT")
APPWRITE_PROJECT_ID = os.getenv("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.getenv("APPWRITE_API_KEY")
APPWRITE_DATABASE_ID = os.getenv("APPWRITE_DATABASE_ID")
APPWRITE_COLLECTION_ID = os.getenv("APPWRITE_COLLECTION_ID")

# Fetch admin credentials from environment variables
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Validate that all required environment variables are set
required_env_vars = [
    "APPWRITE_ENDPOINT",
    "APPWRITE_PROJECT_ID",
    "APPWRITE_API_KEY",
    "APPWRITE_DATABASE_ID",
    "APPWRITE_COLLECTION_ID",
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD"
]
missing_vars = [var for var in required_env_vars if globals()[var] is None]
if missing_vars:
    st.error(f"The following environment variables are missing in your .env file: {', '.join(missing_vars)}. Please add them to your .env file and restart the app.")
    st.stop()

# Set page config
st.set_page_config(layout="wide", page_title="Exam Schedule Dashboard")

# Initialize session state for admin authentication and date range
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

if "date_range" not in st.session_state:
    st.session_state["date_range"] = {
        "start_date": pd.Timestamp(date(2025, 5, 19)),
        "end_date": pd.Timestamp(date(2025, 5, 19))
    }

# Initialize session state for editing an institute
if "editing_institute_id" not in st.session_state:
    st.session_state.editing_institute_id = None

# Sidebar for mode selection
st.sidebar.title("Navigation")
mode = st.sidebar.selectbox("Select Mode", ["User", "Admin"])

# Initialize Appwrite client
client = Client()
client.set_endpoint(APPWRITE_ENDPOINT)
client.set_project(APPWRITE_PROJECT_ID)
client.set_key(APPWRITE_API_KEY)
databases = Databases(client)

# Fetch all documents from Appwrite
def fetch_all_documents():
    limit = 100
    offset = 0
    all_documents = []
    while True:
        documents = databases.list_documents(
            APPWRITE_DATABASE_ID,
            APPWRITE_COLLECTION_ID,
            queries=[Query.limit(limit), Query.offset(offset)]
        ).get("documents", [])
        all_documents.extend(documents)
        if len(documents) < limit:
            break
        offset += limit
    return all_documents

documents = fetch_all_documents()
if not documents:
    st.error("No data found in the Appwrite database. Please ensure the 'exam_schedules' collection contains data and that your database and collection IDs are correct.")
    st.stop()

# Convert Appwrite data to a pandas DataFrame
data = []
for doc in documents:
    row = {
        "document_id": doc.get("$id"),
        "institute_name": doc.get("institute_name", ""),
        "institute_code": doc.get("institute_code", ""),
        "total_students": doc.get("total_students", 0),
        "exam_start": doc.get("exam_start", None),      # I year
        "exams_end": doc.get("exams_end", None),       # I year
        "exam_start_1": doc.get("exam_start_1", None), # II year
        "exam_end": doc.get("exam_end", None),         # II year
        "exam_start_2": doc.get("exam_start_2", None), # III year
        "exam_end_1": doc.get("exam_end_1", None),     # III year
        "exam_start_3": doc.get("exam_start_3", None), # IV year
        "exam_end_2": doc.get("exam_end_2", None),     # IV year
    }
    data.append(row)

df = pd.DataFrame(data)

# Clean the data
df.columns = df.columns.str.strip().str.lower().str.replace(r'\s+', '_', regex=True)

# Define exam date column pairs and map them to academic years
exam_pairs = [
    ("exam_start", "exams_end"),      # I year
    ("exam_start_1", "exam_end"),     # II year
    ("exam_start_2", "exam_end_1"),   # III year
    ("exam_start_3", "exam_end_2"),   # IV year
]
academic_years = ["I year", "II year", "III year", "IV year"]
exam_pairs_to_years = dict(zip(exam_pairs, academic_years))

# Verify that the exam date columns exist in the DataFrame
missing_columns = []
for start_col, end_col in exam_pairs:
    if start_col not in df.columns:
        missing_columns.append(start_col)
    if end_col not in df.columns:
        missing_columns.append(end_col)
if missing_columns:
    st.error(f"The following required columns are missing from the dataset: {', '.join(missing_columns)}. Actual columns found: {', '.join(df.columns)}")
    st.stop()

# Normalize institute names and codes
institute_name_column = "institute_name"
institute_code_column = "institute_code"
df[institute_name_column] = df[institute_name_column].astype(str).str.strip().str.lower()
df[institute_code_column] = df[institute_code_column].astype(str).str.strip()

# Function to normalize date strings to DD-MM-YYYY format
def normalize_date_string(date_str):
    if pd.isna(date_str) or date_str is None or (isinstance(date_str, str) and date_str.strip() == ""):
        return None
    
    date_str = str(date_str).strip()
    formats_to_try = [
        "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d",
        "%d.%m.%Y", "%d %b %Y", "%d %B %Y",
    ]
    
    for fmt in formats_to_try:
        try:
            dt = pd.to_datetime(date_str, format=fmt, errors='raise', dayfirst=True)
            if dt.year < 100:
                dt = dt.replace(year=dt.year + 2000)
            if not (2000 <= dt.year <= 2099):
                continue
            return dt.strftime("%d-%m-%Y")
        except (ValueError, TypeError):
            continue
    
    try:
        dt = pd.to_datetime(date_str, errors='raise', dayfirst=True)
        if not (2000 <= dt.year <= 2099):
            return None
        return dt.strftime("%d-%m-%Y")
    except (ValueError, TypeError):
        if date_str != "None":
            st.warning(f"Could not parse date: {date_str}")
        return None

# Convert exam date columns to string and normalize
for start_col, end_col in exam_pairs:
    if start_col in df.columns and end_col in df.columns:
        df[start_col] = df[start_col].astype(str)
        df[end_col] = df[end_col].astype(str)
        df[start_col] = df[start_col].apply(normalize_date_string)
        df[end_col] = df[end_col].apply(normalize_date_string)

# Ensure total_students is numeric
df['total_students'] = pd.to_numeric(df['total_students'], errors='coerce').fillna(0).astype(int)

# Compute exam_periods, all_exam_dates, and unavailable_students_per_date globally
exam_periods = []
all_exam_dates = []
unavailable_students_per_date = {}
for idx, row in df.iterrows():
    students = row['total_students']
    for (start_col, end_col), academic_year in exam_pairs_to_years.items():
        if start_col in df.columns and end_col in df.columns:
            start_str = row[start_col]
            end_str = row[end_col]
            if start_str and end_str:
                start = pd.to_datetime(start_str, format="%d-%m-%Y", errors="coerce", dayfirst=True)
                end = pd.to_datetime(end_str, format="%d-%m-%Y", errors="coerce", dayfirst=True)
                if pd.notnull(start) and pd.notnull(end) and start <= end:
                    start = start.normalize()
                    end = end.normalize()
                    exam_range = pd.date_range(start=start, end=end, freq='D')
                    all_exam_dates.extend(exam_range)
                    exam_periods.append({
                        'institute_name': row[institute_name_column],
                        'academic_year': academic_year,
                        'start_date': start,
                        'end_date': end,
                        'duration': (end - start).days + 1,
                        'students': students
                    })
                    for exam_date in exam_range:
                        date_key = exam_date.date()
                        if date_key in unavailable_students_per_date:
                            unavailable_students_per_date[date_key] += students
                        else:
                            unavailable_students_per_date[date_key] = students

# User Dashboard (publicly accessible)
if mode == "User":
    st.markdown("<h1 style='text-align: center; color: #2E86C1;'>📅 Exam Schedule Dashboard</h1>", unsafe_allow_html=True)
    
    # Display current timestamp (IST, June 04, 2025, 11:24 AM)
    current_time = datetime(2025, 6, 4, 11, 24).strftime("%B %d, %Y %I:%M %p IST")
    st.caption(f"Data last fetched on: {current_time}")

    # Search feature
    st.markdown("### Search for Your College", unsafe_allow_html=True)
    search_query = st.text_input("Enter institute name or code to search:", key="search_query")
    if search_query:
        search_query = search_query.lower().strip()
        filtered_df = df[
            df['institute_name'].str.lower().str.contains(search_query) |
            df['institute_code'].str.lower().str.contains(search_query)
        ]
        if not filtered_df.empty:
            st.write(f"Found {len(filtered_df)} matching institute(s):")
            display_df = filtered_df[[
                'institute_name', 'institute_code', 'total_students',
                'exam_start', 'exams_end', 'exam_start_1', 'exam_end',
                'exam_start_2', 'exam_end_1', 'exam_start_3', 'exam_end_2'
            ]].copy()
            display_df.columns = [
                'Institute Name', 'Institute Code', 'Total Students',
                'I Year Start', 'I Year End', 'II Year Start', 'II Year End',
                'III Year Start', 'III Year End', 'IV Year Start', 'IV Year End'
            ]
            st.dataframe(display_df, use_container_width=True)
        else:
            st.warning("No institutes found matching your search query.")

    # Option to disable duplicate removal
    remove_duplicates = st.checkbox("Remove duplicate institutes (uncheck if you're sure there are no duplicates)", value=True)

    # Check for duplicates
    if remove_duplicates:
        duplicate_codes = df[institute_code_column][df[institute_code_column].duplicated(keep=False)]
        if not duplicate_codes.empty:
            duplicates_df = df[df[institute_code_column].isin(duplicate_codes)][[institute_name_column, institute_code_column]]
            st.warning(f"Found {len(duplicate_codes)} duplicate institutes based on institute_code:")
            st.dataframe(duplicates_df.sort_values(by=institute_code_column))
            df = df.drop_duplicates(subset=[institute_code_column], keep='first')
    
    # Log institutes with zero students
    zero_students_df = df[df['total_students'] == 0][[institute_name_column, institute_code_column, 'total_students']]
    if not zero_students_df.empty:
        st.warning("The following institutes have zero students and will be filtered out:")
        st.dataframe(zero_students_df)
    
    # Filter out invalid rows
    valid_rows = []
    filtered_out = []
    for idx, row in df.iterrows():
        is_summary_row = False
        for col in df.columns:
            if isinstance(row[col], str) and "total" in row[col].lower():
                is_summary_row = True
                break
        
        total_students_row = row['total_students']
        
        if total_students_row > 0 and not is_summary_row:
            valid_rows.append(idx)
        else:
            filtered_out.append({
                'institute_name': row[institute_name_column],
                'institute_code': row[institute_code_column],
                'total_students': total_students_row,
                'reason': 'Zero students' if total_students_row == 0 else 'Summary row'
            })
    
    if valid_rows:
        df = df.loc[valid_rows].copy()
    else:
        st.error("No valid institutes found with student counts. Please check your data in the Appwrite 'exam_schedules' collection.")
        st.stop()
    
    # Display filtered-out institutes
    if filtered_out:
        filtered_df = pd.DataFrame(filtered_out)
        st.warning("The following institutes were filtered out:")
        st.dataframe(filtered_df)
    
    # Restore original institute names
    df[institute_name_column] = df[institute_name_column].str.title()
    
    # Calculate totals
    total_students = df['total_students'].sum()
    total_institutes = len(df)
    
    # Display totals
    st.markdown("### Overview", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    col1.metric("Total Institutes", total_institutes)
    col2.metric("Total Students", total_students)
    
    # Year input
    year = st.number_input("Enter the calendar year for the heatmap:", min_value=2000, max_value=2100, value=2025, step=1)

    # Date range input
    st.markdown("### Select Date Range", unsafe_allow_html=True)
    st.write("Select the date range to check for exams (format: DD-MM-YYYY):")
    col_start, col_end = st.columns(2)
    with col_start:
        start_date_input = st.date_input("Start Date", value=date(2025, 5, 19), min_value=date(2025, 1, 1), max_value=date(2025, 12, 31), key="start_date")
    with col_end:
        end_date_input = st.date_input("End Date", value=date(2025, 5, 19), min_value=date(2025, 1, 1), max_value=date(2025, 12, 31), key="end_date")

    # Update session state with date range
    if start_date_input and end_date_input:
        try:
            start_date = pd.Timestamp(start_date_input).normalize()
            end_date = pd.Timestamp(end_date_input).normalize()
            if start_date <= end_date:
                st.session_state["date_range"]["start_date"] = start_date
                st.session_state["date_range"]["end_date"] = end_date
            else:
                st.error("Start date must be before or equal to end date.")
                st.session_state["date_range"]["start_date"] = pd.Timestamp(date(2025, 5, 19))
                st.session_state["date_range"]["end_date"] = pd.Timestamp(date(2025, 5, 19))
        except (ValueError, pd.errors.OutOfBoundsDatetime):
            st.error("Invalid date range selected. Please ensure the dates are within 2025 and in a valid format.")
            st.session_state["date_range"]["start_date"] = pd.Timestamp(date(2025, 5, 19))
            st.session_state["date_range"]["end_date"] = pd.Timestamp(date(2025, 5, 19))

    # Calendar Heatmap
    if not all_exam_dates:
        st.warning("No valid exam dates found in the database. The heatmap will show full availability. Please verify that your exam dates are in a supported format (e.g., DD-MM-YYYY).")
    
    exam_series = pd.Series(all_exam_dates) if all_exam_dates else pd.Series()
    exam_counts = exam_series.value_counts().sort_index()
    
    start_date = pd.Timestamp(f"{year}-01-01")
    end_date = pd.Timestamp(f"{year}-12-31")
    full_range = pd.date_range(start_date, end_date)
    
    institute_availability = pd.Series(total_institutes, index=full_range) - exam_counts.reindex(full_range, fill_value=0)
    
    student_availability = pd.Series(total_students, index=full_range)
    for dt in full_range:
        date_key = dt.date()
        if date_key in unavailable_students_per_date:
            student_availability[dt] = total_students - unavailable_students_per_date[date_key]
        else:
            student_availability[dt] = total_students
    
    try:
        calendar_data = pd.DataFrame({
            'date': full_range,
            'day': full_range.day,
            'month': full_range.month,
            'year': full_range.year,
            'weekday': full_range.weekday,
            'institutes_available': institute_availability.values,
            'students_available': student_availability.values,
            'institute_percentage': (institute_availability.values / total_institutes) * 100 if total_institutes > 0 else 0,
            'student_percentage': (student_availability.values / total_students) * 100 if total_students > 0 else 0
        })
        
        calendar_data['intensity'] = 1 - (calendar_data['institutes_available'] / total_institutes) if total_institutes > 0 else 0
    except Exception as e:
        st.error(f"Error generating calendar data: {str(e)}")
        st.stop()
    
    st.markdown("---")
    st.markdown(f"### {year} Calendar Heatmap", unsafe_allow_html=True)
    st.write("This heatmap shows institute availability. Use the date range input above to check exams within a specific range.")
    
    col1, col2, col3, col4 = st.columns(4)
    month_columns = [col1, col2, col3, col4]
    
    def create_month_heatmap(month_idx, container):
        month_data = calendar_data[calendar_data['month'] == month_idx]
        days_in_month = month_data.shape[0]
        first_day = month_data.iloc[0]
        first_weekday = (first_day['weekday'] + 1) % 7
        
        container.markdown(f"<h3 style='text-align: center;'>{calendar.month_name[month_idx].upper()}</h3>", unsafe_allow_html=True)
        
        days_header = container.columns(7)
        days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        for i, day in enumerate(days):
            days_header[i].markdown(f"<div style='text-align:center; font-size:12px;'>{day}</div>", unsafe_allow_html=True)
        
        for week in range(6):
            cols = container.columns(7)
            for weekday in range(7):
                day_number = week * 7 + weekday + 1 - first_weekday
                if 1 <= day_number <= days_in_month:
                    day_data = month_data[month_data['day'] == day_number].iloc[0]
                    intensity = day_data['intensity']
                    red_val = min(255, int(255 * intensity))
                    color = f"rgb({255}, {255-red_val}, {220-red_val})"
                    cols[weekday].markdown(
                        f"""
                        <div style='background-color:{color}; text-align:center; padding:5px; border-radius:5px; position:relative;'>
                            {day_number}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    cols[weekday].write("")
            
            if (week + 1) * 7 - first_weekday >= days_in_month:
                break
    
    for month_idx, col in enumerate(month_columns, 1):
        with col:
            create_month_heatmap(month_idx, col)
    
    for month_idx, col in enumerate(month_columns, 5):
        with col:
            create_month_heatmap(month_idx, col)
    
    for month_idx, col in enumerate(month_columns, 9):
        with col:
            create_month_heatmap(month_idx, col)
    
    st.markdown("---")
    st.markdown("### Color Legend: Institute Availability", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div style='display: flex; align-items: center; justify-content: center; margin-top: 20px;'>
            <div style='width: 300px; height: 20px; background: linear-gradient(to right, rgb(255, 255, 220), rgb(255, 0, 0)); 
                        border: 1px solid #ccc; border-radius:5px;'></div>
        </div>
        <div style='display: flex; justify-content: space-between; width: 300px; margin: 0 auto; font-size: 12px;'>
            <span>{total_institutes} institutes (High Availability)</span>
            <span>0 institutes (Low Availability)</span>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Display detailed information if a date range is selected
    if st.session_state["date_range"]["start_date"] is not None and st.session_state["date_range"]["end_date"] is not None:
        st.markdown("---")
        st.markdown("### 📊 Institute and Student Availability Details", unsafe_allow_html=True)
        start_date = st.session_state["date_range"]["start_date"]
        end_date = st.session_state["date_range"]["end_date"]
        st.write(f"Selected date range: {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}")
        
        # Calculate average availability
        date_range = pd.date_range(start=start_date, end=end_date)
        date_availability = calendar_data[calendar_data['date'].isin(date_range)]
        
        if not date_availability.empty:
            avg_institutes_available = int(date_availability['institutes_available'].mean())
            avg_students_available = int(date_availability['students_available'].mean())
            avg_institute_percentage = date_availability['institute_percentage'].mean()
            avg_student_percentage = date_availability['student_percentage'].mean()
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Avg. Available Institutes", f"{avg_institutes_available}/{total_institutes}", 
                       f"{avg_institute_percentage:.1f}% available")
            col2.metric("Avg. Institutes with Exams", f"{int(total_institutes - avg_institutes_available)}", 
                       f"{100 - avg_institute_percentage:.1f}% busy")
            col3.metric("Avg. Available Students", f"{avg_students_available}/{total_students}", 
                       f"{avg_student_percentage:.1f}% available")
            col4.metric("Avg. Students with Exams", f"{int(total_students - avg_students_available)}", 
                       f"{100 - avg_student_percentage:.1f}% busy")
        
        # Check exam dates for each college
        colleges_with_exams = []
        
        for idx, row in df.iterrows():
            institute_name = row.get(institute_name_column, f"Institute {idx}")
            for (start_col, end_col), academic_year in exam_pairs_to_years.items():
                if start_col in df.columns and end_col in df.columns:
                    start_str = row[start_col]
                    end_str = row[end_col]
                    if start_str and end_str:
                        start = pd.to_datetime(start_str, format="%d-%m-%Y", errors="coerce", dayfirst=True)
                        end = pd.to_datetime(end_str, format="%d-%m-%Y", errors="coerce", dayfirst=True)
                        if pd.notnull(start) and pd.notnull(end) and start <= end:
                            start = start.normalize()
                            end = end.normalize()
                            if start <= end_date and end >= start_date:
                                colleges_with_exams.append((institute_name, academic_year))
        
        # Display colleges with exams
        st.markdown(f"### 🎓 Colleges with Exams from {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}", unsafe_allow_html=True)
        
        colleges_with_exams_in_range = set([college_name for college_name, _ in colleges_with_exams])
        
        if colleges_with_exams_in_range:
            st.write(f"**{len(colleges_with_exams_in_range)} Colleges have exams in this date range:**")
            institutes_with_exams_df = pd.DataFrame(sorted(colleges_with_exams_in_range), columns=["College Name"])
            st.dataframe(institutes_with_exams_df, use_container_width=True)
            
            st.markdown("#### Colleges with Exams by Academic Year", unsafe_allow_html=True)
            exams_by_year = {year: [] for year in academic_years}
            
            for college_name, academic_year in colleges_with_exams:
                exams_by_year[academic_year].append(college_name)
            
            tabs_year = st.tabs(academic_years)
            for i, year in enumerate(academic_years):
                with tabs_year[i]:
                    if exams_by_year[year]:
                        st.write(f"**{len(set(exams_by_year[year]))} Colleges with {year} exams in this date range:**")
                        year_df = pd.DataFrame(sorted(set(exams_by_year[year])), columns=["College Name"])
                        st.dataframe(year_df, use_container_width=True)
                    else:
                        st.write(f"No colleges have {year} exams in this date range.")
        else:
            st.write(f"No colleges have exams between {start_date.strftime('%B %d, %Y')} and {end_date.strftime('%B %d, %Y')}. Please verify that your database includes exam dates covering this range in a supported format (e.g., DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD, DD Mon YYYY).")

# Admin Dashboard (requires login)
elif mode == "Admin":
    if not st.session_state.admin_authenticated:
        st.markdown("<h1 style='text-align: center; color: #2E86C1;'>Admin Login</h1>", unsafe_allow_html=True)
        username = st.text_input("Username", key="admin_username")
        password = st.text_input("Password", type="password", key="admin_password")
        if st.button("Login", key="admin_login"):
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                st.session_state.admin_authenticated = True
                st.success("Logged in as Admin!")
                st.rerun()
            else:
                st.error("Invalid username or password.")
    else:
        st.markdown("<h1 style='text-align: center; color: #2E86C1;'>📋 Admin Dashboard</h1>", unsafe_allow_html=True)
        if st.button("Logout", key="admin_logout"):
            st.session_state.admin_authenticated = False
            st.session_state.editing_institute_id = None  # Reset editing state on logout
            st.success("Logged out successfully!")
            st.rerun()

        # Display all data with search and scrollbar
        st.markdown("### All Institute Data", unsafe_allow_html=True)
        search_query_admin = st.text_input("Search for an institute by name or code:", key="admin_search")
        display_df = df[[
            'document_id', 'institute_name', 'institute_code', 'total_students',
            'exam_start', 'exams_end', 'exam_start_1', 'exam_end',
            'exam_start_2', 'exam_end_1', 'exam_start_3', 'exam_end_2'
        ]].copy()
        display_df.columns = [
            'Document ID', 'Institute Name', 'Institute Code', 'Total Students',
            'I Year Start', 'I Year End', 'II Year Start', 'II Year End',
            'III Year Start', 'III Year End', 'IV Year Start', 'IV Year End'
        ]

        # Filter data based on search query
        if search_query_admin:
            search_query_admin = search_query_admin.lower().strip()
            display_df = display_df[
                display_df['Institute Name'].str.lower().str.contains(search_query_admin) |
                display_df['Institute Code'].str.lower().str.contains(search_query_admin)
            ]

        # Display data in a scrollable container
        st.markdown(
            """
            <style>
            .scrollable-table {
                max-height: 400px;
                overflow-y: auto;
                display: block;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        st.markdown('<div class="scrollable-table">', unsafe_allow_html=True)
        
        # Display headers
        cols = st.columns([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2])  # Adjusted for two buttons
        headers = [
            'Document ID', 'Institute Name', 'Institute Code', 'Total Students',
            'I Year Start', 'I Year End', 'II Year Start', 'II Year End',
            'III Year Start', 'III Year End', 'IV Year Start', 'IV Year End', 'Action'
        ]
        for idx, header in enumerate(headers):
            cols[idx].markdown(f"<b>{header}</b>", unsafe_allow_html=True)

        # Display rows with Edit and Delete buttons
        for idx, row in display_df.iterrows():
            cols = st.columns([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2])
            cols[0].write(row['Document ID'])
            cols[1].write(row['Institute Name'])
            cols[2].write(row['Institute Code'])
            cols[3].write(row['Total Students'])
            cols[4].write(row['I Year Start'])
            cols[5].write(row['I Year End'])
            cols[6].write(row['II Year Start'])
            cols[7].write(row['II Year End'])
            cols[8].write(row['III Year Start'])
            cols[9].write(row['III Year End'])
            cols[10].write(row['IV Year Start'])
            cols[11].write(row['IV Year End'])
            col_action1, col_action2 = cols[12].columns(2)
            if col_action1.button("Edit", key=f"edit_{row['Document ID']}"):
                st.session_state.editing_institute_id = row['Document ID']
            if col_action2.button("Delete", key=f"delete_{row['Document ID']}"):
                try:
                    databases.delete_document(
                        APPWRITE_DATABASE_ID,
                        APPWRITE_COLLECTION_ID,
                        row['Document ID']
                    )
                    st.session_state.editing_institute_id = None  # Reset if deleted
                    st.success(f"Successfully deleted institute: {row['Institute Name']} ({row['Institute Code']})")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting institute: {str(e)}")

        st.markdown('</div>', unsafe_allow_html=True)

        # Edit Institute Section
        if st.session_state.editing_institute_id:
            institute_to_edit = df[df['document_id'] == st.session_state.editing_institute_id].iloc[0]
            with st.expander("Edit Institute Details", expanded=True):
                with st.form("edit_institute_form"):
                    st.markdown(f"### Editing Institute: {institute_to_edit['institute_name']} ({institute_to_edit['institute_code']})")
                    institute_name = st.text_input("Institute Name", value=institute_to_edit['institute_name'])
                    institute_code = st.text_input("Institute Code", value=institute_to_edit['institute_code'])
                    total_students = st.number_input("Total Students", min_value=0, step=1, value=int(institute_to_edit['total_students']))
                    st.write("I Year Exam Schedule")
                    exam_start = st.date_input("Exam Start (I Year)", value=pd.to_datetime(institute_to_edit['exam_start'], format="%d-%m-%Y", errors='coerce', dayfirst=True) if institute_to_edit['exam_start'] else None)
                    exams_end = st.date_input("Exam End (I Year)", value=pd.to_datetime(institute_to_edit['exams_end'], format="%d-%m-%Y", errors='coerce', dayfirst=True) if institute_to_edit['exams_end'] else None)
                    st.write("II Year Exam Schedule")
                    exam_start_1 = st.date_input("Exam Start (II Year)", value=pd.to_datetime(institute_to_edit['exam_start_1'], format="%d-%m-%Y", errors='coerce', dayfirst=True) if institute_to_edit['exam_start_1'] else None)
                    exam_end = st.date_input("Exam End (II Year)", value=pd.to_datetime(institute_to_edit['exam_end'], format="%d-%m-%Y", errors='coerce', dayfirst=True) if institute_to_edit['exam_end'] else None)
                    st.write("III Year Exam Schedule")
                    exam_start_2 = st.date_input("Exam Start (III Year)", value=pd.to_datetime(institute_to_edit['exam_start_2'], format="%d-%m-%Y", errors='coerce', dayfirst=True) if institute_to_edit['exam_start_2'] else None)
                    exam_end_1 = st.date_input("Exam End (III Year)", value=pd.to_datetime(institute_to_edit['exam_end_1'], format="%d-%m-%Y", errors='coerce', dayfirst=True) if institute_to_edit['exam_end_1'] else None)
                    st.write("IV Year Exam Schedule")
                    exam_start_3 = st.date_input("Exam Start (IV Year)", value=pd.to_datetime(institute_to_edit['exam_start_3'], format="%d-%m-%Y", errors='coerce', dayfirst=True) if institute_to_edit['exam_start_3'] else None)
                    exam_end_2 = st.date_input("Exam End (IV Year)", value=pd.to_datetime(institute_to_edit['exam_end_2'], format="%d-%m-%Y", errors='coerce', dayfirst=True) if institute_to_edit['exam_end_2'] else None)

                    col_submit, col_cancel = st.columns(2)
                    with col_submit:
                        submit = st.form_submit_button("Save Changes")
                    with col_cancel:
                        if st.form_submit_button("Cancel"):
                            st.session_state.editing_institute_id = None
                            st.rerun()

                    if submit:
                        # Format dates to DD-MM-YYYY
                        exam_start = exam_start.strftime("%d-%m-%Y") if exam_start else None
                        exams_end = exams_end.strftime("%d-%m-%Y") if exams_end else None
                        exam_start_1 = exam_start_1.strftime("%d-%m-%Y") if exam_start_1 else None
                        exam_end = exam_end.strftime("%d-%m-%Y") if exam_end else None
                        exam_start_2 = exam_start_2.strftime("%d-%m-%Y") if exam_start_2 else None
                        exam_end_1 = exam_end_1.strftime("%d-%m-%Y") if exam_end_1 else None
                        exam_start_3 = exam_start_3.strftime("%d-%m-%Y") if exam_start_3 else None
                        exam_end_2 = exam_end_2.strftime("%d-%m-%Y") if exam_end_2 else None

                        # Check for duplicate institute_code (excluding the current institute)
                        existing = databases.list_documents(
                            APPWRITE_DATABASE_ID,
                            APPWRITE_COLLECTION_ID,
                            queries=[Query.equal("institute_code", institute_code)]
                        ).get("documents", [])
                        conflicting_docs = [doc for doc in existing if doc['$id'] != st.session_state.editing_institute_id]
                        
                        if conflicting_docs:
                            st.error(f"Institute with code {institute_code} already exists. Please choose a different code.")
                        else:
                            try:
                                databases.update_document(
                                    APPWRITE_DATABASE_ID,
                                    APPWRITE_COLLECTION_ID,
                                    st.session_state.editing_institute_id,
                                    data={
                                        "institute_name": institute_name,
                                        "institute_code": institute_code,
                                        "total_students": int(total_students),
                                        "exam_start": exam_start,
                                        "exams_end": exams_end,
                                        "exam_start_1": exam_start_1,
                                        "exam_end": exam_end,
                                        "exam_start_2": exam_start_2,
                                        "exam_end_1": exam_end_1,
                                        "exam_start_3": exam_start_3,
                                        "exam_end_2": exam_end_2,
                                    }
                                )
                                st.success(f"Institute {institute_name} updated successfully! Please refresh the page to see the updated data.")
                                st.session_state.editing_institute_id = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error updating institute: {str(e)}")

        # Add new data
        st.markdown("### Add New Institute", unsafe_allow_html=True)
        with st.form("add_institute_form"):
            institute_name = st.text_input("Institute Name")
            institute_code = st.text_input("Institute Code")
            total_students = st.number_input("Total Students", min_value=0, step=1)
            st.write("I Year Exam Schedule")
            exam_start = st.date_input("Exam Start (I Year)")
            exams_end = st.date_input("Exam End (I Year)")
            st.write("II Year Exam Schedule")
            exam_start_1 = st.date_input("Exam Start (II Year)")
            exam_end = st.date_input("Exam End (II Year)")
            st.write("III Year Exam Schedule")
            exam_start_2 = st.date_input("Exam Start (III Year)")
            exam_end_1 = st.date_input("Exam End (III Year)")
            st.write("IV Year Exam Schedule")
            exam_start_3 = st.date_input("Exam Start (IV Year)")
            exam_end_2 = st.date_input("Exam End (IV Year)")
            submit = st.form_submit_button("Add Institute")

            if submit:
                # Format dates to DD-MM-YYYY
                exam_start = exam_start.strftime("%d-%m-%Y") if exam_start else None
                exams_end = exams_end.strftime("%d-%m-%Y") if exams_end else None
                exam_start_1 = exam_start_1.strftime("%d-%m-%Y") if exam_start_1 else None
                exam_end = exam_end.strftime("%d-%m-%Y") if exam_end else None
                exam_start_2 = exam_start_2.strftime("%d-%m-%Y") if exam_start_2 else None
                exam_end_1 = exam_end_1.strftime("%d-%m-%Y") if exam_end_1 else None
                exam_start_3 = exam_start_3.strftime("%d-%m-%Y") if exam_start_3 else None
                exam_end_2 = exam_end_2.strftime("%d-%m-%Y") if exam_end_2 else None

                # Check for duplicate institute_code
                existing = databases.list_documents(
                    APPWRITE_DATABASE_ID,
                    APPWRITE_COLLECTION_ID,
                    queries=[Query.equal("institute_code", institute_code)]
                ).get("documents", [])
                
                if existing:
                    st.error(f"Institute with code {institute_code} already exists. Please use the CSV upload to edit existing data.")
                else:
                    try:
                        databases.create_document(
                            APPWRITE_DATABASE_ID,
                            APPWRITE_COLLECTION_ID,
                            document_id="unique()",
                            data={
                                "institute_name": institute_name,
                                "institute_code": institute_code,
                                "total_students": int(total_students),
                                "exam_start": exam_start,
                                "exams_end": exams_end,
                                "exam_start_1": exam_start_1,
                                "exam_end": exam_end,
                                "exam_start_2": exam_start_2,
                                "exam_end_1": exam_end_1,
                                "exam_start_3": exam_start_3,
                                "exam_end_2": exam_end_2,
                            }
                        )
                        st.success("Institute added successfully! Please refresh the page to see the updated data.")
                    except Exception as e:
                        st.error(f"Error adding institute: {str(e)}")

        # Upload CSV to add/edit data
        st.markdown("### Upload CSV to Add/Edit Institutes", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload a CSV file", type="csv")
        if uploaded_file:
            try:
                csv_df = pd.read_csv(uploaded_file)
                expected_columns = [
                    "institute_name", "institute_code", "total_students",
                    "exam_start", "exams_end", "exam_start_1", "exam_end",
                    "exam_start_2", "exam_end_1", "exam_start_3", "exam_end_2"
                ]
                if not all(col in csv_df.columns for col in expected_columns):
                    st.error(f"CSV must contain the following columns: {', '.join(expected_columns)}")
                else:
                    st.write("Preview of uploaded CSV:")
                    st.dataframe(csv_df)

                    if st.button("Process CSV"):
                        for idx, row in csv_df.iterrows():
                            institute_code = str(row['institute_code']).strip()
                            # Check if institute_code exists
                            existing = databases.list_documents(
                                APPWRITE_DATABASE_ID,
                                APPWRITE_COLLECTION_ID,
                                queries=[Query.equal("institute_code", institute_code)]
                            ).get("documents", [])
                        
                            data = {
                                "institute_name": str(row['institute_name']),
                                "institute_code": institute_code,
                                "total_students": int(row['total_students']) if pd.notnull(row['total_students']) else 0,
                                "exam_start": str(row['exam_start']) if pd.notnull(row['exam_start']) else None,
                                "exams_end": str(row['exams_end']) if pd.notnull(row['exams_end']) else None,
                                "exam_start_1": str(row['exam_start_1']) if pd.notnull(row['exam_start_1']) else None,
                                "exam_end": str(row['exam_end']) if pd.notnull(row['exam_end']) else None,
                                "exam_start_2": str(row['exam_start_2']) if pd.notnull(row['exam_start_2']) else None,
                                "exam_end_1": str(row['exam_end_1']) if pd.notnull(row['exam_end_1']) else None,
                                "exam_start_3": str(row['exam_start_3']) if pd.notnull(row['exam_start_3']) else None,
                                "exam_end_2": str(row['exam_end_2']) if pd.notnull(row['exam_end_2']) else None,
                            }

                            try:
                                if existing:
                                    # Update existing document
                                    doc_id = existing[0]['$id']
                                    databases.update_document(
                                        APPWRITE_DATABASE_ID,
                                        APPWRITE_COLLECTION_ID,
                                        doc_id,
                                        data
                                    )
                                    st.info(f"Updated institute with code {institute_code}.")
                                else:
                                    # Add new document
                                    databases.create_document(
                                        APPWRITE_DATABASE_ID,
                                        APPWRITE_COLLECTION_ID,
                                        document_id="unique()",
                                        data=data
                                    )
                                    st.info(f"Added new institute with code {institute_code}.")
                            except Exception as e:
                                st.error(f"Error processing institute with code {institute_code}: {str(e)}")
                        st.success("CSV processing completed! Please refresh the page to see the updated data.")

            except Exception as e:
                st.error(f"Error reading CSV file: {str(e)}")

        # Compute calendar_data for Admin Dashboard usage
        year = 2025  # Default year for Admin Dashboard analytics
        total_students_admin = df['total_students'].sum()
        total_institutes_admin = len(df)
        
        exam_series_admin = pd.Series(all_exam_dates) if all_exam_dates else pd.Series()
        exam_counts_admin = exam_series_admin.value_counts().sort_index()
        
        start_date_admin = pd.Timestamp(f"{year}-01-01")
        end_date_admin = pd.Timestamp(f"{year}-12-31")
        full_range_admin = pd.date_range(start_date_admin, end_date_admin)
        
        institute_availability_admin = pd.Series(total_institutes_admin, index=full_range_admin) - exam_counts_admin.reindex(full_range_admin, fill_value=0)
        
        student_availability_admin = pd.Series(total_students_admin, index=full_range_admin)
        for dt in full_range_admin:
            date_key = dt.date()
            if date_key in unavailable_students_per_date:
                student_availability_admin[dt] = total_students_admin - unavailable_students_per_date[date_key]
            else:
                student_availability_admin[dt] = total_students_admin
        
        try:
            calendar_data_admin = pd.DataFrame({
                'date': full_range_admin,
                'day': full_range_admin.day,
                'month': full_range_admin.month,
                'year': full_range_admin.year,
                'weekday': full_range_admin.weekday,
                'institutes_available': institute_availability_admin.values,
                'students_available': student_availability_admin.values,
                'institute_percentage': (institute_availability_admin.values / total_institutes_admin) * 100 if total_institutes_admin > 0 else 0,
                'student_percentage': (student_availability_admin.values / total_students_admin) * 100 if total_students_admin > 0 else 0
            })
            
            calendar_data_admin['intensity'] = 1 - (calendar_data_admin['institutes_available'] / total_institutes_admin) if total_institutes_admin > 0 else 0
        except Exception as e:
            st.error(f"Error generating calendar data for Admin Dashboard: {str(e)}")
            st.stop()

        # Analytics Section for Admin
        st.markdown("---")
        with st.expander("📈 Analytics Dashboard", expanded=False):
            # Institute and Student Availability Details
            if st.session_state["date_range"]["start_date"] is not None and st.session_state["date_range"]["end_date"] is not None:
                st.markdown("### 📊 Institute and Student Availability Details", unsafe_allow_html=True)
                start_date = st.session_state["date_range"]["start_date"]
                end_date = st.session_state["date_range"]["end_date"]
                st.write(f"Selected date range: {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}")
                
                # Calculate average availability
                date_range = pd.date_range(start=start_date, end=end_date)
                date_availability = calendar_data_admin[calendar_data_admin['date'].isin(date_range)]
                
                if not date_availability.empty:
                    avg_institutes_available = int(date_availability['institutes_available'].mean())
                    avg_students_available = int(date_availability['students_available'].mean())
                    avg_institute_percentage = date_availability['institute_percentage'].mean()
                    avg_student_percentage = date_availability['student_percentage'].mean()
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Avg. Available Institutes", f"{avg_institutes_available}/{total_institutes_admin}", 
                               f"{avg_institute_percentage:.1f}% available")
                    col2.metric("Avg. Institutes with Exams", f"{int(total_institutes_admin - avg_institutes_available)}", 
                               f"{100 - avg_institute_percentage:.1f}% busy")
                    col3.metric("Avg. Available Students", f"{avg_students_available}/{total_students_admin}", 
                               f"{avg_student_percentage:.1f}% available")
                    col4.metric("Avg. Students with Exams", f"{int(total_students_admin - avg_students_available)}", 
                               f"{100 - avg_student_percentage:.1f}% busy")

                    # Bar Chart for Institute Availability
                    st.markdown("#### Institute Availability Breakdown", unsafe_allow_html=True)
                    institute_data = pd.DataFrame({
                        "Category": ["Available Institutes", "Institutes with Exams"],
                        "Count": [avg_institutes_available, int(total_institutes_admin - avg_institutes_available)]
                    })
                    fig_institute = px.bar(
                        institute_data,
                        x="Category",
                        y="Count",
                        title="Institute Availability",
                        color="Category",
                        color_discrete_map={
                            "Available Institutes": "#00CC96",
                            "Institutes with Exams": "#EF553B"
                        },
                        text="Count"
                    )
                    fig_institute.update_layout(
                        title_x=0.5,
                        xaxis_title="Category",
                        yaxis_title="Number of Institutes",
                        showlegend=False
                    )
                    fig_institute.update_traces(textposition='auto')
                    st.plotly_chart(fig_institute, use_container_width=True)

                    # Bar Chart for Student Availability
                    st.markdown("#### Student Availability Breakdown", unsafe_allow_html=True)
                    student_data = pd.DataFrame({
                        "Category": ["Available Students", "Students with Exams"],
                        "Count": [avg_students_available, int(total_students_admin - avg_students_available)]
                    })
                    fig_student = px.bar(
                        student_data,
                        x="Category",
                        y="Count",
                        title="Student Availability",
                        color="Category",
                        color_discrete_map={
                            "Available Students": "#00CC96",
                            "Students with Exams": "#EF553B"
                        },
                        text="Count"
                    )
                    fig_student.update_layout(
                        title_x=0.5,
                        xaxis_title="Category",
                        yaxis_title="Number of Students",
                        showlegend=False
                    )
                    fig_student.update_traces(textposition='auto')
                    st.plotly_chart(fig_student, use_container_width=True)

                # Student Impact by Academic Year (Selected Range)
                st.markdown("### Student Impact by Academic Year (Selected Range)", unsafe_allow_html=True)
                students_by_year = {year: 0 for year in academic_years}
                for period in exam_periods:
                    if period['start_date'] <= end_date and period['end_date'] >= start_date:
                        students_by_year[period['academic_year']] += period['students']
                
                students_df = pd.DataFrame(list(students_by_year.items()), columns=['Academic Year', 'Students Affected'])
                if students_df['Students Affected'].sum() > 0:
                    fig2 = px.pie(
                        students_df,
                        names='Academic Year',
                        values='Students Affected',
                        title="Percentage of Students Affected by Exams",
                        color_discrete_sequence=px.colors.qualitative.Plotly
                    )
                    fig2.update_traces(textinfo='percent+label')
                    fig2.update_layout(title_x=0.5)
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("No students are affected by exams in the selected date range.")

            # Total Students per Institute
            st.markdown("### Total Students per Institute", unsafe_allow_html=True)
            student_dist_df = df[['institute_name', 'total_students']].sort_values(by='total_students', ascending=False).head(10)
            fig4 = px.bar(
                student_dist_df,
                x='total_students',
                y='institute_name',
                orientation='h',
                title="Top 10 Institutes by Number of Students",
                labels={'total_students': 'Number of Students', 'institute_name': 'Institute Name'},
                color='total_students',
                color_continuous_scale=px.colors.sequential.Plasma
            )
            fig4.update_layout(
                xaxis_title="Number of Students",
                yaxis_title="Institute Name",
                title_x=0.5,
                showlegend=False
            )
            st.plotly_chart(fig4, use_container_width=True)