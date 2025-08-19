import os
import time
import requests
import PyPDF2
import io
import sys
import json
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from datetime import datetime, timedelta
from app import database

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3')

def setup_webdriver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(f"user-agent={USER_AGENT}")
    try:
        return webdriver.Chrome(options=chrome_options)
    except Exception as e:
        print(f"!!! WebDriver initialization error: {e}")
        return None

def extract_text_from_pdf(pdf_content):
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
        text = "".join(page.extract_text() for page in reader.pages if page.extract_text())
        return text.strip() or None
    except Exception:
        return None

def find_document_links_with_ai(html_content):
    """
    Uses an LLM to find document links in the HTML of a page.
    """
    print("      - Using AI to find document links...")
    prompt = f"""
    You are an expert web scraping assistant. Analyze the following HTML content and identify all hyperlinks (`<a>` tags) that likely lead to transportation planning documents. These documents might be called 'Metropolitan Transportation Plan', 'Transportation Improvement Program', 'Long-Range Plan', 'Meeting Minutes', 'Agendas', 'ITS Architecture', or similar.

    Return ONLY a JSON object with a single key "document_urls", where the value is a list of the full, absolute URLs. Do not include duplicates. If no relevant documents are found, return an empty list.

    HTML Content:
    ```html
    {html_content}
    ```
    """
    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate", json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, headers={'Content-Type': 'application/json'})
        response.raise_for_status()

        response_text = response.json().get('response', '{}').strip()
        # Find the JSON part of the response, in case the LLM adds extra text
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start == -1 or json_end == 0:
            print("      - AI did not return a valid JSON object.")
            return []

        json_response = json.loads(response_text[json_start:json_end])
        urls = json_response.get("document_urls", [])
        print(f"      - AI identified {len(urls)} potential document links.")
        return urls
    except Exception as e:
        print(f"      - ERROR connecting to the AI model or parsing its response: {e}")
        return []

def download_documents_from_url(driver, agency_id, conn, page_url, doc_type, use_ai_finder=False):
    try:
        driver.get(page_url)
        time.sleep(2)  # Allow time for dynamic content to load

        doc_urls = []
        if use_ai_finder:
            html_content = driver.page_source
            ai_urls = find_document_links_with_ai(html_content)
            # Make sure URLs are absolute
            doc_urls = [urljoin(page_url, url) for url in ai_urls]
        else:
            # Fallback to simple PDF link finding
            pdf_links = driver.find_elements(By.TAG_NAME, 'a')
            doc_urls = {urljoin(page_url, link.get_attribute('href')) for link in pdf_links if link.get_attribute('href') and link.get_attribute('href').lower().endswith('.pdf')}

        cur = conn.cursor()
        p_style = database.get_param_style()

        print(f"      - Found {len(doc_urls)} links to process.")
        for doc_url in doc_urls:
            cur.execute(f"SELECT 1 FROM documents WHERE url = {p_style}", (doc_url,))
            if cur.fetchone(): continue

            print(f"        - Downloading document: {doc_url}")
            try:
                response = requests.get(doc_url, headers={'User-Agent': USER_AGENT}, timeout=30)
                response.raise_for_status()

                # Basic check for PDF content type
                if 'application/pdf' not in response.headers.get('Content-Type', ''):
                    print("          - Skipping non-PDF link.")
                    continue

                text = extract_text_from_pdf(response.content)
                if text:
                    now_func = "NOW()" if database.get_db_type() == 'postgres' else "datetime('now')"
                    sql = f"INSERT INTO documents (agency_id, document_type, url, raw_text, scraped_date, publication_date) VALUES ({p_style}, {p_style}, {p_style}, {p_style}, {now_func}, {p_style}) {database.get_on_conflict_clause()}"

                    try:
                        cur.execute(sql, (agency_id, doc_type, doc_url, text, datetime.now().date()))
                    except Exception as e:
                        if "UNIQUE constraint failed" in str(e): pass
                        else: raise e
                conn.commit()
            except requests.RequestException as e:
                print(f"          - ERROR downloading document: {e}")
                pass
    except WebDriverException as e:
        print(f"      - ERROR accessing page {page_url}: {e}")
        pass

def scrape_all_agencies(target_agency_ids=None, use_ai_finder=False):
    print("  - Scraping agency documents...")
    driver = setup_webdriver()
    conn = database.get_db_connection()
    if not driver or not conn: return
    cur = conn.cursor()

    if target_agency_ids:
        print(f"    - Scraping for {len(target_agency_ids)} target agencies.")
        placeholders = ','.join(database.get_param_style() for _ in target_agency_ids)
        cur.execute(f"SELECT agency_id, name, planning_url, minutes_url FROM agencies WHERE agency_id IN ({placeholders})", target_agency_ids)
    else:
        print("    - Scraping for all agencies.")
        cur.execute("SELECT agency_id, name, planning_url, minutes_url FROM agencies")
    agencies = cur.fetchall()

    for agency_id, name, planning_url, minutes_url in agencies:
        print(f"    - Checking '{name}' for documents...")
        if planning_url:
            download_documents_from_url(driver, agency_id, conn, planning_url, "Planning Document", use_ai_finder)
        if minutes_url:
            download_documents_from_url(driver, agency_id, conn, minutes_url, "Meeting Minutes", use_ai_finder)

    driver.quit()
    conn.close()

