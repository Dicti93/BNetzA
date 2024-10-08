# Import necessary libraries
import pandas as pd
import numpy as np
from sklearn.linear_model import LassoCV, LinearRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, mean_absolute_percentage_error
from sklearn.model_selection import GridSearchCV
from sklearn.feature_selection import SelectFromModel
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
import statsmodels.api as sm
from collections import Counter

#### Section 1: Constants and Variables ####
# -------------------------------------------------------------------- 
# -------------------------------------------------------------------- 
# -------------------------------------------------------------------- 

# Define the variables related to technical blocks
technical_blocks_variables = [
    "yCables.all.N13.sum", "yCables.all.N57.sum", "yCables.all.tot", "yCables.circuit.N3", "yCables.circuit.N5", "yCables.circuit.N7",
    "yConnections.incl.inj.N1357.sum", "yConnections.other.dso.lower.N1to6.sum", "yConnections.other.dso.same.tot",
    "yEnergy.delivered.net.N23.sum", "yEnergy.delivered.net.N2to4.sum", "yEnergy.delivered.net.N45.sum", "yEnergy.delivered.net.N5to7.sum", "yEnergy.delivered.net.N67.sum", "yEnergy.delivered.net.tot", 
    "yInjection.net.N2to4.sum", "yInjection.net.N5to7.sum", 
    "yInstalledPower.KWKG.other.tot", "yInstalledPower.N1to4.sum", "yInstalledPower.N5to6.sum", "yInstalledPower.N5to7.sum", "yInstalledPower.N7", "yInstalledPower.nonsimcurt.N1to4.sum", 
    "yInstalledPower.nonsimcurt.N5to7.sum", "yInstalledPower.non.solar.wind.tot",
    "yInstalledPower.reducedAPFI.N1to4.sum", "yInstalledPower.reducedAPFI.N5to7.sum", "yInstalledPower.reducedAPFI.tot", "yInstalledPower.renewables.bio.hydro.tot", 
    "yInstalledPower.renewables.solar.tot", "yInstalledPower.renewables.solar.wind.tot", "yInstalledPower.renewables.wind.tot", 
    "yLines.all.N13.sum", "yLines.all.N57.sum", "yLines.all.tot", "yLines.circuit.N3", "yLines.circuit.N5", "yLines.circuit.N7",
    "yMeters.cp.ctrl.tot", "yMeters.house.tot", "yMeters.noncp.ctrl.excl.house.tot", "yMeters.noncp.ctrl.tot", "yMeters.read.tot", 
    "yNet.length.N5", "yNet.length.N7", "yNet.length.all.tot",
    "yPeakload.N4", "yPeakload.N6", "yPeakload.abs.sim.N4", "yPeakload.from.higher.sim.N4", "yPeakload.into.higher.sim.N4", "yPeakload.into.higher.sim.nett.N6"
]

#### Section 2: Utility Functions ####
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

def safe_exp(y, max_value=700):
    """Safely calculate the exponential to avoid overflow."""
    y_clipped = np.clip(y, None, max_value)
    return np.exp(y_clipped)

def model_predict(model, df_train, df_test, target, outcome_transformation="None", random_state=42, scaling=False):
    """Predicts the target values using the provided model and evaluates with optional scaling and outcome transformation."""
    X_train = df_train.drop(columns=[target])
    y_train = df_train[target]
    
    X_test = df_test.drop(columns=[target])
    y_test = df_test[target]
    
    # Optional feature scaling
    if scaling:
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
    else:
        X_train_scaled = X_train
        X_test_scaled = X_test

    y_train_pred = model.predict(X_train_scaled)
    y_test_pred = model.predict(X_test_scaled)
    
    # Optional outcome transformation (e.g., logarithmic)
    if outcome_transformation == "log":
        y_train_pred = safe_exp(y_train_pred)
        y_test_pred = safe_exp(y_test_pred)
        y_train = safe_exp(y_train)
        y_test = safe_exp(y_test)
        
    return y_train, y_train_pred, y_test, y_test_pred

