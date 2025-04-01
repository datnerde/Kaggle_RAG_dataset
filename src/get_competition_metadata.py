import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import json
import os
import sys
import argparse

class CompetitionScraper:
    def __init__(self, headless=True, output_dir = None):
        self.user_agent = self._get_random_user_agent()
        self.output_dir = os.path.abspath(output_dir) if output_dir else os.getcwd()
        self.driver = self._init_driver(headless)
        self.wait = WebDriverWait(self.driver, 15)
        os.makedirs(self.output_dir, exist_ok=True)  # Create directory if needed
    
    def _get_random_user_agent(self):
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1"
        ]
        return random.choice(user_agents)
    
    def _init_driver(self, headless):
        options = uc.ChromeOptions()
        options.headless = headless
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument(f'--user-agent={self.user_agent}')
        # add download path
        prefs = {
            "download.default_directory": self.output_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        
        options.add_experimental_option("prefs", prefs)  # This was missing
        return uc.Chrome(options=options)

    def refresh_driver(self, headless):
        self.close()
        self.user_agent = self._get_random_user_agent()
        self.driver = self._init_driver(headless)
        self.wait = WebDriverWait(self.driver, 15)
    
    @staticmethod
    def extract_fields(text, desired_fields=None, ignore_fields=None):
        if desired_fields is None:
            desired_fields = {"Competition Host", "Prizes & Awards", "Participation", "Tags"}
        if ignore_fields is None:
            ignore_fields = {"Table of Contents", "Description", "Evaluation", 
                           "Frequently Asked Questions", "Citation"}
        
        extracted = {}
        for field in desired_fields:
            extracted[field] = {} if field == "Participation" else []
        
        current_field = None
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            if line in desired_fields:
                current_field = line
                continue
            
            if line in ignore_fields:
                current_field = None
                continue
            
            if current_field:
                if current_field == "Participation":
                    parts = line.split(" ", 1)
                    if len(parts) == 2:
                        num_str, label = parts
                        try:
                            extracted[current_field][label] = int(num_str.replace(",", ""))
                        except ValueError:
                            extracted[current_field][label] = num_str
                else:
                    extracted[current_field].append(line)
        return extracted
    
    def extract_competition_data(self, url):
        self.driver.get(url)
        
        desc_header = self.wait.until(EC.presence_of_element_located((By.ID, "description")))
        evaluation = self.wait.until(EC.presence_of_element_located((By.ID, "evaluation"))).text.strip()
        sidebar = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "sc-ipAaKu.blEaCU"))).text
        
        sidebar_content = self.extract_fields(sidebar)
        participation = sidebar_content.get("Participation", {})
        
        return {
            'Description': desc_header.text.strip(),
            'Evaluation': evaluation,
            'Competition Host': sidebar_content.get("Competition Host", []),
            'Prizes & Awards': sidebar_content.get("Prizes & Awards", []),
            'Entrants': participation.get('Entrants', 0),
            'Participants': participation.get('Participants', 0),
            'Teams': participation.get('Teams', 0),
            'Submissions': participation.get('Submissions', 0),
            'Tags': sidebar_content.get("Tags", [])
        }
        
    def extract_data_metadata(self, url):
        self.driver.get(url)
        
        try:
            desc_element = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "sc-fqpjkJ.xUjLo")))
            description = desc_element.text.strip()
        except Exception as e:
            print(f"Error extracting data description from {url}: {str(e)}")
            description = ""

        try:
            # Wait for and extract each value individually
            files = WebDriverWait(self.driver, 3).until(
                EC.visibility_of_element_located((By.XPATH, "//h2[contains(., 'Files')]/following-sibling::p[1]"))
            ).text

            size = WebDriverWait(self.driver, 3).until(
                EC.visibility_of_element_located((By.XPATH, "//h2[contains(., 'Size')]/following-sibling::p[1]"))
            ).text

            file_type = WebDriverWait(self.driver, 3).until(
                EC.visibility_of_element_located((By.XPATH, "//h2[contains(., 'Type')]/following-sibling::p[1]"))
            ).text
        except Exception as e:
            print(f"Error extracting data sidebar from {url}: {str(e)}")
            files = size = file_type = ""
        
        return {
            'Description': description,
            'Files': files,
            'Size': size,
            'Type': file_type
        }
        
    def verify_download_completion(self):
        """Check for .crdownload files to confirm download completion"""
        time.sleep(1)  # Initial wait
        for _ in range(30):  # Max 30 seconds wait
            if any(f.endswith('.crdownload') for f in os.listdir(self.output_dir)):
                time.sleep(1)  # Still downloading
            else:
                return True  # No more temp files
        return False
    
    def close_interfering_elements(self):
        try:
            # Close sign-in modal (if present)
            self.driver.execute_script('''
                document.querySelectorAll("div[role='dialog'] button[aria-label='Close']")
                    .forEach(btn => btn.click());
            ''')
            
            # Dismiss cookie banner (if present)
            cookie_accept = WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Accept')]"))
            )
            cookie_accept.click()
            time.sleep(0.5)
            
        except:
            pass  # No interfering elements found
    
    def download_data(self, url):
        self.driver.get(url)
        time.sleep(random.uniform(0.5, 2))
        try:
            # 1. Close any potential overlays (Kaggle-specific)
            self.close_interfering_elements()
            
            # 2. Wait for button AND scroll into view
            download_button = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[.//span[text()='Download All']]")
            ))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
            
            # 3. Use JavaScript click to bypass overlay interference
            time.sleep(random.uniform(0.5, 1))  # Allow final positioning
            self.driver.execute_script("arguments[0].click();", download_button)
            # # Add verification
            # if self.verify_download_completion():
            #     print(f"Download completed to: {self.output_dir}")
            #     return True
            # return False
            
            return True
        except Exception as e:
            print(f"Error downloading: {str(e)}")
            return False
    def download_leaderboard(self, url):
        self.driver.get(url)
        time.sleep(random.uniform(0.5, 2))
        try:
            # 1. Close any potential overlays (Kaggle-specific)
            self.close_interfering_elements()
            
            # 2. Wait for button AND scroll into view
            download_button = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[@title='Download Leaderboard']")
            ))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
            
            # 3. Use JavaScript click to bypass overlay interference
            time.sleep(random.uniform(0.5, 1))  # Allow final positioning
            self.driver.execute_script("arguments[0].click();", download_button)
            # Add verification
            # if self.verify_download_completion():
            #     print(f"Download completed to: {self.output_dir}")
            #     return True
            # return False
            return True
            
        except Exception as e:
            print(f"Error downloading: {str(e)}")
            return False
    def close(self):
        self.driver.quit()
