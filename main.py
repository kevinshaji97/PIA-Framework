import click
from database import create_db_table, insert_dependency, retrieve_all_dependencies
from scrapper import search_privacy_policy

@click.command()
def main():
    tool_name="""
 |  __ \    (_)                       |_   _|                          | |  
 | |__) | __ ___   ____ _  ___ _   _    | |  _ __ ___  _ __   __ _  ___| |_ 
 |  ___/ '__| \ \ / / _` |/ __| | | |   | | | '_ ` _ \| '_ \ / _` |/ __| __|
 | |   | |  | |\ V / (_| | (__| |_| |  _| |_| | | | | | |_) | (_| | (__| |_ 
 |_|   |_|  |_| \_/ \__,_|\___|\__, | |_____|_| |_| |_| .__/ \__,_|\___|\__|
                                __/ |                 | |                   
                               |___/                  |_|                   
     /\                                              | |                    
    /  \   ___ ___  ___  ___ ___ _ __ ___   ___ _ __ | |_                   
   / /\ \ / __/ __|/ _ \/ __/ __| '_ ` _ \ / _ \ '_ \| __|                  
  / ____ \\__ \__ \  __/\__ \__ \ | | | | |  __/ | | | |_                   
 /_/    \_\___/___/\___||___/___/_| |_| |_|\___|_| |_|\__|                  

Python based tool to conduct PIA of Third Party Dependencies                                                                         
"""
    click.echo(tool_name)
    click.echo("1. Display PIA Dashboard")
    click.echo("2. Analyze a New Dependency")

    choice = click.prompt("Select an option (1 or 2)", type=int)

    if choice == 1:
        display_pia_dashboard()
    elif choice == 2:
        analyze_new_dependency()
    else:
        click.echo("Invalid choice. Exiting.")

def display_pia_dashboard():
    create_db_table()

    dependencies = retrieve_all_dependencies()

    if not dependencies:
        click.echo("No dependencies found.")
    else:
        click.echo("Dependency Name | Version | PIA Score")
        click.echo("---------------------------------------")
        for dependency in dependencies:
            click.echo(f"{dependency[0]} | {dependency[1]} | {dependency[2]}")

def analyze_new_dependency():
    create_db_table()
    dependency_name = click.prompt("Enter the Dependency Name")
    search_privacy_policy(dependency_name)
    #version = click.prompt("Enter the Version")
    #pia_score = click.prompt("Enter the PIA Score", type=int)

    #insert_dependency(dependency_name, version)

    click.echo("Dependency analyzed and saved successfully.")

if __name__ == "__main__":
    main()
