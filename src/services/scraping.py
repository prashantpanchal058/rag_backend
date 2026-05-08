from playwright.sync_api import sync_playwright
import requests
from bs4 import BeautifulSoup
import sys
sys.stdout.reconfigure(encoding='utf-8')

def scrape_url_js(url: str) -> str:
    """Fallback for JS-rendered pages - returns raw HTML"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        content = page.content()  # returns full HTML, not just text
        browser.close()
        return content

def scrape_url(url: str) -> str:
    """Returns raw HTML for partition_html to process"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        
        # Check if JS-rendered (body has very little text)
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text(strip=True)
        
        if len(text) < 200:
            return scrape_url_js(url)  # fallback to Playwright
        
        return res.text  # raw HTML, not stripped text

    except Exception as e:
        raise ValueError(f"Failed to scrape {url}: {e}")