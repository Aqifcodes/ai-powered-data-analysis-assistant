import pandas as pd
import numpy as np
import re


# Columns whose names suggest duration/measurement — never treat as calendar dates
_DATE_NAME_EXCLUSIONS = (
    'studytime', 'traveltime', 'freetime', 'runtime', 'playtime',
    'waittime', 'wait_time', 'responsetime', 'response_time',
    'processingtime', 'processing_time', 'cycletime', 'cycle_time',
    'elapsedtime', 'elapsed_time', 'leadtime', 'lead_time',
    'age', 'score', 'quantity', 'amount', 'price', 'salary', 'rating',
    'count', 'duration', 'latency', 'tenure', 'experience', 'units',
)

# Name fragments that support date classification (supporting evidence only)
_DATE_NAME_HINTS = (
    'date', 'timestamp', 'datetime', 'dob', 'birth_date', 'year_month',
    'order_date', 'invoice_date', 'purchase_date', 'joining_date', 'hire_date',
    'created_at', 'updated_at', 'modified_at', 'deleted_at', 'posted_at',
    'transaction_date', 'payment_date', 'ship_date', 'delivery_date',
    'start_date', 'end_date', 'due_date', 'expiry_date', 'expiration_date',
)


def _normalize_col_name(col_name):
    """Normalize a column name for keyword matching."""
    return re.sub(r'[\s\-]+', '_', str(col_name).lower().strip())


def _is_date_name_excluded(col_name):
    """
    Return True when the column name clearly refers to a measurement or
    duration rather than a calendar date (e.g. studytime, runtime, age).
    """
    col_lower = _normalize_col_name(col_name)

    for exclusion in _DATE_NAME_EXCLUSIONS:
        if col_lower == exclusion:
            return True
        if col_lower.endswith(f'_{exclusion}') or col_lower.startswith(f'{exclusion}_'):
            return True

    # Generic *time suffixes are durations unless they are timestamp/datetime-style names
    if col_lower.endswith('time') and not any(
        hint in col_lower for hint in ('timestamp', 'datetime', 'date', '_at')
    ):
        return True

    return False


def _has_date_name_hint(col_name):
    """
    Return True when the column name provides supporting evidence that the
    column may hold calendar dates. Name alone is never sufficient.
    """
    col_lower = _normalize_col_name(col_name)

    if any(hint in col_lower for hint in _DATE_NAME_HINTS):
        return True

    # Common audit-style suffix: created_at, updated_at, etc.
    if re.search(r'_(at|on)$', col_lower) and len(col_lower) > 3:
        return True

    return False


def _validate_parsed_dates(parsed_dates, original_series):
    """
    Reject parsed dates that look like epoch artifacts or other false positives.
    When uncertain, return False so the column stays unchanged.
    """
    valid_dates = parsed_dates.dropna()
    if len(valid_dates) == 0:
        return False

    years = valid_dates.dt.year

    # Mostly 1970 → likely Unix epoch from integers or small numbers
    if (years == 1970).sum() / len(valid_dates) > 0.5:
        return False

    # Clustered around the Unix epoch window
    epoch_window = (
        (valid_dates >= pd.Timestamp('1970-01-01')) &
        (valid_dates <= pd.Timestamp('1970-02-01'))
    )
    if epoch_window.sum() / len(valid_dates) > 0.8:
        return False

    # Digit-only source values often become artificial 1970 dates when coerced
    orig = original_series.dropna().astype(str).str.strip()
    digit_only = orig.str.fullmatch(r'\d+')
    if digit_only.any():
        digit_ratio = digit_only.sum() / len(orig)
        if digit_ratio >= 0.5:
            try:
                nums = orig[digit_only].astype(float)
                median_num = nums.median()
                median_year = years.median()

                # Small integers (scores, counts, IDs) → reject if they map near epoch
                if median_num < 10000 and median_year <= 1971:
                    return False

                # Large integers without a plausible calendar spread → reject
                if median_num >= 1e9:
                    reasonable_year_share = ((years >= 1990) & (years <= 2100)).sum() / len(valid_dates)
                    if reasonable_year_share < 0.8:
                        return False
            except (ValueError, TypeError):
                return False

    # Require a mostly plausible calendar range
    plausible = ((years >= 1900) & (years <= 2100)).sum() / len(valid_dates)
    if plausible < 0.8:
        return False

    # Very low year variance with digit-only inputs suggests accidental parsing
    if years.nunique() <= 2 and digit_only.sum() / max(len(orig), 1) >= 0.8:
        if years.min() <= 1971:
            return False

    return True


