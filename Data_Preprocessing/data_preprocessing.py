import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.impute import KNNImputer
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from scipy.stats import skew

# ==========================
# 1. Data Loading Function
# ==========================

def load_data(path, sheet_name):
    """Load the Excel file and return a DataFrame."""
    return pd.read_excel(path, sheet_name=sheet_name)

# ==========================
# 2. Data Preparation
# ==========================

def prepare_base_data(df, random_state=42):
    """
    Prepare the base dataset by:
    1. Dropping irrelevant and sparse columns.
    2. Splitting data into training and testing sets.
    3. Scaling and imputing missing data.
    """

    # Drop columns with more than 30% missing values and irrelevant columns
    columns_to_drop = ['yRelativeLowerPower.scaled.corr.N4', 'yRelativeLowerPower.N4', 'yRelativeLowerPower.scaled.N4', 
                       'cTOTEXs', 'cTOTEXs_RP3', 'cTOTEXn_RP3', 'NameOrg', 'NameShort', 'dmuName', 'dmu', 
                       'dDateData', 'BNR', 'BNR_NNR']
    df = df.drop(columns=columns_to_drop)
    
    # Drop columns with more than 90% zero values
    threshold = 0.9 * len(df)
    sparse_columns_to_drop = [col for col in df.columns if (df[col] == 0).sum() > threshold]
    df = df.drop(columns=sparse_columns_to_drop)
    
    # Split data into training and testing sets
    df_train, df_test = train_test_split(df, test_size=0.1, random_state=random_state)
    
    # Scale the data
    scaler = StandardScaler()
    df_train_scaled = scaler.fit_transform(df_train)
    df_test_scaled = scaler.transform(df_test)

    # Impute missing data using KNN Imputer
    imputer = KNNImputer(n_neighbors=3)
    df_train_scaled = imputer.fit_transform(df_train_scaled)
    df_test_scaled = imputer.transform(df_test_scaled)

    # Inverse transform to revert data back to original scale
    df_train = scaler.inverse_transform(df_train_scaled)
    df_test = scaler.inverse_transform(df_test_scaled)

    # Convert the results back to DataFrames
    df_train = pd.DataFrame(df_train, columns=df.columns)
    df_test = pd.DataFrame(df_test, columns=df.columns)    
    
    return df_train, df_test

# ==========================
# 3. Feature Transformation
# ==========================

def apply_transformation(df_train, df_test, feature, target, degree=2, skewness_threshold=0.5, improvement_threshold=0.01):
    """
    Apply feature transformation:
    1. Log transformation for skewed features.
    2. Polynomial transformation if it significantly improves model performance.
    """

    # Calculate the skewness of the feature
    skewness = skew(df_train[feature].dropna())
    
    # Apply log transformation if skewness is above the threshold
    if skewness > skewness_threshold:
        df_train[feature] = np.log1p(df_train[feature])
        df_test[feature] = np.log1p(df_test[feature])
        return
    
    # Prepare data for polynomial transformation
    X_train = df_train[[feature]]
    y_train = df_train[target]
    
    # Fit a linear regression model
    lin_reg = LinearRegression()
    lin_reg.fit(X_train, y_train)
    y_pred_lin = lin_reg.predict(X_train)
    
    # Fit a polynomial regression model
    poly = PolynomialFeatures(degree=degree)
    X_poly_train = poly.fit_transform(X_train)
    poly_reg = LinearRegression()
    poly_reg.fit(X_poly_train, y_train)
    y_pred_poly = poly_reg.predict(X_poly_train)
    
    # Compare the R-squared values of the linear and polynomial models
    r2_lin = r2_score(y_train, y_pred_lin)
    r2_poly = r2_score(y_train, y_pred_poly)
    
    # Apply polynomial transformation if it significantly improves the R-squared value
    if r2_poly - r2_lin > improvement_threshold:
        df_train[feature] = y_pred_poly
        X_val = df_test[[feature]]
        X_poly_val = poly.transform(X_val)
        df_test[feature] = poly_reg.predict(X_poly_val)

def transform_features(df_train, df_test, target, degree=2, skewness_threshold=0.5, improvement_threshold=0.01):
    """
    Iterate over features and apply necessary transformations to both training and testing sets.
    """

    # Iterate over all columns except the target
    for feature in df_train.columns:
        if feature != target:
            apply_transformation(df_train, df_test, feature, target, degree, skewness_threshold, improvement_threshold)

    return df_train, df_test

# ==========================
# 4. Feature Aggregation
# ==========================

