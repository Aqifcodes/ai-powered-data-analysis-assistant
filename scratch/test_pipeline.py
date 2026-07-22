import os
import sys
import pandas as pd
import numpy as np

# Add the parent directory to sys.path so we can import utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.data_processor import clean_and_preprocess
from utils.dashboard_helper import generate_dataset_info, generate_kpis, generate_insights

def run_tests():
    print("==================================================")
    print("RUNNING AUTOMATED PIPELINE TESTS")
    print("==================================================")
    
    # 1. CREATE MOCK CSV DATA
    # We create a dictionary that mimics a real messy business dataset
    mock_data = {
        "Transaction_ID": ["T101", "T102", "T103", "T104", "T105", "T106", "T107", "T107", "T108", "T109"],
        "Date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", None, "2026-01-06", "2026-01-07", "2026-01-07", "2026-01-08", "2026-01-09"],
        "Department": ["Sales", "Engineering", "Marketing", "Sales", "Engineering", None, "Marketing", "Marketing", "Sales", "Engineering"],
        # Salary contains a missing value and a massive outlier (500,000) -> should trigger Median Imputation
        "Salary": [50000.0, 120000.0, 75000.0, 52000.0, 130000.0, None, 80000.0, 80000.0, 500000.0, 70000.0],
        # Rating contains a missing value but no outliers -> should trigger Mean Imputation
        "Rating": [4.2, 4.5, 3.8, 4.0, 4.7, 4.1, 4.3, 4.3, 4.5, None],
        # Is_Active contains boolean values
        "Is_Active": ["True", "False", "True", "True", "False", "True", "False", "False", "True", "True"]
    }
    
    df_raw = pd.DataFrame(mock_data)
    print(f"Raw DataFrame created with {len(df_raw)} rows and {len(df_raw.columns)} columns.")
    print("Checking raw null counts:\n", df_raw.isna().sum())
    
    # Calculate initial missing value percentage
    total_cells = df_raw.size
    total_missing = df_raw.isna().sum().sum()
    original_missing_pct = (total_missing / total_cells) * 100
    
    # 2. RUN CLEANING AND PREPROCESSING
    print("\n--- Running Preprocessing Pipeline ---")
    cleaned_df, column_types, logs = clean_and_preprocess(df_raw)
    
    print("\nPreprocessing Logs:")
    for log in logs:
        print(f" - {log}")
        
    print("\nDetected Column Types:")
    for col, col_type in column_types.items():
        print(f" - {col}: {col_type}")

    # 3. VERIFY DEDUPLICATION
    # The raw data has a duplicate row at index 6 and 7 (T107)
    # Total rows should go from 10 to 9 after deduplication
    assert len(cleaned_df) == 9, f"Deduplication failed! Expected 9 rows, got {len(cleaned_df)}"
    print("\n[PASS] Deduplication verified (rows reduced from 10 to 9).")

    # 4. VERIFY DATE DETECTION & CONVERSION
    assert column_types['Date'] == 'date', f"Date column not detected! Got {column_types['Date']}"
    assert pd.api.types.is_datetime64_any_dtype(cleaned_df['Date']), "Date column conversion failed!"
    print("[PASS] Date column detection and conversion verified.")

    # 5. VERIFY ID COLUMN DETECTION
    assert column_types['Transaction_ID'] == 'id', f"ID column not detected! Got {column_types['Transaction_ID']}"
    print("[PASS] ID column detection verified.")

    # 6. VERIFY OUTLIER DETECTION AND IMPUTATION SELECTOR
    # Salary has outliers (500000 is way above Q3 + 1.5*IQR). It should use Median Imputation.
    # The median of non-null Salary (after removing the duplicate row) is 77500.0. Let's verify the filled value.
    salary_imputed_val = cleaned_df.loc[5, 'Salary'] # Index 5 was None in Salary
    assert salary_imputed_val == 77500.0, f"Salary imputation failed! Expected Median (77500.0), got {salary_imputed_val}"
    
    # Check that a log for Median Imputation was recorded
    salary_log_found = any("Median Imputation" in log and "Salary" in log for log in logs)
    assert salary_log_found, "Salary median imputation not logged correctly!"
    print("[PASS] Outlier-based Median Imputation verified for Salary.")

    # Rating has no outliers. It should use Mean Imputation.
    # Ratings are: 4.2, 4.5, 3.8, 4.0, 4.7, 4.1, 4.3, 4.5. (Mean of these 8 values is 4.2625, rounded to 4.26)
    # The 9th value (at index 9) was None. Let's verify the filled value.
    rating_imputed_val = cleaned_df.loc[9, 'Rating']
    assert rating_imputed_val == 4.26, f"Rating imputation failed! Expected Mean (4.26), got {rating_imputed_val}"
    
    # Check that a log for Mean Imputation was recorded
    rating_log_found = any("Mean Imputation" in log and "Rating" in log for log in logs)
    assert rating_log_found, "Rating mean imputation not logged correctly!"
    print("[PASS] Mean Imputation verified for Rating.")

    # Department is categorical, missing value at index 5 should use Mode Imputation.
    # Department modes: Sales (3 times: index 0, 3, 8), Engineering (3 times: index 1, 4, 9), Marketing (2 times: index 2, 6 after drop).
    # Since Sales and Engineering are tied, mode could be Sales or Engineering. Let's check that it filled with one of them.
    dept_imputed_val = cleaned_df.loc[5, 'Department']
    assert dept_imputed_val in ['Sales', 'Engineering'], f"Department imputation failed! Expected Sales or Engineering, got {dept_imputed_val}"
    print("[PASS] Categorical Mode Imputation verified for Department.")

    # 7. VERIFY METADATA AND KPIS
    info = generate_dataset_info(cleaned_df, "test_file.csv", original_missing_pct)
    print("\nDataset Info Panel Summary:")
    for k, v in info.items():
        print(f" - {k}: {v}")
        
    assert info['rows'] == 9
    assert info['cols'] == 6
    assert info['missing_pct'] != "0.00%"
    print("[PASS] Dataset metadata generation verified.")

    kpis = generate_kpis(cleaned_df, column_types)
    print("\nGenerated KPIs:")
    for kpi in kpis:
        print(f" - {kpi['label']}: {kpi['value']} (icon: {kpi['icon']}, color: {kpi['color']})")
        
    # Should find Salary average KPI
    salary_kpi_found = any("Salary" in kpi['label'] for kpi in kpis)
    assert salary_kpi_found, "Salary KPI was not generated!"
    print("[PASS] Domain-specific KPI generation verified.")

    # 8. VERIFY KEY INSIGHTS GENERATION
    insights = generate_insights(cleaned_df, column_types)
    print(f"\nGenerated Insights ({len(insights)}):")
    for ins in insights:
        print(f" - {ins}")

    assert len(insights) > 0, "No insights were generated for the HR sample dataset!"
    assert all(isinstance(ins, str) and len(ins) > 0 for ins in insights), \
        "Insights must be non-empty strings!"
    print("[PASS] Key insights generation verified.")

    print("\n==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