def _is_likely_date_column(series):
    """
    Attempt datetime parsing on a non-numeric column and classify it as a date
    only when parsing is successful, validated, and unambiguous.
    """
    if pd.api.types.is_numeric_dtype(series):
        return False

    non_null = series.dropna()
    if len(non_null) == 0:
        return False

    # Only string/object columns are candidates
    if not (
        pd.api.types.is_object_dtype(series) or
        pd.api.types.is_string_dtype(series)
    ):
        return False

    parsed = pd.to_datetime(series, errors='coerce', utc=False)

    # Require at least 80% of non-null values to parse successfully
    parse_success_rate = parsed.notna().sum() / len(non_null)
    if parse_success_rate < 0.8:
        return False

    if not _validate_parsed_dates(parsed, series):
        return False

    return True


def detect_column_types(df):
    """
    Intelligently detects the data type of each column in the DataFrame.
    Categorizes columns into: 'date', 'boolean', 'id', 'numeric', or 'categorical'.
    
    This helps the application decide how to impute missing values and what metrics
    to calculate.
    """
    column_types = {}
    
    # We loop through each column in the DataFrame
    for col in df.columns:
        # Get the non-null values for analysis
        non_null_values = df[col].dropna()
        
        # If the column is completely empty, default to categorical
        if len(non_null_values) == 0:
            column_types[col] = 'categorical'
            continue
            
        col_lower = _normalize_col_name(col)
        is_numeric = pd.api.types.is_numeric_dtype(df[col])
        
        # 1. DETECT DATE COLUMNS
        # Only attempt datetime conversion on non-numeric (object/string) columns.
        if not is_numeric and not _is_date_name_excluded(col):
            # Use column name hints as supporting evidence, but require successful parsing.
            if _is_likely_date_column(df[col]):
                column_types[col] = 'date'
                continue

        # 2. DETECT BOOLEAN COLUMNS
        # Boolean columns contain binary values (True/False, 1/0, Yes/No)
        # We check if the set of unique values is a subset of standard boolean representations
        unique_vals = set(non_null_values.unique())
        boolean_representations = {True, False, 1, 0, '1', '0', 'True', 'False', 'true', 'false', 'Yes', 'No', 'yes', 'no'}
        
        if unique_vals.issubset(boolean_representations) and len(unique_vals) <= 2:
            column_types[col] = 'boolean'
            continue

        # 3. DETECT ID COLUMNS
        # Rule A: Column name contains ID keywords
        has_id_keyword = any(kw in col_lower for kw in ['id', 'key', 'code', 'number', 'invoice', 'order_id', 'customer_id'])
        
        # Rule B: Values are nearly 100% unique (cardinality is extremely high, indicating a unique identifier)
        is_nearly_unique = (df[col].nunique() / len(df)) >= 0.95
        
        # Rule C: Check if values are sequential integers (e.g. 1, 2, 3, 4...)
        is_sequential = False
        if is_numeric and pd.api.types.is_integer_dtype(df[col]):
            sorted_vals = np.sort(non_null_values.unique())
            if len(sorted_vals) > 1:
                # If the difference between consecutive sorted values is always 1, it's sequential
                diffs = np.diff(sorted_vals)
                if np.all(diffs == 1):
                    is_sequential = True
        
        if (has_id_keyword or is_nearly_unique or is_sequential) and not is_numeric:
            # If it's a string unique key or has ID keyword
            column_types[col] = 'id'
            continue
        elif has_id_keyword or is_sequential:
            # If it's a numeric ID column
            column_types[col] = 'id'
            continue

        # 4. DETECT NUMERIC COLUMNS
        # Standard Pandas check for integer or float data types
        if pd.api.types.is_numeric_dtype(df[col]):
            column_types[col] = 'numeric'
            continue

        # 5. FALLBACK TO CATEGORICAL
        # If the column doesn't match any of the above, it's treated as categorical (text/labels)
        column_types[col] = 'categorical'
        
    return column_types


