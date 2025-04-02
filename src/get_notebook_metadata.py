import os
import random
import time
import json
import traceback
import re
import undetected_chromedriver as uc
import argparse
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from functools import wraps

# Constants
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CHECKPOINT_FILE = os.path.join(DATA_DIR, 'competition_list.json')

# Sorting options
SORT_OPTIONS = {
    'voteCount': 'Vote Count (Default)',
    'commentCount': 'Comment Count',
    'dateCreated': 'Date Created',
    'scoreDescending': 'Score (High to Low)',
    'scoreAscending': 'Score (Low to High)'
}

# Helper functions
def load_json(filepath):
    """Load data from a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"Error loading from {filepath}: {e}")
        return None

def save_json(data, filepath):
    """Save data to a JSON file."""
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"✅ Saved data to {filepath}")

def load_competitions():
    """Load competitions data from the checkpoint file."""
    if os.path.exists(CHECKPOINT_FILE):
        comps = load_json(CHECKPOINT_FILE)
        if comps:
            print(f"Loaded {len(comps)} competitions from checkpoint.")
            return comps
    return []

def random_sleep(mean=1.0, std=0.3):
    """Sleep for a random duration with normal distribution."""
    delay = max(0, random.normalvariate(mean, std))
    time.sleep(delay)

def print_progress(current, total, prefix='', bar_length=40):
    """Print a progress bar."""
    fraction = current / total if total else 1
    arrow = int(fraction * bar_length) * '='
    spaces = (bar_length - len(arrow)) * ' '
    print(f'\r{prefix}[{arrow}{spaces}] {current}/{total}', end='', flush=True)
    if current >= total:
        print()  # New line when complete

def setup_driver():
    """Initialize undetected_chromedriver with options."""
    options = uc.ChromeOptions()
    # options.add_argument('--headless')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36")
    options.add_argument('--disable-blink-features=AutomationControlled')
    return uc.Chrome(options=options)

class NotebookDownloader:
    def __init__(self, driver, target_count=50, test_mode=False, sort_by='voteCount'):
        self.driver = driver
        self.target_count = target_count
        self.test_mode = test_mode
        self.sort_by = sort_by
        
    def get_notebook_path(self, competition_folder, notebook_slug):
        """Get potential notebook file paths including .py and .R"""
        base = os.path.join(competition_folder, notebook_slug)
        return [
            f"{base}.ipynb",  # Jupyter Notebook
            f"{base}.Rmd",    # R Markdown
            f"{base}.py",     # Python script
            f"{base}.R"       # R script
        ]
    
    def file_exists(self, *filepaths):
        """Check if any of the given filepaths exist."""
        return any(os.path.exists(path) for path in filepaths)
        
    def collect_solution_metadata(self, url):
        """Scroll and collect solution metadata from a competition's code page."""
        self.driver.get(url)
        collected = {}
        print(f"\nCollecting solutions from {url}...")
        
        while len(collected) < self.target_count:
            # Wait for solution cards to load
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_all_elements_located((By.XPATH, "//li[contains(@class, 'MuiListItem-root')]"))
            )
            # random wait to ensure the page has loaded properly
            random_sleep(2, 0.5)
            # Get all solution cards
            cards = self.driver.find_elements(By.XPATH, "//li[contains(@class, 'MuiListItem-root')]")
            
            new_added = 0
            
            # Process each card
            for card in cards:
                outer_html = card.get_attribute("outerHTML")
                if "Upvote" not in outer_html:
                    continue
                try:
                    score_elem = card.find_element(By.XPATH, ".//span[contains(text(), 'Score')]")
                    score = float(re.search(r"Score: (\d+\.\d+)", score_elem.text).group(1))
                except (NoSuchElementException, AttributeError):
                    score = 0.0
                # Extract solution URL
                a_elem = card.find_element(By.XPATH, ".//a[contains(@class, 'sc-uYFMi') and contains(@href, '/code/')]")
                solution_url = a_elem.get_attribute("href")
                
                # Extract votes
                votes_elem = card.find_element(By.XPATH, ".//span[contains(@aria-label, 'votes')]")
                votes_text = votes_elem.get_attribute("aria-label")
                votes_match = re.search(r"(\d+)\s*votes?", votes_text)
                votes = int(votes_match.group(1)) if votes_match else 0
                
                # Try to extract comment count
                comment_count = 0
                try:
                    comment_elems = card.find_elements(By.XPATH, ".//a[contains(@href, '/comments')]")
                    if comment_elems:
                        comment_match = re.search(r"(\d+)", comment_elems[0].text)
                        comment_count = int(comment_match.group(1)) if comment_match else 0
                except Exception:
                    pass

                # Try to extract date created
                date_created = ""
                try:
                    date_elems = card.find_elements(By.XPATH, ".//span[contains(text(), 'Updated')]//span[@title]")
                    if date_elems:
                        date_created = date_elems[0].get_attribute("title")  # Extracts the full timestamp
                except Exception:
                    pass
                # Extract notebook slug
                parsed_url = urlparse(solution_url)
                path_segments = parsed_url.path.strip('/').split('/')
                notebook_slug = path_segments[2] if len(path_segments) >= 3 else ""
                
                # Add if new solution
                if solution_url not in collected:
                    new_added += 1
                    collected[solution_url] = {
                        "score": score, 
                        "votes": votes,
                        "comments": comment_count,
                        "date_created": date_created,
                        "notebook_slug": notebook_slug
                    }
                    print_progress(len(collected), self.target_count, prefix='Metadata collected: ')
                    
                    if len(collected) >= self.target_count:
                        break
            
            # Continue scrolling only if new content was found
            if new_added > 0:
                self._scroll_page(cards, new_added)
            else:
                print("No new content detected. Trying one more scroll...")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                random_sleep(2, 0.5)
                
                # If still no new content after extra scroll, we might be at the end
                if new_added == 0:
                    print(f"\nNo more content to load. Found {len(collected)} solutions.")
                    break
                
        print(f"\nFinished collecting. Total solutions found: {len(collected)}")
        return collected
    
    def _scroll_page(self, cards, new_items_count):
        """Scroll the page using multiple methods to load more content."""
        try:
            # Method 1: Scroll to last card
            if cards:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                    cards[-1]
                )
            
            # Method 2: Scroll by viewport height
            self.driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")
            
            # Method 3: Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Dynamic wait based on number of new items
            load_time = max(1.5, new_items_count/10)
            random_sleep(load_time, 0.5)
        except Exception as e:
            print(f"Error during scrolling: {str(e)}")
    
    def download_solution(self, solution_url, competition_folder):
        """Navigate to solution URL and download the notebook."""
        # Parse URL to get notebook slug
        parsed_url = urlparse(solution_url)
        path_segments = parsed_url.path.strip('/').split('/')
        
        if len(path_segments) < 3 or path_segments[0] != 'code':
            print(f"❌ Invalid solution URL structure: {solution_url}")
            return False
            
        notebook_slug = path_segments[2]
        possible_paths = self.get_notebook_path(competition_folder, notebook_slug)
        
        # Skip if any format already exists
        existing_file = next((p for p in possible_paths if os.path.exists(p)), None)
        if existing_file:
            print(f"✓ Notebook '{os.path.basename(existing_file)}' already exists. Skipping download.")
            return True
            
        # Create folder if it doesn't exist
        os.makedirs(competition_folder, exist_ok=True)
        
        # Set download path
        self.driver.execute_cdp_cmd("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": os.path.abspath(competition_folder)
        })
        
        # Navigate to solution page
        self.driver.get(solution_url)
        WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        return self._try_download(notebook_slug, competition_folder)
    
    def _try_download(self, notebook_slug,competition_folder):
        """Try multiple methods to download the notebook."""
        possible_paths = self.get_notebook_path(competition_folder, notebook_slug)
    
        # Check if any format already exists
        existing_file = next((p for p in possible_paths if os.path.exists(p)), None)
        if existing_file:
            print(f"✓ Notebook '{os.path.basename(existing_file)}' already exists. Skipping download.")
            return True
        # Finding more options button
        try:
            more_options_btn = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((
                    By.XPATH, "//button[contains(@aria-label, 'More options for this notebook')]"
                ))
            )
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                more_options_btn
            )
            more_options_btn.click()
        except Exception as e:
            print(f"❌ Failed at more options button: {str(e)}")
            return False

        # Finding download menu item
        try:
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "ul.MuiMenu-list"))
            )
            menu_items = self.driver.find_elements(By.CSS_SELECTOR, "li.MuiMenuItem-root")
            download_item = next((item for item in menu_items if "Download code" in item.text), None)
            
            if download_item is None:
                raise Exception("Could not find 'Download code' in menu items")
                
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                download_item
            )
            random_sleep(1, 0.2)
        except Exception as e:
            print(f"❌ Failed to find download item: {str(e)}")
            return False

        def check_file_downloaded():
            return any(os.path.exists(p) for p in possible_paths)
        
        # Method 1: ActionChains click
        try:
            ActionChains(self.driver).move_to_element(download_item).pause(0.5).click().perform()
            WebDriverWait(self.driver, 10).until(lambda _: check_file_downloaded())
            self._report_success(notebook_slug, possible_paths)
            return True
        except Exception as e:
            print(f"❌ Primary click failed: {str(e)}")
        
        # Method 2: JavaScript click
        try:
            print("🔄 Attempting JavaScript click")
            self.driver.execute_script("arguments[0].click();", download_item)
            WebDriverWait(self.driver, 10).until(lambda _: check_file_downloaded())
            self._report_success(notebook_slug, possible_paths)
            return True
        except Exception as e:
            print(f"❌ JavaScript click failed: {str(e)}")
        
        # Method 3: Direct element click
        try:
            print("🔄 Attempting direct element click")
            download_item.click()
            WebDriverWait(self.driver, 10).until(lambda _: check_file_downloaded())
            self._report_success(notebook_slug, possible_paths)
            return True
        except Exception as e:
            print(f"❌ All click attempts failed: {str(e)}")
            return False
    
    def _report_success(self, notebook_slug, possible_paths):
        """Report which file was successfully downloaded."""
        downloaded = [p for p in possible_paths if os.path.exists(p)]
        if downloaded:
            for path in downloaded:
                print(f"✅ Downloaded '{os.path.basename(path)}' successfully.")
        else:
            print("❌ Download completed but no file found")
    
    def process_competition(self, competition):
        """Process a competition: collect metadata and download notebooks."""
        slug = competition.get("competition_name")
        
        # Set paths based on test mode
        if self.test_mode:
            base_folder = os.path.join(DATA_DIR, 'test', 'notebooks', slug)
        else:
            base_folder = os.path.join(DATA_DIR, 'notebooks', slug)
        
        # Ensure base folder and metadata subfolder exist
        os.makedirs(os.path.join(base_folder, 'metadata'), exist_ok=True)
        # Sort-specific metadata path
        metadata_path = os.path.join(base_folder, 'metadata', f"notebooks_metadata_{self.sort_by}.json")
        
        # Also maintain a master metadata file that tracks all downloaded notebooks
        master_metadata_path = os.path.join(base_folder, 'metadata', "all_notebooks_metadata.json")
        
        # Load or initialize master metadata
        master_metadata = {}
        if os.path.exists(master_metadata_path):
            master_metadata = load_json(master_metadata_path) or {}
        
        # Construct code page URL with sorting parameter
        base_code_url = competition.get("code_url")
        code_page_url = f"{base_code_url}?sortBy={self.sort_by}&excludeNonAccessedDatasources=true"
        print(f"\nProcessing competition '{slug}' using URL: {code_page_url}")
        print(f"Sorting by: {SORT_OPTIONS.get(self.sort_by, 'Unknown')}")
        
        # Handle metadata collection
        solution_urls = {}
        if os.path.exists(metadata_path):
            print(f"Loading existing metadata from {metadata_path}...")
            solution_urls = load_json(metadata_path) or {}
            
            if len(solution_urls) < self.target_count:
                print(f"Need {self.target_count - len(solution_urls)} more entries. Collecting additional solutions...")
                new_solutions = self.collect_solution_metadata(code_page_url)
                
                # Merge with existing metadata
                for url, data in new_solutions.items():
                    if url not in solution_urls:
                        solution_urls[url] = data
                        
                save_json(solution_urls, metadata_path)
        else:
            print("No existing metadata found. Collecting solution URLs...")
            solution_urls = self.collect_solution_metadata(code_page_url)
            save_json(solution_urls, metadata_path)
        
        # Download notebooks
        total_solutions = len(solution_urls)
        downloaded_count = 0
        already_downloaded_count = 0
        print("\nStarting notebook downloads...")
        
        # Check which notebooks we've already downloaded according to master metadata
        for url in solution_urls.keys():
            # Skip if URL is already in master metadata
            if url in master_metadata:
                already_downloaded_count += 1
            # # Get notebook slug from URL or metadata
            # notebook_slug = data.get("notebook_slug", "")
            # if not notebook_slug:
            #     parsed_url = urlparse(url)
            #     path_segments = parsed_url.path.strip('/').split('/')
            #     if len(path_segments) >= 3 and path_segments[0] == 'code':
            #         notebook_slug = path_segments[2]
        
                
        if already_downloaded_count > 0:
            print(f"Found {already_downloaded_count} notebooks that have already been downloaded.")
            
        # Process each solution for downloading
        skipped_count = 0
        for idx, (sol_url, data) in enumerate(solution_urls.items(), start=1):
            print_progress(idx, total_solutions, prefix='Download progress: ')
            
            # Get notebook slug
            notebook_slug = data.get("notebook_slug", "")
            if not notebook_slug:
                parsed_url = urlparse(sol_url)
                path_segments = parsed_url.path.strip('/').split('/')
                if len(path_segments) >= 3 and path_segments[0] == 'code':
                    notebook_slug = path_segments[2]
                else:
                    print(f"❌ Invalid URL structure: {sol_url}")
                    skipped_count += 1
                    continue
            
            # Check if notebook is already in master metadata
            if sol_url in master_metadata:
                print(f"✓ Notebook '{notebook_slug}' already recorded in master metadata. Skipping.")
                downloaded_count += 1
                continue
                
            # Check if notebook file already exists
            possible_paths = self.get_notebook_path(base_folder, notebook_slug)
            if self.file_exists(*possible_paths):
                existing_file = next(p for p in possible_paths if os.path.exists(p))
                print(f"✓ Notebook '{os.path.basename(existing_file)}' already exists but not in metadata. Adding to metadata.")
                master_metadata[sol_url] = {
                    "notebook_name": notebook_slug,
                    "sort_by": self.sort_by,
                    "score": data.get("score", 0),
                    "votes": data.get("votes", 0),
                    "comments": data.get("comments", 0),
                    "date_created": data.get("date_created", ""),
                    "downloaded": True
                }
                downloaded_count += 1
                continue
            
            # If not already downloaded, attempt download
            success = self.download_solution(sol_url, base_folder)
            if success:
                # Add to master metadata
                master_metadata[sol_url] = {
                    "notebook_name": notebook_slug,
                    "sort_by": self.sort_by,
                    "score": data.get("score", 0),
                    "votes": data.get("votes", 0),
                    "comments": data.get("comments", 0),
                    "date_created": data.get("date_created", ""),
                    "downloaded": True
                }
                downloaded_count += 1
                # Save master metadata after each successful download
                save_json(master_metadata, master_metadata_path)
            else:
                print(f"\nSkipping solution: {sol_url}")
                skipped_count += 1
                
            random_sleep(5, 1)
        
        # Final save of master metadata
        save_json(master_metadata, master_metadata_path)
        
        print(f"\nDownload complete for {self.sort_by} sorting:")
        print(f"- Total solutions processed: {total_solutions}")
        print(f"- Successfully downloaded: {downloaded_count - already_downloaded_count}")
        print(f"- Already downloaded: {already_downloaded_count}")
        print(f"- Skipped: {skipped_count}")
        print(f"- All notebooks saved to: {base_folder}")

