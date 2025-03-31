import os
import time
import json
import re
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

# File to store checkpoint data (scraped competitions)
CHECKPOINT_FILE = 'competitions_checkpoint.json'

def save_checkpoint(data):
    """Save the list of competitions to a JSON file."""
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Checkpoint saved with {len(data)} entries.")

def load_checkpoint():
    """Load competitions data from the checkpoint file if it exists."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            try:
                data = json.load(f)
                print(f"Loaded checkpoint with {len(data)} entries.")
                return data
            except Exception as e:
                print("Error loading checkpoint:", e)
    return []

def setup_driver():
    """Set up an undetected_chromedriver with options to bypass anti-scraping measures."""
    options = uc.ChromeOptions()
    # Uncomment the line below to run headless:
    # options.add_argument('--headless')
    
    # Set a common user-agent string
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36")
    
    # Additional options to help bypass detection can be added here
    options.add_argument('--disable-blink-features=AutomationControlled')
    # Other options or proxy settings can be added as needed.
    
    driver = uc.Chrome(options=options)
    return driver

def click_explore_button(driver):
    """Click the 'Explore all competitions' button if it exists."""
    try:
        # The button may be a <button> or <a> element containing "Explore all competitions".
        explore_button = driver.find_element(By.XPATH, "//*[contains(text(), 'Explore all competitions')]")
        explore_button.click()
        print("Clicked 'Explore all competitions' button.")
        time.sleep(5)  # Allow time for the page to update after clicking.
    except NoSuchElementException:
        print("'Explore all competitions' button not found. Continuing without click.")
    except Exception as e:
        print("Error clicking the 'Explore all competitions' button:", e)

def scrape_page(driver, url, scraped_slugs):
    """Scrape competitions from a given page URL."""
    driver.get(url)
    time.sleep(5)  # Wait for the page to load.
    competitions_found = []
    
    # Find competition link elements; links that include '/competitions/'.
    competition_elements = driver.find_elements(By.XPATH, "//a[contains(@href, '/competitions/')]")
    print(f"Found {len(competition_elements)} competition link elements on {url}.")
    
    for element in competition_elements:
        try:
            comp_url = element.get_attribute('href')
            # Extract the competition slug from the URL.
            parts = comp_url.rstrip('/').split('/')
            if 'competitions' in parts:
                idx = parts.index('competitions')
                if idx + 1 < len(parts):
                    slug = parts[idx + 1]
                else:
                    continue
            else:
                continue

            # Skip if we've already processed this competition.
            if slug in scraped_slugs:
                continue

            # Extract teams count from a nearby element's text.
            try:
                parent_text = element.find_element(By.XPATH, "..").text
            except Exception:
                parent_text = ""
            teams_match = re.search(r'([\d,]+)\s*teams', parent_text, re.IGNORECASE)
            if teams_match:
                teams_count = int(teams_match.group(1).replace(',', ''))
            else:
                continue

            # Only include competitions with more than 100 teams.
            if teams_count < 100:
                continue

            comp_data = {
                'slug': slug,
                'competition_url': comp_url.rstrip('/'),
                'code_url': comp_url.rstrip('/') + '/code',
                'teams_count': teams_count
            }
            competitions_found.append(comp_data)
            scraped_slugs.add(slug)
            print(f"Added competition: {slug} with {teams_count} teams")
        except Exception as e:
            print("Error processing an element:", e)
            continue
    
    return competitions_found

def scrape_competitions():
    """Scrape Kaggle competitions with >100 teams by first clicking the explore button for page 1,
    then iterating through pages 2 onward.
    
    Checkpointing allows resuming if the script stops unexpectedly.
    """
    driver = setup_driver()
    
    # Start at base URL and click the button to load the first page.
    base_url = 'https://www.kaggle.com/competitions?sortOption=numTeams'
    driver.get(base_url)
    time.sleep(5)
    click_explore_button(driver)
    
    competitions = load_checkpoint()
    scraped_slugs = {comp['slug'] for comp in competitions}
    
    # Scrape page 1 (after clicking the button, the first page is loaded).
    print("Scraping page 1...")
    competitions += scrape_page(driver, driver.current_url, scraped_slugs)
    save_checkpoint(competitions)
    
    # Now scrape subsequent pages (page 2 onward)
    page = 2
    while True:
        url = f"https://www.kaggle.com/competitions?sortOption=numTeams&page={page}"
        print(f"Processing page {page}: {url}")
        comps_found = scrape_page(driver, url, scraped_slugs)
        if not comps_found:
            print(f"No new competitions found on page {page}. Ending pagination.")
            break
        competitions += comps_found
        save_checkpoint(competitions)
        page += 1

    driver.quit()
    return competitions

if __name__ == '__main__':
    comps = scrape_competitions()
    print("\nScraped Competitions (with over 100 teams):")
    for comp in comps:
        print(comp)