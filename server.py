from flask import Flask, jsonify, request
from database import create_db_table, retrieve_all_dependencies
from scrapper import search_privacy_policy
from model import analyze_privacy_policy

app = Flask(__name__)

@app.route('/')
def home():
    return "Welcome to the PIA API"

@app.route('/pia_dashboard', methods=['GET'])
def get_pia_dashboard():
    create_db_table()
    dependencies = retrieve_all_dependencies()

    if not dependencies:
        return jsonify({"message": "No dependencies found."}), 200
    else:
        result = [{"Dependency Name": dep[0], "Metric 1": dep[1], "Metric 2": dep[2], "Metric 3": dep[3],"Metric 4": dep[4], "Metric 5": dep[5], "Metric 6": dep[6], "PIA Score": dep[7]} for dep in dependencies]
        return jsonify(result), 200

@app.route('/analyze_dependency', methods=['POST'])
def post_analyze_dependency():
    create_db_table()
    data = request.json
    dependency_name = data.get('dependency_name')

    if not dependency_name:
        return jsonify({"error": "Dependency Name is required"}), 400

    search_privacy_policy(dependency_name)
    analyze_privacy_policy(dependency_name)

    return jsonify({"message": "Dependency analyzed and saved successfully."}), 200

if __name__ == '__main__':
    app.run(debug=True)