def model_evaluation(y_train, y_train_pred, y_test, y_test_pred, model_name):
    """Evaluates the model performance using various metrics and returns a DataFrame with the results."""
    # Metrics for training data
    train_rmse = np.sqrt(mean_squared_error(y_train, y_train_pred))
    train_mae = mean_absolute_error(y_train, y_train_pred)
    train_mape = mean_absolute_percentage_error(y_train, y_train_pred)

    # Metrics for test data
    test_rmse = np.sqrt(mean_squared_error(y_test, y_test_pred))
    test_mae = mean_absolute_error(y_test, y_test_pred)
    test_mape = mean_absolute_percentage_error(y_test, y_test_pred)
    
    # Collecting all metrics
    results_dict = {
        "Model": [model_name],
        "Training RMSE": [f"{train_rmse:.2f}"],
        "Training MAE": [f"{train_mae:.2f}"],
        "Training MAPE": [f"{train_mape:.2f}"],
        "Testing RMSE": [f"{test_rmse:.2f}"],
        "Testing MAE": [f"{test_mae:.2f}"],
        "Testing MAPE": [f"{test_mape:.2f}"]
    }

    results_df = pd.DataFrame(results_dict)
    return results_df

def variable_frequency(vips, name):
    """Calculates and returns the frequency of selected variables across different models."""
    variable_counter = Counter()
    for vip in vips:
        variables = vip['Feature']  
        variable_counter.update(variables)

    variable_counts_df = pd.DataFrame(variable_counter.items(), columns=['Variable', name])
    variable_counts_df = variable_counts_df.sort_values(by=name, ascending=False).reset_index(drop=True)
    
    return variable_counts_df

def percentage_deviation(y_train, y_train_pred, y_test, y_test_pred):
    """Calculates and returns the percentage deviation of the predictions."""
    test_percentage_deviation = abs((y_test - y_test_pred) / y_test) * 100
    test_df = pd.DataFrame({'Actual': y_test, 'Predicted': y_test_pred, 'Percentage Deviation': test_percentage_deviation})
    test_df_sorted = test_df.sort_values(by='Percentage Deviation', ascending=False)
    return test_df_sorted

#### Section 3: Regression Models ####
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

def lasso_regression(df_train, df_test, target, model_name, outcome_transformation="None", random_state=42):
    """Performs Lasso regression with cross-validation for feature selection and evaluation."""
    # Split data into features and target
    X_train = df_train.drop(columns=[target])
    y_train = df_train[target]
    
    # Standardize the features using training data
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_train_scaled = pd.DataFrame(X_train_scaled, columns=X_train.columns)
    
    # Lasso regression with cross-validation
    lasso = LassoCV(cv=5, random_state=random_state, max_iter=10000).fit(X_train_scaled, y_train)
    
    # Set negative coefficients to zero
    lasso.coef_[lasso.coef_ < 0] = 0

    # Predict and evaluate the model
    y_train, y_train_pred, y_test, y_test_pred = model_predict(lasso, df_train, df_test, target, outcome_transformation, random_state, scaling=True)
    eval_metrics = model_evaluation(y_train, y_train_pred, y_test, y_test_pred, model_name)
    
    # Variable importance
    selected_features_lasso = X_train_scaled.columns[lasso.coef_ != 0]  
    variable_importance_dict = {
        "Feature": selected_features_lasso,
        "Coefficient": lasso.coef_[lasso.coef_ != 0]  
    }
    variable_importance_df = pd.DataFrame(variable_importance_dict).sort_values(by="Coefficient", ascending=False).reset_index(drop=True)
    
    return eval_metrics, lasso, variable_importance_df

