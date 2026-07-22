# AI-Powered Data Analysis Assistant

An AI-assisted Data Analyst portfolio project that automates the data preparation and analysis workflow. Users can upload any CSV dataset, and the application automatically cleans the data, detects column types, generates relevant KPI cards, produces AI-powered business insights, and allows the cleaned dataset to be downloaded for further analysis.

---

## 🚀 Key Features

1. **Automatic Dataset Inspection**
   - Detects dataset dimensions, missing values, duplicate rows, and inferred column types.

2. **Intelligent Data Cleaning**
   - Removes duplicate records.
   - Automatically imputes missing values.
   - Uses Mean or Median imputation based on outlier detection.
   - Fills categorical values using Mode.

3. **Automatic Data Type Detection**
   - Identifies Numeric, Categorical, Boolean, Date, and Identifier columns dynamically.

4. **Dynamic KPI Generation**
   - Generates relevant KPI cards based on the uploaded dataset instead of using fixed metrics.

5. **AI-Powered Insight Generation**
   - Uses Google's Gemini API to generate business-friendly insights from dataset summaries rather than hardcoded rules.

6. **Dataset Preview**
   - Displays a preview of the cleaned dataset before download.

7. **Cleaned CSV Export**
   - Allows users to download the processed dataset for further analysis.

---

## 🛠️ Tech Stack

- Python
- Flask
- Pandas
- NumPy
- Google Gemini API

---

## 📂 Project Directory Structure

```
Project/
│
├── app.py
├── config.py
├── requirements.txt
├── README.md
│
├── templates/
│   └── index.html
│
├── static/
│   ├── css/
│   └── js/
│
├── uploads/
│
└── utils/
    ├── data_processor.py
    ├── analytics_engine.py
    └── ai_insights.py
```

---

## 📊 Inside the Logic: Backend Workflow

When a user uploads a CSV file, the application follows the workflow below:

### Step 1: File Upload & Validation
- The uploaded file is received through the Flask backend.
- The system checks whether the file is a valid CSV.
- Empty or invalid files are rejected with appropriate error messages.

### Step 2: Dataset Loading
- The CSV is loaded into a Pandas DataFrame.
- Basic information such as the number of rows, columns, and missing values is collected.

### Step 3: Automatic Data Cleaning
The preprocessing engine automatically performs:

- Removal of duplicate records
- Missing value detection
- Adaptive missing value imputation
  - Uses **Median** when outliers are detected.
  - Uses **Mean** when the data is normally distributed.
- Mode imputation for categorical columns.
- Automatic date conversion where applicable.

### Step 4: Column Type Detection
The application automatically identifies each column as:

- Numeric
- Categorical
- Boolean
- Date
- Identifier (ID)

This allows the system to adapt its analysis to different datasets without requiring predefined schemas.

### Step 5: KPI Generation
Based on the detected column types, the application generates dataset-specific KPI cards such as:

- Total Records
- Total Features
- Missing Values
- Average Values
- Business Metrics (when applicable)

The KPIs change automatically depending on the uploaded dataset.

### Step 6: AI Insight Generation
Instead of relying on fixed rules, the application prepares a lightweight summary of the cleaned dataset containing:

- Column names
- Data types
- Missing values
- Descriptive statistics
- Category distributions

This summarized information is sent to the Gemini API, which generates business-friendly analytical insights tailored to the uploaded dataset.

### Step 7: Dataset Preview
The cleaned dataset is displayed in an interactive preview table so users can inspect the processed data before downloading it.

### Step 8: Export
Finally, users can download the cleaned CSV file for further analysis or visualization in external tools such as Excel, Power BI, or Tableau.

---

### 🔒 Privacy & Security

Data privacy is considered throughout the analysis process.

- The uploaded dataset is processed locally by the Flask application for cleaning, preprocessing, and KPI generation.
- Only a **summarized representation** of the cleaned dataset (such as column names, data types, descriptive statistics, and aggregated distributions) is sent to the Gemini API for generating analytical insights.
- Individual records and personally identifiable information (PII) are not intentionally included in the AI prompt.
- Uploaded files are stored only temporarily during processing and are automatically removed after the analysis is completed or the cleaned file is downloaded.
- No datasets are permanently stored by the application.

## 💻 How to Install and Run Locally

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd ai-data-analysis-assistant
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Gemini API**
   Create a `config.py` file in the project root and add:

   ```python
   GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
   ```

4. **Run the Application**
   ```bash
   python app.py
   ```

5. **Open the Application**
   Visit:

   ```
   http://127.0.0.1:5000
   ```

6. **Upload Any CSV Dataset**
   Upload your own CSV file, review the generated KPIs and AI-powered insights, then download the cleaned dataset.

## 🎯 Benefits

- Saves significant time by automating repetitive data cleaning and preprocessing tasks.
- Generates AI-powered business insights within seconds, reducing manual analysis effort.
- Adapts automatically to different dataset structures without requiring custom code.
- Helps users identify key trends, KPIs, and data quality issues quickly.
- Enables analysts to download a cleaned dataset for further analysis or reporting.
- Provides an intuitive interface that allows both technical and non-technical users to analyze datasets easily

## 🔮 Future Scope

- Add secure user authentication and personalized user accounts.
- Store analysis history for each user individually.
- Allow users to reopen previous analyses and view the complete report without reprocessing the dataset.
- Integrate support for locally hosted AI models to generate insights while keeping sensitive data entirely on the user's device.