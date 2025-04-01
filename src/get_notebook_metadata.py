import os
import random
import time
import json
import traceback
import re
import argparse
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

def load_competitions(checkpoint_file):
    """Load competitions data from the checkpoint JSON file."""
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, 'r') as f:
            try:
                comps = json.load(f)
                print(f"Loaded {len(comps)} competitions from checkpoint.")
                return comps
            except Exception as e:
                print("Error loading checkpoint:", e)
    return []

def save_json(data, filepath):
    """Save data as JSON to the given filepath."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Saved JSON data to {filepath}")

def setup_driver(download_dir):
    """Initialize undetected_chromedriver with download preferences."""
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Set download preferences
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    
    driver = uc.Chrome(options=options)
    driver.maximize_window()
    return driver

def scroll_and_collect_solutions(driver, url, target_count=50):
    driver.get(url)
    collected = []
    
    while len(collected) < target_count:
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, "//li[contains(@class, 'MuiListItem-root')]"))
            )
            cards = driver.find_elements(By.XPATH, "//li[contains(@class, 'MuiListItem-root')]")
            
            for card in cards:
                if len(collected) >= target_count:
                    break
                
                try:
                    # Extract metadata
                    metadata = {
                        'url': card.find_element(By.XPATH, ".//a[contains(@href, '/code/')]").get_attribute("href"),
                        'score': None,
                        'votes': None
                    }

                    # Extract score if available
                    score_elem = card.find_elements(By.XPATH, ".//span[contains(text(), 'Score: ')]")
                    if score_elem:
                        score_match = re.search(r"Score: (\d+\.\d+)", score_elem[0].text)
                        metadata['score'] = float(score_match.group(1)) if score_match else None

                    # Extract votes if available
                    vote_elem = card.find_elements(By.XPATH, ".//span[contains(@class, 'vote-count')]")
                    if vote_elem:
                        metadata['votes'] = int(vote_elem[0].text.strip())

                    collected.append(metadata)
                    print(f"Collected: {metadata['url']}")

                except Exception as e:
                    print(f"Error processing card: {str(e)}")
                    continue

            # Scroll to load more
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
        except Exception as e:
            print(f"Error during collection: {str(e)}")
            break

    return collected[:target_count]

def download_solution(driver, solution_url, competition_folder, download_dir):
    """Download notebook code with improved error handling"""
    try:
        # Configure download path
        driver.execute_cdp_cmd("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": os.path.abspath(download_dir)
        })

        driver.get(solution_url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        
        # Click more options button
        more_options_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'More options')]")))
        ActionChains(driver).move_to_element(more_options_btn).click().perform()
        
        # Click download button
        download_item = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//*[normalize-space()='Download code']")))
        download_item.click()
        
        # Verify download
        WebDriverWait(driver, 30).until(
            lambda d: any(fname.endswith('.ipynb') for fname in os.listdir(download_dir)))
        return True
    except Exception as e:
        print(f"Download failed: {traceback.format_exc()}")
        return False

def process_competition(driver, comp, args):
    """Process a single competition with configurable parameters"""
    comp_slug = comp.get("slug")
    comp_folder = os.path.join(args.download_dir, comp_slug)
    
    # Create folder structure
    os.makedirs(comp_folder, exist_ok=True)
    
    # Collect solutions metadata
    code_page_url = f"{comp['code_url']}?sortBy=voteCount"
    solutions = scroll_and_collect_solutions(driver, code_page_url, args.num_notebooks)
    
    # Save metadata
    metadata_path = os.path.join(args.metadata_dir, f"{comp_slug}_metadata.json")
    save_json(solutions, metadata_path)
    
    # Download notebooks
    for idx, solution in enumerate(solutions):
        print(f"Downloading {idx+1}/{len(solutions)}: {solution['url']}")
        if download_solution(driver, solution['url'], comp_folder, args.download_dir):
            print("Download successful")
        else:
            print("Download failed")
        time.sleep(random.uniform(1, 3))

def main():
    parser = argparse.ArgumentParser(description='Kaggle Notebook Downloader')
    parser.add_argument('--checkpoint', default='./data/competitions_list.json',
                      help='Path to competitions checkpoint file')
    parser.add_argument('--download-dir', default='./data/notebooks',
                      help='Directory to save downloaded notebooks')
    parser.add_argument('--metadata-dir', default='./data/metadata',
                      help='Directory to save metadata files')
    parser.add_argument('--num-notebooks', type=int, default=50,
                      help='Number of notebooks to download per competition')
    parser.add_argument('--headless', action='store_true',
                      help='Run browser in headless mode')
    args = parser.parse_args()

    # Create necessary directories
    os.makedirs(args.download_dir, exist_ok=True)
    os.makedirs(args.metadata_dir, exist_ok=True)

    # Load competitions and process
    competitions = load_competitions(args.checkpoint)
    driver = setup_driver(args.download_dir)
    
    try:
        for comp in competitions:
            print(f"\nProcessing competition: {comp['slug']}")
            process_competition(driver, comp, args)
    finally:
        driver.quit()

if __name__ == '__main__':
    main()