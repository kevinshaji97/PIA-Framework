import requests
from bs4 import BeautifulSoup
import re
import spacy

# Function to fetch the website's policy document
def fetch_policy_document(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None

# Function to extract data collection and compliance details from the policy document
def extract_policy_details(document_text):
    # Load a spaCy NLP model
    nlp = spacy.load("en_core_web_sm")

    # Parse the document with spaCy
    doc = nlp(document_text)

    # Define keywords related to data collection and compliance
    data_collection_keywords = ["data collection", "data gathering", "data capture"]
    compliance_keywords = ["compliance", "regulations", "privacy policy"]

    # Initialize variables to store the extracted information
    data_collection_details = []
    compliance_details = []

    # Search for relevant sentences in the document
    for sent in doc.sents:
        for keyword in data_collection_keywords:
            if keyword in sent.text.lower():
                data_collection_details.append(sent.text)

        for keyword in compliance_keywords:
            if keyword in sent.text.lower():
                compliance_details.append(sent.text)

    return data_collection_details, compliance_details

if __name__ == "__main__":
    website_url = "https://www.apachefriends.org/privacy_policy.html"  # Replace with the URL of the policy document
    policy_text = fetch_policy_document(website_url)

    if policy_text:
        data_collection, compliance = extract_policy_details(policy_text)

        print("Data Collection Details:")
        for detail in data_collection:
            print(detail)

        print("\nCompliance Details:")
        for detail in compliance:
            print(detail)
