import random
import sys
from database import insert_dependency

# Define strings and score metrics
string1 = [
    "Clear and detailed privacy policy",
    "Adequate privacy policy but lacks details",
    
]
string2 = [
    "Granular and explicit consent options",
    "Consent options available but not granular",
    "Limited or no consent options",
]
string3 = [
    "Strong encryption for data transmission and storage",
    "Encryption used for data transmission but not storage",
    "Limited or no encryption",
]
string4 = [
    "Easy and accessible options for data deletion",
    "Options available but not user-friendly",
    "Limited or no data deletion options",
]
string5 = [
    "No data sharing with third parties",
    "Limited and transparent data sharing",
    "Extensive data sharing without clear transparency",
]
string6 = ["GDPR complaint", "Not mentioned regarding GDPR compliance"]

score_metrics = {
    "Clear and detailed privacy policy": 2,
    "Adequate privacy policy but lacks details": 1,
    "Granular and explicit consent options": 2,
    "Consent options available but not granular": 1,
    "Limited or no consent options": 0,
    "Strong encryption for data transmission and storage": 1.5,
    "Encryption used for data transmission but not storage": 0.5,
    "Limited or no encryption": 0,
    "Easy and accessible options for data deletion": 1.5,
    "Options available but not user-friendly": 0.5,
    "Limited or no data deletion options": 0,
    "No data sharing with third parties": 2,
    "Limited and transparent data sharing": 1,
    "Extensive data sharing without clear transparency": 0,
    "GDPR complaint": 1,
    "Not mentioned regarding GDPR compliance": 0,
}

# Function to randomly select a string and print the result
def analyze_privacy_policy(dependency_name):
    result_string1 = random.choice(string1)
    result_string2 = random.choice(string2)
    result_string3 = random.choice(string3)
    result_string4 = random.choice(string4)
    result_string5 = random.choice(string5)
    result_string6 = random.choice(string6)

    # Define ANSI escape codes for color formatting
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    RESET = "\033[0m"

    # Function to print with color based on the scoring
    def print_colored(metric, score):
        if score < 1:
            print(f"{YELLOW}{metric}{RESET}")
        else:
            print(f"{GREEN}{metric}{RESET}")

    # Print the randomly selected results with color
    print_colored(f"1. {result_string1}", score_metrics[result_string1])
    print_colored(f"2. {result_string2}", score_metrics[result_string2])
    print_colored(f"3. {result_string3}", score_metrics[result_string3])
    print_colored(f"4. {result_string4}", score_metrics[result_string4])
    print_colored(f"5. {result_string5}", score_metrics[result_string5])
    print_colored(f"6. {result_string6}", score_metrics[result_string6])

    # Calculate and print the PIA score
    pia_score = (
        score_metrics[result_string1]
        + score_metrics[result_string2]
        + score_metrics[result_string3]
        + score_metrics[result_string4]
        + score_metrics[result_string5]
        + score_metrics[result_string6]
    )
    print(f"\nPIA Score for {dependency_name}: {pia_score}")
    insert_dependency(dependency_name,result_string1,result_string2,result_string3,result_string4,result_string5,result_string6,pia_score)
# Check if a dependency_name argument is provided
if len(sys.argv) > 1:
    dependency_name = sys.argv[1]
    # Run the analysis with the provided dependency_name
    analyze_privacy_policy(dependency_name)
else:
    print("Please provide a Dependency Name.")