def lasso_feature_selection_linear_regression(df_train, df_test, target, model_name, outcome_transformation="None", random_state=42):
    """Combines Lasso regression for feature selection with linear regression for final modeling."""
    # Split data into features and target
    X_train = df_train.drop(columns=[target])
    y_train = df_train[target]
    
    # Standardize the features using training data
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_train_scaled = pd.DataFrame(X_train_scaled, columns=X_train.columns)
    
    # Lasso regression with cross-validation
    lasso = LassoCV(cv=5, random_state=random_state, max_iter=10000).fit(X_train_scaled, y_train)
    
    # Select features based on Lasso coefficients
    selected_features_lasso = np.where(lasso.coef_ > 0)[0]
    selected_feature_names_lasso = X_train.columns[selected_features_lasso]
    
    # Raise an exception if no features are selected
    if len(selected_feature_names_lasso) == 0:
        raise ValueError("No features were selected by Lasso. Try adjusting the Lasso parameters.")
    
    # Use selected features for linear regression
    X_train_selected = X_train_scaled[selected_feature_names_lasso]
    X_train_selected = sm.add_constant(X_train_selected)

    # Fit linear regression model using statsmodels for p-values
    sm_model = sm.OLS(y_train, X_train_selected).fit()

    # Prepare test data
    X_test = df_test.drop(columns=[target])
    X_test_scaled = scaler.transform(X_test)
    X_test_scaled = pd.DataFrame(X_test_scaled, columns=X_test.columns)
    
    X_test_selected = X_test_scaled[selected_feature_names_lasso].copy()
    X_test_selected['const'] = 1
    X_test_selected = X_test_selected[['const'] + [col for col in X_test_selected.columns if col != 'const']]

    y_test = df_test[target]
    y_train_pred = sm_model.predict(X_train_selected)
    y_test_pred = sm_model.predict(X_test_selected)
    
    # Optional outcome transformation
    if outcome_transformation == "log":
        y_train_pred = safe_exp(y_train_pred)
        y_test_pred = safe_exp(y_test_pred)
        y_train = safe_exp(y_train)
        y_test = safe_exp(y_test)
    
    eval_metrics = model_evaluation(y_train, y_train_pred, y_test, y_test_pred, model_name)
    
    return eval_metrics, sm_model

def random_forest_regression(df_train, df_test, target, model_name, outcome_transformation="None", random_state=42):
    """Performs Random Forest regression with cross-validation and feature selection."""
    # Split data into features and target
    X_train = df_train.drop(columns=[target])
    y_train = df_train[target]
    
    # Define the model
    rf = RandomForestRegressor(random_state=random_state)
    
    # Define a pipeline for feature selection and model training
    pipeline = Pipeline([
        ('feature_selection', SelectFromModel(rf, max_features=20)),
        ('rf', rf)
    ])
    
    # Define the hyperparameter grid - reduce training time by manually setting best parameters
    param_grid = {
        'rf__n_estimators': [100],  
        'rf__max_depth': [None, 10],  
        'rf__min_samples_split': [2],  
        'rf__min_samples_leaf': [1, 2],  
    }
    
    # Perform GridSearchCV with cross-validation
    grid_search = GridSearchCV(pipeline, param_grid, cv=5, n_jobs=-1, verbose=2)
    grid_search.fit(X_train, y_train)
    
    # Get the best model
    best_model = grid_search.best_estimator_
    
    # Predict and evaluate the model
    y_train, y_train_pred, y_test, y_test_pred = model_predict(best_model, df_train, df_test, target, outcome_transformation, random_state)
    eval_metrics = model_evaluation(y_train, y_train_pred, y_test, y_test_pred, model_name)
    
    # Feature importance
    selected_features = best_model.named_steps['feature_selection'].get_support(indices=True)
    selected_feature_names = X_train.columns[selected_features]
    feature_importance_dict = {
        "Feature": selected_feature_names,
        "Importance": best_model.named_steps['rf'].feature_importances_
    }
    feature_importance_df = pd.DataFrame(feature_importance_dict).sort_values(by="Importance", ascending=False).reset_index(drop=True)
    
    return eval_metrics, best_model, feature_importance_df

