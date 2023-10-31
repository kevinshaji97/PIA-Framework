import argparse
from Wappalyzer import Wappalyzer, WebPage

def analyze_website(url):
    try:
        # Create a Wappalyzer object
        wappalyzer = Wappalyzer.latest()

        # Fetch and analyze the website
        webpage = WebPage.new_from_url(url)
        results = wappalyzer.analyze_with_versions(webpage)

        if results:
            print(f"Technology stack for {url}:")

            for app_name, app_info in results.items():
                version = app_info.get("versions", [])
                if version:
                    print(f"{app_name}: {', '.join(version)}")
                else:
                    print(app_name)

        else:
            print("No technologies detected.")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Analyze the technology stack of a web application.")
    parser.add_argument("website", help="URL of the website to analyze")
    args = parser.parse_args()

    url = args.website
    analyze_website(url)

if __name__ == "__main__":
    main()