def main():
    parser = argparse.ArgumentParser(description="Kaggle Competition Notebook Downloader")
    parser.add_argument(
        '--competition', type=str, default=None,
        help="Optional competition slug to process a specific competition."
    )
    parser.add_argument(
        '--test', action='store_true', default=False,
        help="Enable test mode: only process 'titanic' competition and store in test directory."
    )
    parser.add_argument(
        '--target_count', type=int, default=50,
        help="Target number of solution URLs to collect."
    )
    parser.add_argument(
        '--sort_by', type=str, choices=list(SORT_OPTIONS.keys()), default='voteCount',
        help="Sort method for notebooks: voteCount (default), commentCount, dateCreated, scoreDescending, scoreAscending"
    )
    args = parser.parse_args()

    # Print sort options
    print("Available sorting options:")
    for key, desc in SORT_OPTIONS.items():
        print(f"  - {key}: {desc}")
    print(f"Selected sorting: {SORT_OPTIONS.get(args.sort_by, 'Unknown')}")

    # Load competitions
    competitions = load_competitions()
    if not competitions:
        print("No competitions to process. Exiting.")
        return

    # Filter competitions based on arguments
    if args.test:
        competitions = [comp for comp in competitions if comp.get("competition_name", "").lower() == "titanic"]
        if not competitions:
            print("Test mode active but no 'titanic' competition found. Exiting.")
            return
    elif args.competition:
        competitions = [comp for comp in competitions if comp.get("competition_name", "").lower() == args.competition.lower()]
        if not competitions:
            print(f"No competition found with slug '{args.competition}'. Exiting.")
            return

    # Setup and run downloader
    driver = setup_driver()
    downloader = NotebookDownloader(driver, args.target_count, args.test, args.sort_by)
    
    try:
        for comp in competitions:
            try:
                downloader.process_competition(comp)
                if args.test:
                    break
            except Exception as e:
                print(f"Error processing competition {comp.get('competition_name', 'unknown')}:")
                traceback.print_exc()
    finally:
        driver.quit()
        print("All competitions processed.")

if __name__ == '__main__':
    main()