def decision_tree_regression(df_train, df_test, target, model_name, outcome_transformation="None", random_state=42):
    """Performs Decision Tree regression with cross-validation and feature selection."""
    # Split data into features and target
    X_train = df_train.drop(columns=[target])
    y_train = df_train[target]
    
    # Define the model
    dt = DecisionTreeRegressor(random_state=random_state)
    
    # Define a pipeline for feature selection and model training
    pipeline = Pipeline([
        ('feature_selection', SelectFromModel(dt, max_features=20)),
        ('dt', dt)
    ])
    
    # Define the hyperparameter grid
    param_grid = {
        'dt__max_depth': [10, 20, 30],
        'dt__min_samples_split': [2, 5, 10],
        'dt__min_samples_leaf': [1, 2, 4]
    }
    
    # Perform GridSearchCV with cross-validation
    grid_search = GridSearchCV(pipeline, param_grid, cv=5, n_jobs=-1, verbose=2)
    grid_search.fit(X_train, y_train)
    
    # Get the best model
    best_model = grid_search.best_estimator_
             
    # Predict and evaluate the model
    y_train, y_train_pred, y_test, y_test_pred = model_predict(best_model, df_train, df_test, target, outcome_transformation, random_state)
    eval_metrics = model_evaluation(y_train, y_train_pred, y_test, y_test_pred, model_name)
    
    # Feature importance
    selected_features = best_model.named_steps['feature_selection'].get_support(indices=True)
    selected_feature_names = X_train.columns[selected_features]
    feature_importance_dict = {
        "Feature": selected_feature_names,
        "Importance": best_model.named_steps['dt'].feature_importances_
    }
    feature_importance_df = pd.DataFrame(feature_importance_dict).sort_values(by="Importance", ascending=False).reset_index(drop=True)
    
    return eval_metrics, best_model, feature_importance_df

#### Section 4: Clustering and Cluster-Based Modeling ####
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

def create_clusters(df_train):
    """Clusters data using DBSCAN based on technical block variables and returns cluster-specific data."""
    # Standardize the features from technical blocks
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_train[technical_blocks_variables])

    dbscan = DBSCAN(eps=0.5, min_samples=5)
    train_clusters = dbscan.fit_predict(X_scaled)

    # Add cluster labels to training data
    df_train['Cluster'] = train_clusters

    # Split the training data based on cluster labels
    df_train_c0 = df_train[df_train['Cluster'] == 0].drop(['Cluster'], axis=1)
    df_train_c1 = df_train[df_train['Cluster'] == -1].drop(['Cluster'], axis=1)
    
    return df_train_c0, df_train_c1, dbscan, scaler