# Modified main function
def main(args):
    scraper = CompetitionScraper(headless=args.headless, output_dir=args.output_dir)
    os.makedirs(args.data_dir, exist_ok=True)
    
    # Initialize rotation counter
    rotation_interval = args.rotation_interval

    if args.test:
        competition_urls = ['https://www.kaggle.com/competitions/titanic']
    else:
        try:
            competition_list = load_json(os.path.join('./data/', 'competition_list.json'))
            competition_urls = [entry['competition_url'] for entry in competition_list]
        except Exception as e:
            print(f"Failed to load competition list: {str(e)}")
            scraper.close()
            sys.exit(1)

    metadata_path = os.path.join(args.data_dir, 'competitions.json')
    metadata = load_json(metadata_path) if os.path.exists(metadata_path) else {}

    for i, url in enumerate(competition_urls):
        competition_name = url.rstrip('/').split('/')[-1]
        if url in metadata:
            print(f"Skipping already processed: {url}")
            continue

        # Rotate user agent and refresh driver every N competitions
        if i % rotation_interval == 0 and i != 0:
            print(f"\nRotating user agent after {rotation_interval} competitions")
            print(f"Old User Agent: {scraper.user_agent}")
            scraper.refresh_driver(args.headless)
            print(f"New User Agent: {scraper.user_agent}\n")

        print(f"Processing: {url} (Competition: {competition_name})")
        try:
            # Process main competition page
            competition_data = scraper.extract_competition_data(url)
            competition_data['competition_url'] = url

            # Process data page
            data_url = f"{url.rstrip('/')}/data"
            print(f"Processing data page: {data_url}")
            try:
                data_metadata = scraper.extract_data_metadata(data_url)
                competition_data['data'] = data_metadata
            except Exception as e:
                print(f"Failed to process data page: {str(e)}")
                competition_data['data'] = None

            metadata[competition_name] = competition_data
            save_json(metadata, metadata_path)
            
            # Download data if available
            # if scraper.download_data(data_url):
            #     print("Data download initiated")
            # else:
            #     print("Skipping data download")
            
            # # Download leaderboard if available
            # leaderboard_url = f"{url.rstrip('/')}/leaderboard"
            # if scraper.download_leaderboard(leaderboard_url):
            #     print("Leaderboard download initiated")
            # else:
            #     print("Skipping leaderboard download")
            
            # Random delays
            time.sleep(random.uniform(2, 5))
            if i % random.randint(5, 10) == 0:
                sleep_time = random.uniform(1, 5)
                print(f"Random anti-detection delay: {sleep_time:.1f} seconds")
                time.sleep(sleep_time)
                
        except Exception as e:
            print(f"Failed to process {url}: {str(e)}")
            save_json(metadata, metadata_path)
            print("Progress saved. Continuing...")
            continue

    scraper.close()
    print("Scraping completed successfully")

def load_json(file_path):
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"File {file_path} not found")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in {file_path}")
    except Exception as e:
        raise RuntimeError(f"Error loading {file_path}: {str(e)}")

def save_json(data, file_path):
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving {file_path}: {str(e)}")
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Kaggle Competition Scraper')
    parser.add_argument('--test', action='store_true',
                       help='Run in test mode (only processes Titanic competition)')
    parser.add_argument('--no-headless', action='store_false', dest='headless',
                       help='Disable headless mode (show browser window)')
    parser.add_argument('--data-dir', default='./data/test',
                       help='Directory for input/output data (default: ./data/test)')
    parser.add_argument('--rotation-interval', type=int, default=30,
                       help='Number of competitions between user agent rotations (default: 30)')
    parser.add_argument('--output-dir', default='./data/dataset',
                          help='Directory for output data (default: ./data/dataset)')
    args = parser.parse_args()

    # Adjust output directory for test mode
    if args.test:
        args.output_dir = './data/test/dataset'
    main(args)