import pandas as pd
import numpy as np
import re

# -------------------------------------------------------------------------
# Column Classification Constants and Helper Functions
# -------------------------------------------------------------------------

BUSINESS_KEYWORDS = [
    'sales', 'revenue', 'profit', 'amount', 'price', 'cost',
    'salary', 'income', 'rating', 'score', 'marks',
    'quantity', 'units', 'age', 'experience', 'attendance', 'absences'
]

DATE_NAME_HINTS = [
    'date', 'created_at', 'updated_at', 'modified_at',
    'timestamp', 'purchase_date', 'order_date', 'joining_date',
    'hire_date'
]

ID_KEYWORDS = [
    'id', 'key', 'code', 'number', 'invoice', 'phone', 'zip',
    'postal', 'reference', 'client', 'customer', 'order', 'application'
]

def _classify_columns(column_types, df):
    """
    Refine column classification into:
    - business_metric
    - date
    - identifier
    - boolean
    - categorical
    - numeric_other (numeric but not a metric)
    """
    classification = {}
    for col, typ in column_types.items():
        col_lower = col.lower()
        if typ == 'date':
            classification[col] = 'date'
        elif typ == 'boolean':
            classification[col] = 'boolean'
        elif typ == 'id':
            classification[col] = 'identifier'
        elif typ == 'categorical':
            classification[col] = 'categorical'
        elif typ == 'numeric':
            if any(kw in col_lower for kw in ID_KEYWORDS):
                classification[col] = 'identifier'
            elif any(kw in col_lower for kw in DATE_NAME_HINTS):
                classification[col] = 'date'
            elif any(kw in col_lower for kw in BUSINESS_KEYWORDS):
                classification[col] = 'business_metric'
            else:
                series = df[col].dropna()
                if pd.api.types.is_integer_dtype(series):
                    parsed = pd.to_datetime(series, errors='coerce', unit='s')
                    years = parsed.dt.year
                    if years.notna().mean() > 0.8 and (years == 1970).sum() / len(years) > 0.5:
                        classification[col] = 'date'
                    else:
                        classification[col] = 'numeric_other'
                else:
                    classification[col] = 'numeric_other'
        else:
            classification[col] = 'unknown'
    return classification


# =============================================================================
# COLUMN SCORING ENGINE
# =============================================================================

def score_numeric_column(df, col):
    """
    Scores a numeric column from 0 to 100 based on how informative it is.

    Higher scores mean the column is more suitable for visualization.
    We penalise columns that look like IDs (sequential integers, very
    high cardinality) and reward columns with meaningful variance and
    good completeness.

    Scoring factors:
        - Completeness  (% non-null values)
        - Variance      (std-dev / mean, i.e. coefficient of variation)
        - Unique value count (more unique values = more distribution to show)
        - Business-keyword bonus (salary, revenue, amount, etc.)
        - ID-like column penalty
    """
    series = df[col].dropna()

    # If fewer than 3 non-null values the column is useless for charts
    if len(series) < 3:
        return 0

    col_lower = col.lower()

    # 1. COMPLETENESS (0–30 points)
    completeness = series.count() / len(df)
    completeness_score = completeness * 30

    # 2. VARIANCE / SPREAD (0–30 points)
    # Coefficient of variation = std / |mean|. Capped at 1 for scoring.
    mean_val = series.mean()
    std_val = series.std()
    if mean_val != 0 and not np.isnan(std_val):
        cv = min(std_val / abs(mean_val), 1.0)
    else:
        cv = 0.0
    variance_score = cv * 30

    # 3. UNIQUE VALUE COUNT (0–20 points)
    # We want columns with at least a handful of distinct values (not binary flags)
    unique_count = series.nunique()
    unique_score = min(unique_count / max(len(df) * 0.5, 1), 1.0) * 20

    # 4. BUSINESS-KEYWORD BONUS (+15 points)
    business_keywords = [
        'revenue', 'sales', 'amount', 'profit', 'income', 'cost',
        'price', 'salary', 'wage', 'quantity', 'units', 'orders',
        'rating', 'score', 'age', 'total', 'budget', 'spend'
    ]
    keyword_bonus = 15 if any(kw in col_lower for kw in business_keywords) else 0

    # 5. ID-LIKE COLUMN PENALTY (-50 points, effectively disqualifies)
    id_keywords = ['id', 'key', 'code', 'number', 'invoice', 'phone', 'zip', 'postal']
    is_id_keyword = any(kw == col_lower or col_lower.endswith('_' + kw) or col_lower.startswith(kw + '_')
                        for kw in id_keywords)
    # Also penalise if 95%+ of values are unique integers (primary key pattern)
    is_unique_int = (
        pd.api.types.is_integer_dtype(df[col]) and
        (unique_count / len(df)) >= 0.95
    )
    id_penalty = 50 if (is_id_keyword or is_unique_int) else 0

    total = completeness_score + variance_score + unique_score + keyword_bonus - id_penalty
    return max(total, 0)


