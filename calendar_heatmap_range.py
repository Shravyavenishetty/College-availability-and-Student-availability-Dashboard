import pandas as pd
import streamlit as st
import calendar
import numpy as np
from datetime import datetime, date
import os

# Set page config
st.set_page_config(layout="wide")
st.title("📅 Institute and Student Availability Calendar Heatmap")

# File uploader for any file type
uploaded_file = st.file_uploader("Upload your file (e.g., .ods, .xlsx, .csv)", type=None)

# Allow user to specify the header row
header_row = st.number_input("Specify the header row (0-based index, typically 0 or 1):", min_value=0, max_value=10, value=1, step=1)

# Year input from user (calendar year for the heatmap)
year = st.number_input("Enter the calendar year for the heatmap:", min_value=2000, max_value=2100, value=2025, step=1)

# Date range input for manual entry
st.write("Select the date range to check for exams (format: DD-MM-YYYY):")
col_start, col_end = st.columns(2)
with col_start:
    start_date_input = st.date_input("Start Date", value=date(2025, 5, 19), min_value=date(2025, 1, 1), max_value=date(2025, 12, 31))
with col_end:
    end_date_input = st.date_input("End Date", value=date(2025, 5, 19), min_value=date(2025, 1, 1), max_value=date(2025, 12, 31))

# Option to disable duplicate removal
remove_duplicates = st.checkbox("Remove duplicate institutes (uncheck if you're sure there are no duplicates)", value=True)

# Initialize session state for selected date range
if "date_range" not in st.session_state:
    st.session_state["date_range"] = {"start_date": None, "end_date": None}

# Update session state with the manually entered date range
if start_date_input and end_date_input:
    try:
        start_date = pd.Timestamp(start_date_input).normalize()
        end_date = pd.Timestamp(end_date_input).normalize()
        if start_date <= end_date:
            st.session_state["date_range"]["start_date"] = start_date
            st.session_state["date_range"]["end_date"] = end_date
        else:
            st.error("Start date must be before or equal to end date.")
            st.session_state["date_range"]["start_date"] = None
            st.session_state["date_range"]["end_date"] = None
    except (ValueError, pd.errors.OutOfBoundsDatetime):
        st.session_state["date_range"]["start_date"] = None
        st.session_state["date_range"]["end_date"] = None
else:
    st.session_state["date_range"]["start_date"] = None
    st.session_state["date_range"]["end_date"] = None

