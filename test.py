import joblib

# Load the joblib file
analyze_privacy_policy = joblib.load('analyze_privacy_policy.joblib')

# Call the function with a dependency name
analyze_privacy_policy('google')
