from config import GEMINI_API_KEY
import pandas as pd
import google.generativeai as genai

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Load model
model = genai.GenerativeModel("gemini-3.1-flash-lite")


def generate_ai_insights(df):
    """
    Generates business insights using Gemini AI.

    Instead of sending the entire dataset,
    we send a compact statistical summary.
    """

    # ---------- Dataset Summary ----------

    summary = []

    summary.append(f"Rows: {len(df)}")
    summary.append(f"Columns: {len(df.columns)}")
    summary.append(f"Column Names: {list(df.columns)}")

    numeric_cols = df.select_dtypes(include="number").columns
    categorical_cols = df.select_dtypes(include="object").columns
    date_cols = df.select_dtypes(include=["datetime64[ns]"]).columns

    # Numeric Summary
    for col in numeric_cols:
        summary.append(f"\nNumeric Column: {col}")
        summary.append(df[col].describe().to_string())

    # Categorical Summary
    for col in categorical_cols:
        summary.append(f"\nCategorical Column: {col}")
        summary.append(df[col].value_counts().head(5).to_string())

    # Date Summary
    for col in date_cols:
        summary.append(f"\nDate Column: {col}")
        summary.append(
            f"From {df[col].min()} to {df[col].max()}"
        )

    dataset_summary = "\n".join(summary)

    # ---------- Prompt ----------

    prompt = f"""
You are an experienced Senior Data Analyst.

Below is a statistical summary of a dataset.

{dataset_summary}

Your task is to generate ONLY business insights.

Rules:

- Do NOT mention missing values.
- Do NOT mention duplicates.
- Do NOT mention preprocessing.
- Do NOT mention data cleaning.
- Do NOT invent information.
- Generate insights ONLY if supported by the summary.
- Use numbers wherever possible.
- Maximum 8 bullet points.
- Each insight should be one sentence.
- Sound like insights written in a business report.
- Date and timestamp columns should be treated only as timeline fields, not as business metrics.
- If a date/timestamp column is paired with a valid business metric (such as Sales, Revenue, Profit, Orders, Quantity, Cost, Applicants, Customers, or similar), use it only to generate time-based insights such as trends, growth or decline, seasonality, peak periods, comparisons across time, and dataset coverage.
- Never calculate totals, averages, medians, skewness, quartiles, maximums, minimums, or any other statistical summaries directly on timestamp values.
- If a timestamp column is a technical or system-generated field (for example: created_at, updated_at, modified_at, last_login, timestamp, created_on, updated_on, inserted_at), and it is not associated with a valid business metric, ignore it completely and do not generate any insight from it.

Return ONLY bullet points.
"""

    # ---------- Gemini ----------

    try:
        response = model.generate_content(prompt)

        if response.text:
            insights = []

            for line in response.text.split("\n"):
                line = line.strip()

                if not line:
                    continue

                line = line.lstrip("-•* ")

                if line:
                    insights.append(line)

            return insights

        return ["No meaningful insights could be generated."]

    except Exception as e:
        return [f"Gemini Error: {str(e)}"]
 