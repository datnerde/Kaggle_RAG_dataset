import os
import time
import json
import re
import argparse
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

def save_checkpoint(data, checkpoint_file):
    """Save the list of competitions to a JSON file."""
    with open(checkpoint_file, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Checkpoint saved with {len(data)} entries to {checkpoint_file}.")

def load_checkpoint(checkpoint_file):
    """Load competitions data from the checkpoint file if it exists."""
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, 'r') as f:
            try:
                data = json.load(f)
                print(f"Loaded checkpoint from {checkpoint_file} with {len(data)} entries.")
                return data
            except Exception as e:
                print("Error loading checkpoint:", e)
    return []

def setup_driver():
    """Set up an undetected_chromedriver with options to bypass anti-scraping measures."""
    options = uc.ChromeOptions()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36")
    options.add_argument('--disable-blink-features=AutomationControlled')
    driver = uc.Chrome(options=options)
    return driver

def click_explore_button(driver):
    """Click the 'Explore all competitions' button if it exists."""
    try:
        explore_button = driver.find_element(By.XPATH, "//*[contains(text(), 'Explore all competitions')]")
        explore_button.click()
        print("Clicked 'Explore all competitions' button.")
        time.sleep(5)
    except NoSuchElementException:
        print("'Explore all competitions' button not found. Continuing without click.")
    except Exception as e:
        print("Error clicking the 'Explore all competitions' button:", e)

def scrape_page(driver, url, scraped_slugs):
    """Scrape competitions from a given page URL."""
    driver.get(url)
    time.sleep(5)
    competitions_found = []
    
    competition_elements = driver.find_elements(By.XPATH, "//a[contains(@href, '/competitions/')]")
    print(f"Found {len(competition_elements)} competition link elements on {url}.")
    
    for element in competition_elements:
        try:
            comp_url = element.get_attribute('href')
            parts = comp_url.rstrip('/').split('/')
            if 'competitions' in parts:
                idx = parts.index('competitions')
                if idx + 1 < len(parts):
                    slug = parts[idx + 1]
                else:
                    continue
            else:
                continue

            if slug in scraped_slugs:
                continue

            try:
                parent_text = element.find_element(By.XPATH, "..").text
            except Exception:
                parent_text = ""
            teams_match = re.search(r'([\d,]+)\s*teams', parent_text, re.IGNORECASE)
            if teams_match:
                teams_count = int(teams_match.group(1).replace(',', ''))
            else:
                continue

            if teams_count < 100:
                continue

            comp_data = {
                'slug': slug,
                'competition_url': comp_url.rstrip('/'),
                'code_url': comp_url.rstrip('/') + '/code',
                'data_url': comp_url.rstrip('/') + '/data',
                'teams_count': teams_count
            }
            competitions_found.append(comp_data)
            scraped_slugs.add(slug)
            print(f"Added competition: {slug} with {teams_count} teams")
        except Exception as e:
            print("Error processing an element:", e)
            continue
    
    return competitions_found

def scrape_competitions(checkpoint_file):
    """Main scraping function with checkpoint support."""
    driver = setup_driver()
    base_url = 'https://www.kaggle.com/competitions?sortOption=numTeams'
    driver.get(base_url)
    time.sleep(5)
    click_explore_button(driver)
    
    competitions = load_checkpoint(checkpoint_file)
    scraped_slugs = {comp['slug'] for comp in competitions}
    
    print("Scraping page 1...")
    competitions += scrape_page(driver, driver.current_url, scraped_slugs)
    save_checkpoint(competitions, checkpoint_file)
    
    page = 2
    while True:
        url = f"https://www.kaggle.com/competitions?sortOption=numTeams&page={page}"
        print(f"Processing page {page}: {url}")
        comps_found = scrape_page(driver, url, scraped_slugs)
        if not comps_found:
            print(f"No new competitions found on page {page}. Ending pagination.")
            break
        competitions += comps_found
        save_checkpoint(competitions, checkpoint_file)
        page += 1

    driver.quit()
    return competitions

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scrape Kaggle competitions with team counts over 100')
    parser.add_argument('--data-dir', type=str, default='./data',
                       help='Directory to store scraped data (default: ./data)')
    args = parser.parse_args()

    # Create data directory if it doesn't exist
    os.makedirs(args.data_dir, exist_ok=True)
    checkpoint_file = os.path.join(args.data_dir, 'competition_list.json')

    try:
        comps = scrape_competitions(checkpoint_file)
        print("\nScraped Competitions (with over 100 teams):")
        for comp in comps:
            print(comp)
    except Exception as e:
        print(f"Error during scraping: {e}")
        print(f"Last checkpoint saved at {checkpoint_file}")