def aggregate_and_sum_by_group(df):
    """
    Aggregate features by summing them across defined groups:
    1. Sum columns with similar variable prefixes (e.g., N1-N4, N5-N7).
    2. Drop the original columns after aggregation.
    3. Filter out existing aggregate columns that might be correlated.
    """

    # Find unique variable prefixes (variable names before ".N")
    variable_groups = set(col.split('.N')[0] for col in df.columns if '.N' in col)
    
    # Dictionary to collect new columns
    new_columns = {}

    for var in variable_groups:
        # Identify columns that belong to this variable group for N1-N4 and N5-N7
        n1_n4_cols = [f"{var}.N{i}" for i in range(1, 5) if f"{var}.N{i}" in df.columns]
        n5_n7_cols = [f"{var}.N{i}" for i in range(5, 8) if f"{var}.N{i}" in df.columns]
        
        # Sum the columns within each group
        if n1_n4_cols:
            new_columns[f'{var}_agg_N1to4'] = df[n1_n4_cols].sum(axis=1)
        if n5_n7_cols:
            new_columns[f'{var}_agg_N5to7'] = df[n5_n7_cols].sum(axis=1)
        
        # Drop the original N1-N7 columns
        df.drop(columns=n1_n4_cols + n5_n7_cols, inplace=True)
    
    # Concatenate all new columns at once
    df = pd.concat([df, pd.DataFrame(new_columns)], axis=1)
    
    # Filter out possibly correlated existing aggregate columns
    df = df.filter(regex='^(?!.*(tot|sum)).*').copy()

    return df

# ==========================
# 5. Creating Data Variations
# ==========================

def create_variations(df_train, df_test, random_state=42):
    """
    Create multiple variations of the dataset to experiment with different transformations:
    1. Log-transformed features.
    2. Log-transformed features and outcome.
    3. Log-transformed outcome.
    4. Aggregated features.
    5. Aggregated log-transformed features.
    6. Disaggregated features.
    7. Aggregated features based on N1-4 and N5-7 groups.
    """

    # Log-transformed features
    df_train_xlog = df_train.copy()
    df_test_xlog = df_test.copy()
    transform_features(df_train_xlog, df_test_xlog, target='cTOTEXn')
    
    # Log-transformed features and outcome
    df_train_xlog_ylog = df_train_xlog.copy()
    df_test_xlog_ylog = df_test_xlog.copy()
    df_train_xlog_ylog['cTOTEXn_log'] = np.log1p(df_train_xlog_ylog['cTOTEXn'])
    df_test_xlog_ylog['cTOTEXn_log'] = np.log1p(df_test_xlog_ylog['cTOTEXn'])
    df_train_xlog_ylog.drop(columns=['cTOTEXn'], inplace=True)
    df_test_xlog_ylog.drop(columns=['cTOTEXn'], inplace=True)
    
    # Log-transformed outcome
    df_train_ylog = df_train.copy()
    df_test_ylog = df_test.copy()
    df_train_ylog['cTOTEXn_log'] = np.log1p(df_train_ylog['cTOTEXn'])
    df_test_ylog['cTOTEXn_log'] = np.log1p(df_test_ylog['cTOTEXn'])
    df_train_ylog.drop(columns=['cTOTEXn'], inplace=True)
    df_test_ylog.drop(columns=['cTOTEXn'], inplace=True)
    
    # Only aggregated features
    df_train_agg = df_train.copy().filter(regex='(tot|sum)$|^cTOTEXn$')
    df_test_agg = df_test.copy().filter(regex='(tot|sum)$|^cTOTEXn$')
    
    # Only aggregated log features
    df_train_agg_log = df_train_xlog_ylog.copy().filter(regex='(tot|sum)|^cTOTEXn_log$')
    df_test_agg_log = df_test_xlog_ylog.copy().filter(regex='(tot|sum)|^cTOTEXn_log$')
    
    # Only disaggregated features
    df_train_non_agg = df_train.copy().filter(regex='^(?!.*(tot|sum)).*')
    df_test_non_agg = df_test.copy().filter(regex='^(?!.*(tot|sum)).*')
    
    # Aggregation only on N1-4 and N5-7
    df_train_group_agg = df_train.copy()
    df_test_group_agg = df_test.copy()
    df_train_group_agg = aggregate_and_sum_by_group(df_train_group_agg)
    df_test_group_agg = aggregate_and_sum_by_group(df_test_group_agg)
    
    # Return all variations
    df_train_list = [df_train, df_train_xlog, df_train_xlog_ylog, df_train_ylog, df_train_agg, 
                     df_train_agg_log, df_train_non_agg, df_train_group_agg]
    df_test_list = [df_test, df_test_xlog, df_test_xlog_ylog, df_test_ylog, df_test_agg, 
                    df_test_agg_log, df_test_non_agg, df_test_group_agg]
    
    return df_train_list, df_test_list