def scrape_news_for_agencies(target_agency_ids=None):
    print("  - Harvesting news articles...")
    api_key = os.environ.get('NEWS_API_KEY')
    if not api_key or 'YOUR_ACTUAL_API_KEY' in api_key:
        print("    - WARNING: NEWS_API_KEY not set. Skipping.")
        return

    conn = database.get_db_connection()
    if not conn: return
    cur = conn.cursor()

    if target_agency_ids:
        placeholders = ','.join(database.get_param_style() for _ in target_agency_ids)
        cur.execute(f"SELECT agency_id, name FROM agencies WHERE agency_id IN ({placeholders})", target_agency_ids)
    else:
        order_by = "RANDOM()" if database.get_db_type() == 'sqlite' else "RANDOM()"
        cur.execute(f"SELECT agency_id, name FROM agencies ORDER BY {order_by} LIMIT 20")
    agencies_to_query = cur.fetchall()

    from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    for agency_id, agency_name in agencies_to_query:
        print(f"    - Searching news for '{agency_name}'...")
        query = f'"{agency_name}" AND (transportation OR transit OR procurement)'
        url = f"https://newsapi.org/v2/everything?q={requests.utils.quote(query)}&from={from_date}&sortBy=relevancy&apiKey={api_key}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            articles = response.json().get('articles', [])
            if not articles: continue

            for a in articles[:5]:
                sql = f"INSERT {database.get_on_conflict_clause()} INTO news_articles (agency_id, article_url, title, source_name, published_date, content) VALUES ({database.get_param_style()}, {database.get_param_style()}, {database.get_param_style()}, {database.get_param_style()}, {database.get_param_style()}, {database.get_param_style()})"
                cur.execute(sql, (agency_id, a['url'], a['title'], a['source']['name'], a['publishedAt'], a.get('description')))
            conn.commit()
            time.sleep(1)
        except requests.RequestException as e:
            print(f"      - ERROR fetching news: {e}")
            pass
    if conn: conn.close()

def scrape_historical_solicitations_from_sam(years=5):
    print("--- Scraping Historical Solicitations from SAM.gov ---")
    api_key = os.environ.get('SAM_API_KEY')
    if not api_key or 'YOUR_SAM_API_KEY' in api_key:
        print("    - CRITICAL: SAM_API_KEY not set in .env file. Cannot scrape historical data.")
        return

    conn = database.get_db_connection()
    if not conn: return
    cur = conn.cursor()

    ITS_NAICS_CODES = ["541512", "541330", "541715", "334511"]
    today = datetime.now()

    for year_offset in range(years):
        target_year = today.year - year_offset
        posted_from = f"01/01/{target_year}"
        posted_to = f"12/31/{target_year}"
        print(f"  - Fetching data for year: {target_year}")

        for ncode in ITS_NAICS_CODES:
            offset = 0
            while True:
                params = {'api_key': api_key, 'postedFrom': posted_from, 'postedTo': posted_to, 'ncode': ncode, 'limit': 1000, 'offset': offset}
                try:
                    response = requests.get("https://api.sam.gov/opportunities/v2/search", params=params)
                    response.raise_for_status()
                    data = response.json()
                    opportunities = data.get("opportunitiesData", [])
                    if not opportunities: break

                    for opp in opportunities:
                        like_op = "LIKE" if database.get_db_type() == 'sqlite' else "ILIKE"
                        cur.execute(f"SELECT agency_id FROM agencies WHERE name {like_op} {database.get_param_style()}", (f"%{opp.get('fullParentPathName', '')}%",))
                        agency_result = cur.fetchone()
                        agency_id = agency_result[0] if agency_result else None
                        release_date = opp.get('postedDate')
                        title = opp.get('title')
                        url = opp.get('uiLink')

                        if release_date and title and url:
                            sql = f"INSERT {database.get_on_conflict_clause()} INTO historical_solicitations (agency_id, release_date, title, url, keywords) VALUES ({database.get_param_style()}, {database.get_param_style()}, {database.get_param_style()}, {database.get_param_style()}, {database.get_param_style()})"
                            keywords_val = ncode if database.get_db_type() == 'sqlite' else [ncode]
                            cur.execute(sql, (agency_id, release_date, title, url, keywords_val))

                    conn.commit()
                    if len(opportunities) < 1000: break
                    offset += 1000
                    time.sleep(1)
                except requests.RequestException as e:
                    print(f"    - ERROR fetching data for NAICS {ncode}: {e}")
                    break
    conn.close()
    print("--- Historical scraping complete. ---")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--historical':
        scrape_historical_solicitations_from_sam()
    else:
        print("Running standard scrapers...")
        scrape_all_agencies()
        scrape_news_for_agencies()
