from googlesearch import search

def search_privacy_policy(dependency_name):
    query = f"{dependency_name} privacy policy"
    
    try:
        # Perform a Google search
        search_results = list(search(query, num=1, stop=1, pause=2))
        
        if search_results:
            privacy_policy_url = search_results[0]
            print(f"Privacy Policy for {dependency_name} found at: {privacy_policy_url}")
        else:
            print(f"Privacy Policy for {dependency_name} not found.")
            privacy_policy_url = input("Please enter the Privacy Policy URL: ")

        return privacy_policy_url
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    # Get the dependency name from the user
    dependency_name = input("Enter the name of the third-party dependency: ")

    # Search for the privacy policy document
    privacy_policy_url = search_privacy_policy(dependency_name)

    if privacy_policy_url:
        print(f"The Privacy Policy URL for {dependency_name}: {privacy_policy_url}")
