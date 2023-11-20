import requests
import os
from bs4 import BeautifulSoup
from openai import OpenAI

# Replace 'YOUR_OPENAI_API_KEY' with your actual OpenAI API key
client = OpenAI()

def fetch_text_from_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        text = ' '.join([p.get_text() for p in soup.find_all('p')])
        #print(text)
        return text
    except Exception as e:
        print(f"Error fetching content from the URL: {e}")
        return None

def analyze_privacy_policy_transparency(policy_text):
    if not policy_text:
        return 0  # Return 0 if there was an issue fetching the content

    prompt = f"Analyse the privacy policy transparency of the following text:\n\n{policy_text}\n\nScore on a scale of 0 to 2:"
    print(prompt)
    completion = client.chat.completions.create(
        model="text-davinci-003",
        messages=[
            {"role": "system", "content": "You are a privacy policy analyzer."},
            {"role": "user", "content": prompt}
        ]
    )

    score = int(completion.choices[0].message['content'].strip())
    return score

def main():
    # Replace 'POLICY_DOCUMENT_URL' with the actual URL of the policy document you want to analyze
    policy_document_url = 'https://www.jquerycards.com/privacy-policy/'

    # Fetch text from the URL
    policy_text = fetch_text_from_url(policy_document_url)

    # Analyze privacy policy transparency and get the score
    score = analyze_privacy_policy_transparency(policy_text)

    print(f"Privacy Policy Transparency Score: {score}/2")

if __name__ == "__main__":
    main()