def clean_and_preprocess(df):
    """
    Cleans the input DataFrame by performing duplicate removal and
    adaptive missing value imputation.
    
    Returns:
        cleaned_df: The cleaned Pandas DataFrame
        column_types: A dictionary mapping columns to their detected types
        summary_logs: A list of string messages detailing the operations performed
    """
    # Create a copy so we do not modify the original data directly
    cleaned_df = df.copy()
    summary_logs = []
    
    # --- STEP 1: DUPLICATE ROW REMOVAL ---
    # We find duplicate rows across all columns
    duplicate_count = cleaned_df.duplicated().sum()
    if duplicate_count > 0:
        # Drop duplicates, keeping only the first occurrence
        cleaned_df.drop_duplicates(inplace=True)
        summary_logs.append(f"Detected and removed {duplicate_count} duplicate row(s).")
    else:
        summary_logs.append("No duplicate rows detected.")

    # --- STEP 2: COLUMN DETECTION ---
    # Intelligently detect column types after removing duplicates
    column_types = detect_column_types(cleaned_df)
    
    # --- STEP 3: CONVERT DATE COLUMNS ---
    for col, col_type in column_types.items():
        if col_type == 'date':
            # Convert values to standard Datetime objects. Unparseable values are turned to NaT (Not a Time)
            before_nulls = cleaned_df[col].isna().sum()
            cleaned_df[col] = pd.to_datetime(cleaned_df[col], errors='coerce')
            after_nulls = cleaned_df[col].isna().sum()
            
            summary_logs.append(f"Converted column '{col}' to Datetime.")
            # If conversion introduced new nulls (unparseable dates), we log it
            new_nulls = after_nulls - before_nulls
            if new_nulls > 0:
                summary_logs.append(f"Warning: {new_nulls} values in '{col}' could not be parsed as dates and are set to missing.")

    # --- STEP 4: MISSING VALUE IMPUTATION ---
    for col in cleaned_df.columns:
        missing_count = cleaned_df[col].isna().sum()
        
        # If there are no missing values, we don't need to impute anything
        if missing_count == 0:
            continue
            
        col_type = column_types[col]
        
        if col_type == 'numeric':
            # --- OUTLIER DETECTION USING IQR (INTERQUARTILE RANGE) ---
            # 1. Find the 25th percentile (Q1) and 75th percentile (Q3)
            q1 = cleaned_df[col].quantile(0.25)
            q3 = cleaned_df[col].quantile(0.75)
            
            # 2. Calculate the IQR (middle 50% range of the data)
            iqr = q3 - q1
            
            # 3. Calculate lower and upper outlier boundaries
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            # 4. Count the outliers in this column
            outliers = cleaned_df[(cleaned_df[col] < lower_bound) | (cleaned_df[col] > upper_bound)][col]
            outlier_count = len(outliers)
            
            # --- ADAPTIVE IMPUTATION ---
            if outlier_count > 0:
                # If there are outliers, the Mean (average) will be distorted.
                # We use the Median (middle value), which is robust to extreme values.
                median_value = cleaned_df[col].median()
                
                # In case the median is NaN (which happens if all values are NaN, though rare)
                if pd.isna(median_value):
                    median_value = 0
                
                cleaned_df[col] = cleaned_df[col].fillna(median_value)
                summary_logs.append(
                    f"Detected {missing_count} missing value(s) in '{col}'. "
                    f"Outliers detected using IQR ({outlier_count} outlier(s) found). "
                    f"Applied Median Imputation (Value: {median_value})."
                )
            else:
                # If there are no outliers, the Mean represents the central tendency accurately.
                mean_value = cleaned_df[col].mean()
                
                if pd.isna(mean_value):
                    mean_value = 0
                
                # Round to 2 decimal places for cleaner presentation
                mean_value = round(float(mean_value), 2)
                
                cleaned_df[col] = cleaned_df[col].fillna(mean_value)
                summary_logs.append(
                    f"Detected {missing_count} missing value(s) in '{col}'. "
                    f"No significant outliers found. "
                    f"Applied Mean Imputation (Value: {mean_value})."
                )
                
        elif col_type in ['categorical', 'boolean', 'id']:
            # --- MODE IMPUTATION FOR CATEGORICAL/BOOLEAN/ID ---
            # Mode represents the most frequent value.
            mode_series = cleaned_df[col].mode()
            
            if not mode_series.empty:
                mode_value = mode_series[0]
            else:
                mode_value = "Unknown"
                
            cleaned_df[col] = cleaned_df[col].fillna(mode_value)
            summary_logs.append(
                f"Detected {missing_count} missing value(s) in '{col}' (type: {col_type}). "
                f"Applied Mode Imputation (Value: '{mode_value}')."
            )
            
        elif col_type == 'date':
            # --- DATE IMPUTATION ---
            # For date columns, we impute missing values with the most common date (Mode)
            mode_series = cleaned_df[col].mode()
            if not mode_series.empty:
                mode_date = mode_series[0]
                cleaned_df[col] = cleaned_df[col].fillna(mode_date)
                summary_logs.append(
                    f"Detected {missing_count} missing date(s) in '{col}'. "
                    f"Imputed using Mode Date (Value: {mode_date.strftime('%Y-%m-%d')})."
                )
            else:
                # If no mode exists, we leave them or drop them. Let's leave them.
                summary_logs.append(f"Detected {missing_count} missing date(s) in '{col}'. Left as missing.")
                
    return cleaned_df, column_types, summary_logs