def score_categorical_column(df, col):
    """
    Scores a categorical column from 0 to 100 based on how suitable it
    is as a grouping axis in charts.

    Good categorical columns have:
        - Low-to-moderate number of unique categories (2–20)
        - High completeness (few missing values)
        - Business-relevant names (department, category, region, etc.)

    We strongly penalise columns with too many categories (hard to read
    in a bar chart) or columns that are essentially free-text fields.
    """
    series = df[col].dropna()

    if len(series) == 0:
        return 0

    col_lower = col.lower()
    n_unique = series.nunique()
    n_total = len(df)

    # 1. UNIQUE VALUE COUNT SWEET-SPOT (0–40 points)
    # Ideal range: 2–15 unique categories. Penalise extremes.
    if n_unique < 2:
        cardinality_score = 0          # Only one value — useless
    elif n_unique <= 8:
        cardinality_score = 40         # Perfect for pie/bar
    elif n_unique <= 15:
        cardinality_score = 30         # Good for bar
    elif n_unique <= 25:
        cardinality_score = 15         # Marginal
    else:
        cardinality_score = 0          # Too many categories — skip

    # 2. COMPLETENESS (0–30 points)
    completeness = series.count() / n_total
    completeness_score = completeness * 30

    # 3. BUSINESS-KEYWORD BONUS (+20 points)
    business_keywords = [
        'category', 'type', 'department', 'region', 'country', 'city',
        'gender', 'status', 'segment', 'product', 'brand', 'channel',
        'grade', 'level', 'group', 'class', 'industry', 'team'
    ]
    keyword_bonus = 20 if any(kw in col_lower for kw in business_keywords) else 0

    # 4. ID/NAME FIELD PENALTY (-40 points)
    id_name_keywords = ['id', 'name', 'email', 'phone', 'address', 'description', 'notes', 'comment']
    id_name_penalty = 40 if any(kw in col_lower for kw in id_name_keywords) else 0

    total = cardinality_score + completeness_score + keyword_bonus - id_name_penalty
    return max(total, 0)


def get_best_numeric_columns(df, column_types, min_score=10):
    """
    Returns a ranked list of (column_name, score) tuples for all numeric
    columns, sorted from most informative to least.

    Only columns with a score above min_score are returned.
    This list drives histogram, scatter, box plot, and heatmap decisions.
    """
    numeric_cols = [col for col, t in column_types.items() if t == 'numeric']
    scored = []
    for col in numeric_cols:
        s = score_numeric_column(df, col)
        if s >= min_score:
            scored.append((col, s))
    # Sort descending by score
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def get_best_categorical_columns(df, column_types, min_score=10):
    """
    Returns a ranked list of (column_name, score) tuples for all
    categorical and boolean columns, sorted from most informative to least.

    Only columns with a score above min_score are returned.
    This list drives bar chart, pie chart, and grouping decisions.
    """
    cat_types = ['categorical', 'boolean']
    cat_cols = [col for col, t in column_types.items() if t in cat_types]
    scored = []
    for col in cat_cols:
        s = score_categorical_column(df, col)
        if s >= min_score:
            scored.append((col, s))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