def cluster_based_modeling(df_train, df_test, target, model_name, outcome_transformation="None", random_state=42):
    """Performs cluster-based modeling by dividing data into clusters and applying Lasso and Random Forest models."""
    # Create clusters of network providers
    df_train_c0, df_train_c1, dbscan, scaler = create_clusters(df_train)
    
    # Scale the test data using the scaler fitted on the training data
    X_test_scaled = scaler.transform(df_test[technical_blocks_variables])

    # Apply the DBSCAN model to the test data
    test_clusters = dbscan.fit_predict(X_test_scaled)

    # Add cluster labels to test data
    df_test['Cluster'] = test_clusters

    # Split the test data based on the cluster labels
    df_test_c0 = df_test[df_test['Cluster'] == 0].drop(['Cluster'], axis=1)
    df_test_c1 = df_test[df_test['Cluster'] == -1].drop(['Cluster'], axis=1)

    # Train Lasso on both clusters and track evaluation
    _, lasso_c0, lasso_vip_c0 = lasso_regression(df_train_c0, df_test_c0, target, model_name, outcome_transformation, random_state)
    y_train_lasso_c0, y_train_pred_lasso_c0, y_test_lasso_c0, y_test_pred_lasso_c0 = model_predict(lasso_c0, df_train_c0, df_test_c0, target, outcome_transformation, random_state, scaling=True)
    eval_metrics_c0 = model_evaluation(y_train_lasso_c0, y_train_pred_lasso_c0, y_test_lasso_c0, y_test_pred_lasso_c0, "Lasso")
    
    _, lasso_c1, lasso_vip_c1 = lasso_regression(df_train_c1, df_test_c1, target, model_name, outcome_transformation, random_state)
    y_train_lasso_c1, y_train_pred_lasso_c1, y_test_lasso_c1, y_test_pred_lasso_c1 = model_predict(lasso_c1, df_train_c1, df_test_c1, target, outcome_transformation, random_state, scaling=True)
    eval_metrics_c1 = model_evaluation(y_train_lasso_c1, y_train_pred_lasso_c1, y_test_lasso_c1, y_test_pred_lasso_c1, "Lasso")
    
    # Train Random Forest on both clusters and track evaluation
    _, rf_c0, rf_vip_c0 = random_forest_regression(df_train_c0, df_test_c0, target, model_name, outcome_transformation, random_state)
    y_train_rf_c0, y_train_pred_rf_c0, y_test_rf_c0, y_test_pred_rf_c0 = model_predict(rf_c0, df_train_c0, df_test_c0, target, outcome_transformation, random_state)
    eval_metrics_c0_rf = model_evaluation(y_train_rf_c0, y_train_pred_rf_c0, y_test_rf_c0, y_test_pred_rf_c0, "Random Forest")
    eval_metrics_c0 = pd.concat([eval_metrics_c0, eval_metrics_c0_rf], ignore_index=True)
    
    _, rf_c1, rf_vip_c1 = random_forest_regression(df_train_c1, df_test_c1, target, model_name, outcome_transformation, random_state)
    y_train_rf_c1, y_train_pred_rf_c1, y_test_rf_c1, y_test_pred_rf_c1 = model_predict(rf_c1, df_train_c1, df_test_c1, target, outcome_transformation, random_state)
    eval_metrics_c1_rf = model_evaluation(y_train_rf_c1, y_train_pred_rf_c1, y_test_rf_c1, y_test_pred_rf_c1, "Random Forest")
    eval_metrics_c1 = pd.concat([eval_metrics_c1, eval_metrics_c1_rf], ignore_index=True)
    
    # Identify the best model for each cluster based on the lowest test MAPE
    eval_metrics_c0["Testing MAPE"] = pd.to_numeric(eval_metrics_c0["Testing MAPE"], errors='coerce')
    best_model_df_c0 = eval_metrics_c0.loc[eval_metrics_c0["Testing MAPE"].idxmin()]
    
    eval_metrics_c1["Testing MAPE"] = pd.to_numeric(eval_metrics_c1["Testing MAPE"], errors='coerce')
    best_model_df_c1 = eval_metrics_c1.loc[eval_metrics_c1["Testing MAPE"].idxmin()]
    
    # Calculate new test metrics across both clusters
    best_model_c0 = best_model_df_c0["Model"]
    if best_model_c0 == "Lasso":
        y_train_c0, y_train_pred_c0, y_test_c0, y_test_pred_c0 = model_predict(lasso_c0, df_train_c0, df_test_c0, target, outcome_transformation, random_state, scaling=True)
        model_c0 = lasso_c0
    elif best_model_c0 == "Random Forest":
        y_train_c0, y_train_pred_c0, y_test_c0, y_test_pred_c0 = model_predict(rf_c0, df_train_c0, df_test_c0, target, outcome_transformation, random_state)
        model_c0 = rf_c0
        
    best_model_c1 = best_model_df_c1["Model"]
    if best_model_c1 == "Lasso":
        y_train_c1, y_train_pred_c1, y_test_c1, y_test_pred_c1 = model_predict(lasso_c1, df_train_c1, df_test_c1, target, outcome_transformation, random_state, scaling=True)
        model_c1 = lasso_c1
    elif best_model_c1 == "Random Forest":
        y_train_c1, y_train_pred_c1, y_test_c1, y_test_pred_c1 = model_predict(rf_c1, df_train_c1, df_test_c1, target, outcome_transformation, random_state)
        model_c1 = rf_c1
    
    # Concatenate all data
    y_train = np.concatenate([y_train_c0, y_train_c1], axis=0)
    y_train_pred = np.concatenate([y_train_pred_c0, y_train_pred_c1], axis=0)
    y_test = np.concatenate([y_test_c0, y_test_c1], axis=0)
    y_test_pred = np.concatenate([y_test_pred_c0, y_test_pred_c1], axis=0)
    
    model_name = f"{model_name}_{best_model_c0}_{best_model_c1}"
    
    eval_metrics = model_evaluation(y_train, y_train_pred, y_test, y_test_pred, model_name)

    return eval_metrics, model_c0, model_c1
