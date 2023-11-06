import requests
import json

# NVD API base URL
base_url = "https://services.nvd.nist.gov/rest/json/cves/1.0"

def calculate_severity_score(cves):
    # Mapping of CVSS base scores to severity levels
    severity_scores = {
        'LOW': 1,
        'MEDIUM': 4,
        'HIGH': 7,
        'CRITICAL': 10
    }

    max_severity = 'HIGH'  # Initialize max severity
    for cve in cves:
        if 'baseMetricV3' in cve:
            severity = cve['baseMetricV3']['cvssV3']['baseSeverity']
            if severity in severity_scores and severity_scores[severity] > severity_scores[max_severity]:
                max_severity = severity
    return severity_scores[max_severity]

def check_vulnerabilities_for_software(software_name):
    try:
        # Construct the API URL with the software name as a parameter
        url = f"{base_url}?keyword={software_name}"
        
        # Make a GET request to the NVD API
        response = requests.get(url)

        if response.status_code == 200:
            data = json.loads(response.text)
            if "result" in data:
                vulnerabilities = data["result"]["CVE_Items"]
                if vulnerabilities:
                    print(f"Vulnerabilities for {software_name}:")
                    for i, cve in enumerate(vulnerabilities):
                        cve_id = cve["cve"]["CVE_data_meta"]["ID"]
                        description = cve["cve"]["description"]["description_data"][0]["value"]
                        print(f"{i + 1}. CVE ID: {cve_id}")
                        print(f"   Description: {description}")
                    severity_score = calculate_severity_score(vulnerabilities)
                    print(f"Vulnerability Score: {severity_score} out of 10")
                else:
                    print(f"No vulnerabilities found for {software_name}.")
            else:
                print("No results found.")
        else:
            print(f"Failed to retrieve data. Status code: {response.status_code}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    software_name = input("Enter the name of the software to check for vulnerabilities: ")
    check_vulnerabilities_for_software(software_name)