# =============================================================================
# DATASET INFO PANEL
# =============================================================================

def generate_dataset_info(df, filename, original_missing_pct=0.0):
    """
    Generates metadata statistics for the Dataset Information panel.
    """
    memory_bytes = df.memory_usage(deep=True).sum()
    if memory_bytes < 1024 * 1024:
        memory_str = f"{memory_bytes / 1024:.2f} KB"
    else:
        memory_str = f"{memory_bytes / (1024 * 1024):.2f} MB"

    from utils.data_processor import detect_column_types
    col_types = detect_column_types(df)

    counts = {'numeric': 0, 'categorical': 0, 'date': 0, 'boolean': 0, 'id': 0}
    for t in col_types.values():
        if t in counts:
            counts[t] += 1

    return {
        "filename": filename,
        "rows": len(df),
        "cols": len(df.columns),
        "size": memory_str,
        "numeric_count": counts['numeric'],
        "categorical_count": counts['categorical'],
        "date_count": counts['date'],
        "boolean_count": counts['boolean'],
        "id_count": counts['id'],
        "missing_pct": f"{original_missing_pct:.2f}%"
    }


# =============================================================================
# DYNAMIC KPI GENERATION
# =============================================================================

def generate_kpis(df, column_types):
    """
    Dynamically generates meaningful KPIs based on the detected dataset.

    Priority:
    1. Business KPIs (Revenue, Profit, Orders, Customers, etc.)
    2. Dataset KPIs
    3. Category KPIs

    Avg/Max are ONLY shown when a real business metric exists.
    """

    kpis = []

    classification = _classify_columns(column_types, df)

    business_metric_columns = [
        c for c, t in classification.items()
        if t == "business_metric"
    ]

    categorical_columns = [
        c for c, t in classification.items()
        if t == "categorical"
    ]

    # --------------------------------------------
    # Dataset KPIs (Always)
    # --------------------------------------------

    kpis.append({
        "label": "Total Records",
        "value": f"{len(df):,}",
        "icon": "fa-database",
        "color": "primary"
    })

    kpis.append({
        "label": "Total Features",
        "value": str(len(df.columns)),
        "icon": "fa-columns",
        "color": "info"
    })

    # --------------------------------------------
    # Top Category
    # --------------------------------------------

    if categorical_columns:

        best_cat = None
        best_score = -1

        for col in categorical_columns:

            nunique = df[col].nunique()

            if 2 <= nunique <= 50:

                mode = df[col].mode()

                if not mode.empty:

                    count = (df[col] == mode.iloc[0]).sum()

                    if count > best_score:
                        best_score = count
                        best_cat = col

        if best_cat:

            mode = df[best_cat].mode().iloc[0]
            count = (df[best_cat] == mode).sum()

            kpis.append({
                "label": f"Top {best_cat.replace('_',' ').title()}",
                "value": f"{mode} ({count:,} records)",
                "icon": "fa-bullseye",
                "color": "warning"
            })

    # --------------------------------------------
    # Business Metric KPIs
    # ONLY if business metric exists
    # --------------------------------------------

    if business_metric_columns:

        metric = business_metric_columns[0]

        avg_val = df[metric].mean()
        max_val = df[metric].max()

        kpis.append({
            "label": f"Avg {metric.replace('_',' ').title()}",
            "value": f"{avg_val:,.2f}",
            "icon": "fa-chart-line",
            "color": "success"
        })

        kpis.append({
            "label": f"Max {metric.replace('_',' ').title()}",
            "value": f"{max_val:,.2f}",
            "icon": "fa-arrow-up",
            "color": "danger"
        })

    return kpis

# =============================================================================
# KEY INSIGHTS GENERATION ENGINE
# =============================================================================

def _find_entity_column(column_types):
    """Find a customer/user entity column, preferring ID-type columns."""
    id_keywords = ['customer_id', 'user_id', 'client_id', 'employee_id', 'emp_id', 'staff_id']
    for col, col_type in column_types.items():
        col_lower = col.lower()
        if col_type == 'id' and any(
            col_lower == kw or col_lower.endswith('_' + kw) or col_lower.startswith(kw + '_')
            for kw in id_keywords
        ):
            return col
    return None


