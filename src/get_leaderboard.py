import argparse
import subprocess
import json

def main(competition_name=None, test_mode=False):
    if test_mode:
        competition_list = [{"competition_name": "titanic"}]  # Use Titanic for testing purposes
    elif competition_name:
        # If a specific competition name is provided, use it to create a single-item list
        competition_list = [{"competition_name": competition_name}]
    else:
        with open("./data/competition_list.json", "r") as file:
            competition_list = json.load(file)

    for comp in competition_list:
        competition = comp["competition_name"]
        # Create commands with proper variable substitution
        base_dir = "../data/test" if test_mode else "../data"
        commands = [
            f"kaggle competitions leaderboard --download -c {competition} -p {base_dir}/leaderboard",
            f"mkdir -p {base_dir}/leaderboard",
            f"unzip -o {base_dir}/leaderboard/{competition}.zip -d {base_dir}/leaderboard/temp",
            f"find {base_dir}/leaderboard/temp -name \"*.csv\" -exec mv {{}} {base_dir}/leaderboard/{competition}.csv \\;",
            f"rm {base_dir}/leaderboard/{competition}.zip"
        ]

        # Execute each command
        for cmd in commands:
            subprocess.run(cmd, shell=True)
        subprocess.run(f"rm -rf {base_dir}/leaderboard/temp", shell=True)
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download and process Kaggle competition leaderboard data.")
    parser.add_argument("--competition_name", type=str, help="Name of the Kaggle competition (used only in non-test mode)")
    parser.add_argument("--test", action="store_true", help="Run in test mode (only for Titanic competition)")
    args = parser.parse_args()
    main(competition_name=args.competition_name, test_mode=args.test)