if uploaded_file:
    try:
        # Determine file extension
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        
        # Read the file based on its extension
        if file_extension == '.ods':
            df = pd.read_excel(uploaded_file, engine="odf", header=header_row)
        elif file_extension in ['.xlsx', '.xls']:
            df = pd.read_excel(uploaded_file, engine="openpyxl", header=header_row)
        elif file_extension == '.csv':
            df = pd.read_csv(uploaded_file, header=header_row)
        else:
            st.error(f"Unsupported file type: {file_extension}. Please upload a .ods, .xlsx, or .csv file.")
            st.stop()
        
        # Clean the data
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        # Define exam date column pairs and map them to academic years
        exam_pairs = [
            ("exam_start", "exams_end"),      # I year
            ("exam_start.1", "exam_end"),     # II year
            ("exam_start.2", "exam_end.1"),   # III year
            ("exam_start.3", "exam_end.2"),   # IV year
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
        
        # Identify institute name and code columns
        possible_institute_name_columns = ['institute_name', 'name', 'institute', 'college_name', 'college']
        possible_institute_code_columns = ['institute_code', 'code', 'id', 'institute_id']
        
        institute_name_column = None
        institute_code_column = None
        
        for col in possible_institute_name_columns:
            if col in df.columns:
                institute_name_column = col
                break
        
        for col in possible_institute_code_columns:
            if col in df.columns:
                institute_code_column = col
                break
        
        if institute_name_column is None:
            st.error(f"Could not find a column for institute names (tried {possible_institute_name_columns}). Actual columns found: {', '.join(df.columns)}")
            st.stop()
        
        if institute_code_column is None:
            st.error(f"Could not find a column for institute codes (tried {possible_institute_code_columns}). Actual columns found: {', '.join(df.columns)}")
            st.stop()
        
        # Normalize institute names and codes to handle case sensitivity and whitespace
        df[institute_name_column] = df[institute_name_column].astype(str).str.strip().str.lower()
        df[institute_code_column] = df[institute_code_column].astype(str).str.strip()
        
        # Check for duplicates using the institute code column
        if remove_duplicates:
            duplicates = df.duplicated(subset=[institute_code_column], keep=False)
            if duplicates.any():
                df = df.drop_duplicates(subset=[institute_code_column], keep='first')
        
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
                return None
        
        # Convert exam date columns to string to handle mixed data types
        for start_col, end_col in exam_pairs:
            if start_col in df.columns and end_col in df.columns:
                df[start_col] = df[start_col].astype(str)
                df[end_col] = df[end_col].astype(str)
        
        # Apply normalization to all exam date columns
        for start_col, end_col in exam_pairs:
            if start_col in df.columns and end_col in df.columns:
                df[start_col] = df[start_col].apply(normalize_date_string)
                df[end_col] = df[end_col].apply(normalize_date_string)
        
        # Filter out invalid rows
        valid_rows = []
        expected_total_students = 98603
        for idx, row in df.iterrows():
            is_summary_row = False
            for col in df.columns:
                if isinstance(row[col], str) and "total" in row[col].lower():
                    is_summary_row = True
                    break
            
            has_valid_exam_dates = False
            for start_col, end_col in exam_pairs:
                if start_col in df.columns and end_col in df.columns:
                    start_str = row[start_col]
                    end_str = row[end_col]
                    if start_str and end_str:
                        start = pd.to_datetime(start_str, format="%d-%m-%Y", errors="coerce", dayfirst=True)
                        end = pd.to_datetime(end_str, format="%d-%m-%Y", errors="coerce", dayfirst=True)
                        if pd.notnull(start) and pd.notnull(end) and start <= end:
                            has_valid_exam_dates = True
                            break
            
            total_students_row = pd.to_numeric(row.get('total_students', 0), errors='coerce') or 0
            if total_students_row == expected_total_students:
                is_summary_row = True
            
            if (has_valid_exam_dates or total_students_row > 0) and not is_summary_row:
                valid_rows.append(idx)
        
        if valid_rows:
            df = df.loc[valid_rows].copy()
        else:
            st.error("No valid rows found with exam dates or student counts. Please check your data.")
            st.stop()
        
        # Restore original institute names (proper case for display purposes)
        df[institute_name_column] = df[institute_name_column].str.title()
        
        # Use the total_students column directly from the sheet
        if 'total_students' in df.columns:
            df['total_students'] = pd.to_numeric(df['total_students'], errors='coerce').fillna(0).astype(int)
        else:
            if 'convener_seats' in df.columns and 'management_seats' in df.columns:
                df['convener_seats'] = pd.to_numeric(df['convener_seats'], errors='coerce').fillna(0).astype(int)
                df['management_seats'] = pd.to_numeric(df['management_seats'], errors='coerce').fillna(0).astype(int)
                df['total_students'] = df['convener_seats'] + df['management_seats']
            else:
                st.error("Neither 'total_students' nor 'convener_seats' and 'management_seats' columns found. Cannot calculate student counts.")
                st.stop()
        
        # Calculate the total students
        total_students = df['total_students'].sum()
        total_institutes = len(df)
        
        # Verify the calculated total against the provided total
        if total_students != expected_total_students:
            st.warning(f"Calculated total students ({total_students}) does not match the provided total ({expected_total_students}). Please check your data for duplicates or errors.")
        else:
            st.success(f"Calculated total students ({total_students}) matches the provided total ({expected_total_students}).")
        
        # Display the totals for verification
        st.write(f"**Total Institutes**: {total_institutes}")
        st.write(f"**Total Students**: {total_students}")
        
        # --- Calendar Heatmap ---
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
                            for date in exam_range:
                                date_key = date.date()
                                if date_key in unavailable_students_per_date:
                                    unavailable_students_per_date[date_key] += students
                                else:
                                    unavailable_students_per_date[date_key] = students
        
        if not all_exam_dates:
            st.warning("No valid exam dates found in the file.")
        else:
            exam_series = pd.Series(all_exam_dates)
            exam_counts = exam_series.value_counts().sort_index()
            
            start_date = pd.Timestamp(f"{year}-01-01")
            end_date = pd.Timestamp(f"{year}-12-31")
            full_range = pd.date_range(start_date, end_date)
            
            institute_availability = pd.Series(total_institutes, index=full_range) - exam_counts.reindex(full_range, fill_value=0)
            
            student_availability = pd.Series(total_students, index=full_range)
            for date in full_range:
                date_key = date.date()
                if date_key in unavailable_students_per_date:
                    student_availability[date] = total_students - unavailable_students_per_date[date_key]
                else:
                    student_availability[date] = total_students
            
            calendar_data = pd.DataFrame({
                'date': full_range,
                'day': full_range.day,
                'month': full_range.month,
                'year': full_range.year,
                'weekday': full_range.weekday,
                'institutes_available': institute_availability.values,
                'students_available': student_availability.values,
                'institute_percentage': (institute_availability.values / total_institutes) * 100,
                'student_percentage': (student_availability.values / total_students) * 100 if total_students > 0 else 0
            })
            
            calendar_data['intensity'] = 1 - (calendar_data['institutes_available'] / total_institutes)
            
            st.markdown("---")
            st.subheader(f"{year} Calendar Heatmap")
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
            st.subheader("Color Legend: Institute Availability")
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
                st.subheader("📊 Institute and Student Availability Details")
                start_date = st.session_state["date_range"]["start_date"]
                end_date = st.session_state["date_range"]["end_date"]
                st.write(f"Selected date range: {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}")
                
                # Calculate average availability over the date range
                date_range = pd.date_range(start=start_date, end=end_date)
                date_availability = calendar_data[calendar_data['date'].isin(date_range)]
                
                if not date_availability.empty:
                    avg_institutes_available = int(date_availability['institutes_available'].mean())
                    avg_students_available = int(date_availability['students_available'].mean())
                    avg_institute_percentage = date_availability['institute_percentage'].mean()
                    avg_student_percentage = date_availability['student_percentage'].mean()
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Avg. Available Institutes", f"{avg_institutes_available} / {total_institutes}", 
                               f"{avg_institute_percentage:.1f}% available")
                    col2.metric("Avg. Institutes with Exams", f"{int(total_institutes - avg_institutes_available)}", 
                               f"{100 - avg_institute_percentage:.1f}% busy")
                    col3.metric("Avg. Available Students", f"{avg_students_available} / {total_students}", 
                               f"{avg_student_percentage:.1f}% available")
                    col4.metric("Avg. Students with Exams", f"{int(total_students - avg_students_available)}", 
                               f"{100 - avg_student_percentage:.1f}% busy")
                
                # --- Check Exam Dates for Each College ---
                colleges_with_exams = []  # List to store (college_name, academic_year) pairs
                
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
                                    # Check for overlap between exam range and selected range
                                    # Two ranges overlap if: start1 <= end2 and end1 >= start2
                                    if start <= end_date and end >= start_date:
                                        colleges_with_exams.append((institute_name, academic_year))
                
                # Display the specific names of colleges with exams in the selected range
                st.subheader(f"🎓 Colleges with Exams from {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}")
                
                colleges_with_exams_in_range = set([college_name for college_name, _ in colleges_with_exams])
                
                if colleges_with_exams_in_range:
                    st.write(f"**{len(colleges_with_exams_in_range)} Colleges have exams in this date range:**")
                    institutes_with_exams_df = pd.DataFrame(sorted(colleges_with_exams_in_range), columns=["College Name"])
                    st.dataframe(institutes_with_exams_df)
                    
                    st.subheader("Colleges with Exams by Academic Year")
                    exams_by_year = {year: [] for year in academic_years}
                    
                    for college_name, academic_year in colleges_with_exams:
                        exams_by_year[academic_year].append(college_name)
                    
                    tabs = st.tabs(academic_years)
                    for i, year in enumerate(academic_years):
                        with tabs[i]:
                            if exams_by_year[year]:
                                st.write(f"**{len(set(exams_by_year[year]))} Colleges with {year} exams in this date range:**")
                                year_df = pd.DataFrame(sorted(set(exams_by_year[year])), columns=["College Name"])
                                st.dataframe(year_df)
                            else:
                                st.write(f"No colleges have {year} exams in this date range.")
                else:
                    st.write(f"No colleges have exams between {start_date.strftime('%B %d, %Y')} and {end_date.strftime('%B %d, %Y')}. Please verify that your dataset includes exam dates covering this range in a supported format (e.g., DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD, DD Mon YYYY).")
    
    except Exception as e:
        st.error(f"Error reading the file: {str(e)}. Please ensure the file is in a supported format (.ods, .xlsx, .csv) and contains the required data.")