def generate_insights(df, column_types):
    """
    Inspects the cleaned dataset and generates human-readable analytical
    observations — the kind a Data Analyst would write in a report.

    Rules:
        - Every insight is derived directly from the data (no hardcoding).
        - An insight is only added when the required column actually exists
          AND the computation produces a meaningful result.
        - Insights describe the DATA, not preprocessing actions.
        - Output is a list of plain strings, one per bullet point.
    """
    insights = []

    # ---- helpers ---------------------------------------------------------- #

    def fmt_num(val):
        """Format a number neatly: comma-separated, 2 decimal places."""
        if val == int(val):
            return f"{int(val):,}"
        return f"{val:,.2f}"

    def col_label(col):
        """Human-readable column label."""
        return col.replace('_', ' ').title()

    # Bucketed column lists (IDs excluded by design via column_types)
    numeric_cols  = [c for c, t in column_types.items() if t == 'numeric']
    cat_cols      = [c for c, t in column_types.items() if t == 'categorical']
    date_cols     = [c for c, t in column_types.items() if t == 'date']
    bool_cols     = [c for c, t in column_types.items() if t == 'boolean']

    # ---- 1. DATASET COVERAGE (date range) --------------------------------- #
    if date_cols:
        date_col = date_cols[0]
        valid_dates = df[date_col].dropna()
        if len(valid_dates) > 0:
            min_date = valid_dates.min()
            max_date = valid_dates.max()
            if pd.notna(min_date) and pd.notna(max_date) and min_date != max_date:
                insights.append(
                    f"The dataset covers transactions from "
                    f"{min_date.strftime('%d %B %Y')} to {max_date.strftime('%d %B %Y')}."
                )

    # ---- 2. TOP & BOTTOM CATEGORY BY A NUMERIC METRIC --------------------- #
    # Find the best categorical column and best numeric column to pair them
    best_cats = get_best_categorical_columns(df, column_types, min_score=25)
    best_nums = get_best_numeric_columns(df, column_types, min_score=15)

    if best_cats and best_nums:
        grp_col = best_cats[0][0]
        num_col = best_nums[0][0]

        # Only proceed if we have a manageable number of categories
        n_unique = df[grp_col].nunique()
        if 2 <= n_unique <= 30:
            grouped = df.groupby(grp_col)[num_col].sum().sort_values(ascending=False)

            top_cat   = grouped.index[0]
            top_val   = grouped.iloc[0]
            bot_cat   = grouped.index[-1]
            bot_val   = grouped.iloc[-1]
            total_val = grouped.sum()

            if total_val > 0:
                top_pct = (top_val / total_val) * 100
                insights.append(
                    f"{top_cat} generated the highest total {col_label(num_col).lower()} "
                    f"({fmt_num(top_val)}) across all {col_label(grp_col).lower()} groups, "
                    f"contributing {top_pct:.1f}% of the overall total."
                )
                insights.append(
                    f"{bot_cat} recorded the lowest total {col_label(num_col).lower()} "
                    f"({fmt_num(bot_val)}) among all {col_label(grp_col).lower()} groups."
                )

            # ---- 3. TOP-N CONCENTRATION (Pareto-style insight) ------------ #
            if n_unique >= 4:
                top_n = max(2, int(np.ceil(n_unique * 0.2)))   # top 20% of categories
                top_n_sum = grouped.head(top_n).sum()
                if total_val > 0:
                    conc_pct = (top_n_sum / total_val) * 100
                    if conc_pct >= 50:
                        insights.append(
                            f"The top {top_n} {col_label(grp_col).lower()} group(s) account for "
                            f"{conc_pct:.1f}% of total {col_label(num_col).lower()}, "
                            f"indicating high concentration."
                        )

    # ---- 4. AVERAGE VALUE INSIGHT ----------------------------------------- #
    # Find a business-meaningful numeric column
    avg_keywords = ['amount', 'revenue', 'sales', 'price', 'cost', 'value', 'salary', 'wage']
    avg_col = None
    for col, _ in best_nums:
        if any(kw in col.lower() for kw in avg_keywords):
            avg_col = col
            break
    if not avg_col and best_nums:
        avg_col = best_nums[0][0]

    if avg_col:
        avg_val = df[avg_col].mean()
        insights.append(
            f"The average {col_label(avg_col).lower()} across all records is {fmt_num(avg_val)}."
        )

    # ---- 5. PEAK DATE INSIGHT --------------------------------------------- #
    if date_cols and best_nums:
        date_col  = date_cols[0]
        num_col   = best_nums[0][0]
        valid     = df[[date_col, num_col]].dropna()
        if len(valid) > 0:
            daily = valid.groupby(date_col)[num_col].sum()
            if len(daily) > 1:
                peak_date = daily.idxmax()
                peak_val  = daily.max()
                if pd.notna(peak_date):
                    insights.append(
                        f"{col_label(num_col)} reached its highest value of {fmt_num(peak_val)} "
                        f"on {peak_date.strftime('%d %B %Y')}."
                    )

    # ---- 6. TREND DIRECTION (increasing / decreasing / flat) -------------- #
    if date_cols and best_nums:
        date_col = date_cols[0]
        num_col  = best_nums[0][0]
        valid    = df[[date_col, num_col]].dropna().sort_values(date_col)
        if len(valid) >= 5:
            daily = valid.groupby(date_col)[num_col].sum().reset_index()
            if len(daily) >= 5:
                # Simple linear regression slope using numpy
                x = np.arange(len(daily))
                y = daily[num_col].values
                slope = np.polyfit(x, y, 1)[0]
                mean_y = y.mean()
                # Express slope as % of mean to judge significance
                if mean_y != 0:
                    rel_slope = (slope / mean_y) * 100
                    if rel_slope > 2:
                        insights.append(
                            f"{col_label(num_col)} shows an increasing trend over time."
                        )
                    elif rel_slope < -2:
                        insights.append(
                            f"{col_label(num_col)} shows a decreasing trend over time."
                        )

    # ---- 7. RATING / SCORE CONSISTENCY ------------------------------------ #
    rating_keywords = ['rating', 'score', 'feedback', 'review']
    rating_col = None
    for col in numeric_cols:
        if any(kw in col.lower() for kw in rating_keywords):
            rating_col = col
            break

    if rating_col:
        avg_r = df[rating_col].mean()
        max_r = df[rating_col].max()
        std_r = df[rating_col].std()
        consistency = "consistently high" if avg_r >= 0.75 * max_r else "moderate"
        rating_label = col_label(rating_col).lower()
        if std_r <= 0.5:
            insights.append(
                f"{col_label(rating_col)}s are {consistency}, "
                f"averaging {avg_r:.2f} out of {fmt_num(max_r)} with low variation (std: {std_r:.2f})."
            )
        else:
            insights.append(
                f"The average {rating_label} is {avg_r:.2f} out of {fmt_num(max_r)}."
            )

        # Rating consistency across categories
        if best_cats:
            grp_col = best_cats[0][0]
            if 2 <= df[grp_col].nunique() <= 15:
                cat_ratings = df.groupby(grp_col)[rating_col].mean()
                rating_range = cat_ratings.max() - cat_ratings.min()
                if rating_range < 0.5:
                    insights.append(
                        f"{col_label(rating_col)} remains consistent across all "
                        f"{col_label(grp_col).lower()} groups (range: {rating_range:.2f})."
                    )
                else:
                    best_grp = cat_ratings.idxmax()
                    insights.append(
                        f"{best_grp} has the highest average {col_label(rating_col).lower()} "
                        f"({cat_ratings.max():.2f}) among all {col_label(grp_col).lower()} groups."
                    )

    # ---- 8. DISTRIBUTION SKEWNESS ----------------------------------------- #
    if best_nums:
        skew_col = best_nums[0][0]
        series   = df[skew_col].dropna()
        if len(series) >= 10:
            skewness = series.skew()
            if skewness > 1.0:
                insights.append(
                    f"{col_label(skew_col)} distribution is positively skewed (skewness: {skewness:.2f}), "
                    f"indicating a small number of high-value records pulling the average upward."
                )
            elif skewness < -1.0:
                insights.append(
                    f"{col_label(skew_col)} distribution is negatively skewed (skewness: {skewness:.2f}), "
                    f"suggesting most values are concentrated at the higher end."
                )

    # ---- 9. TYPICAL VALUE RANGE (IQR-based) ------------------------------- #
    if best_nums:
        range_col = best_nums[0][0]
        series = df[range_col].dropna()
        if len(series) >= 10:
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            if q1 != q3:
                insights.append(
                    f"The majority of {col_label(range_col).lower()} values fall between "
                    f"{fmt_num(q1)} and {fmt_num(q3)} (interquartile range)."
                )

    # ---- 10. MOST FREQUENT CATEGORY --------------------------------------- #
    if best_cats:
        freq_col = best_cats[0][0]
        if df[freq_col].nunique() <= 20:
            mode_val   = df[freq_col].mode()
            if not mode_val.empty:
                top_val  = mode_val[0]
                top_cnt  = int((df[freq_col] == top_val).sum())
                total_r  = len(df)
                top_pct  = (top_cnt / total_r) * 100
                insights.append(
                    f"'{top_val}' is the most frequent {col_label(freq_col).lower()}, "
                    f"appearing in {top_cnt} out of {total_r} records ({top_pct:.1f}%)."
                )

    # ---- 11. REPEAT CUSTOMER / ENTITY DETECTION --------------------------- #
    entity_col = _find_entity_column(column_types)

    if entity_col:
        purchase_counts = df[entity_col].value_counts()
        single_purchase = int((purchase_counts == 1).sum())
        multi_purchase  = int((purchase_counts > 1).sum())
        total_entities  = len(purchase_counts)
        if total_entities > 0 and multi_purchase > 0:
            if single_purchase > multi_purchase:
                insights.append(
                    f"Most {col_label(entity_col).lower()}s made only one transaction, "
                    f"while {multi_purchase} placed multiple orders."
                )
            else:
                repeat_pct = (multi_purchase / total_entities) * 100
                insights.append(
                    f"{repeat_pct:.1f}% of {col_label(entity_col).lower()}s appear more than once, "
                    f"while {single_purchase} made only a single transaction."
                )

    # ---- 12. BOOLEAN COLUMN SPLIT ----------------------------------------- #
    if bool_cols:
        b_col = bool_cols[0]
        vc = df[b_col].value_counts()
        if len(vc) == 2:
            vals = list(vc.index)
            cnts = list(vc.values)
            total = sum(cnts)
            insights.append(
                f"{fmt_num(cnts[0])} records ({(cnts[0]/total*100):.1f}%) have "
                f"{col_label(b_col)} = '{vals[0]}', while {fmt_num(cnts[1])} "
                f"({(cnts[1]/total*100):.1f}%) have '{vals[1]}'."
            )

    # ---- 13. WEEKEND VS WEEKDAY COMPARISON -------------------------------- #
    if date_cols and best_nums:
        date_col = date_cols[0]
        num_col  = best_nums[0][0]
        valid    = df[[date_col, num_col]].dropna()
        if len(valid) >= 14:
            valid = valid.copy()
            valid['_is_weekend'] = valid[date_col].dt.dayofweek.isin([5, 6])
            weekend_avg = valid.loc[valid['_is_weekend'], num_col].mean()
            weekday_avg = valid.loc[~valid['_is_weekend'], num_col].mean()
            if weekday_avg > 0 and not np.isnan(weekend_avg):
                diff_pct = ((weekend_avg - weekday_avg) / weekday_avg) * 100
                if diff_pct >= 10:
                    metric = col_label(num_col).lower()
                    insights.append(
                        f"Weekend {metric} are noticeably higher than weekday {metric}."
                    )
                elif diff_pct <= -10:
                    metric = col_label(num_col).lower()
                    insights.append(
                        f"Weekday {metric} are noticeably higher than weekend {metric}."
                    )

    # ---- 14. TOP-N PRODUCT / ITEM CONCENTRATION --------------------------- #
    product_keywords = ['product', 'item', 'sku', 'product_name', 'item_name']
    product_col = None
    for col, _ in best_cats:
        if any(kw in col.lower() for kw in product_keywords):
            product_col = col
            break

    if product_col and best_nums:
        num_col = best_nums[0][0]
        grouped = df.groupby(product_col)[num_col].sum().sort_values(ascending=False)
        total   = grouped.sum()
        if len(grouped) >= 5 and total > 0:
            top5_pct = (grouped.head(5).sum() / total) * 100
            if top5_pct >= 50:
                insights.append(
                    f"The top 5 {col_label(product_col).lower()}s contribute "
                    f"{top5_pct:.1f}% of the total {col_label(num_col).lower()}."
                )

    # ---- 15. PREMIUM VS BUDGET SEGMENT COMPARISON ------------------------- #
    tier_keywords = ['tier', 'segment', 'price_band', 'price_range', 'level', 'grade', 'class']
    for col in cat_cols:
        col_lower = col.lower()
        if not any(kw in col_lower for kw in tier_keywords):
            unique_vals = df[col].dropna().astype(str).str.lower().unique()
            has_tier_vals = any(v in unique_vals for v in ['premium', 'budget', 'economy', 'standard', 'luxury'])
            if not has_tier_vals:
                continue
        if best_nums and 2 <= df[col].nunique() <= 10:
            num_col = best_nums[0][0]
            tier_sums = df.groupby(col)[num_col].sum()
            if len(tier_sums) >= 2:
                high_tier = None
                low_tier  = None
                for val in tier_sums.index:
                    val_lower = str(val).lower()
                    if any(kw in val_lower for kw in ['premium', 'luxury', 'high']):
                        high_tier = val
                    elif any(kw in val_lower for kw in ['budget', 'economy', 'low', 'basic']):
                        low_tier = val
                if high_tier is not None and low_tier is not None:
                    high_val = tier_sums[high_tier]
                    low_val  = tier_sums[low_tier]
                    if low_val > 0 and high_val > low_val * 1.5:
                        insights.append(
                            f"{high_tier} products generate significantly higher "
                            f"{col_label(num_col).lower()} than {low_tier} products."
                        )
            break

    # ---- 16. STRONGEST CATEGORICAL INFLUENCE ON NUMERIC METRIC -------------- #
    if best_cats and best_nums and len(best_cats) >= 2:
        num_col = best_nums[0][0]
        best_influence_col = None
        best_cv = 0
        for col, _ in best_cats[:5]:
            if 2 <= df[col].nunique() <= 20:
                group_sums = df.groupby(col)[num_col].sum()
                if group_sums.mean() > 0:
                    cv = group_sums.std() / group_sums.mean()
                    if cv > best_cv:
                        best_cv = cv
                        best_influence_col = col
        if best_influence_col and best_cv >= 0.5:
            insights.append(
                f"{col_label(best_influence_col)} has the strongest influence on "
                f"total {col_label(num_col).lower()}."
            )

    # ---- 17. MAJORITY CATEGORY PURCHASE PATTERN --------------------------- #
    if best_cats and entity_col:
        cat_col = best_cats[0][0]
        if df[cat_col].nunique() <= 15:
            entity_top_cat = df.groupby(entity_col)[cat_col].agg(
                lambda x: x.mode().iloc[0] if not x.mode().empty else x.iloc[0]
            )
            mode_cat = entity_top_cat.mode()
            if not mode_cat.empty:
                dominant = mode_cat.iloc[0]
                dominant_pct = (entity_top_cat == dominant).sum() / len(entity_top_cat) * 100
                if dominant_pct >= 40:
                    insights.append(
                        f"The majority of {col_label(entity_col).lower()}s purchased "
                        f"{dominant} {col_label(cat_col).lower()} products."
                    )

    return insights
