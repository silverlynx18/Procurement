import os, time, requests, PyPDF2, io
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from datetime import datetime, timedelta
from app import database

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"

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

def download_documents_from_url(driver, agency_id, conn, page_url, doc_type):
    try:
        driver.get(page_url)
        time.sleep(1)
        pdf_urls = {urljoin(page_url, link.get_attribute('href')) for link in driver.find_elements(By.TAG_NAME, 'a') if link.get_attribute('href') and link.get_attribute('href').lower().endswith('.pdf')}

        for pdf_url in pdf_urls:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM documents WHERE url = %s", (pdf_url,))
                if cur.fetchone(): continue
            try:
                response = requests.get(pdf_url, headers={'User-Agent': USER_AGENT}, timeout=30)
                response.raise_for_status()
                text = extract_text_from_pdf(response.content)
                if text:
                    with conn.cursor() as cur:
                        # Placeholder for real date parsing
                        pub_date = datetime.now().date()
                        cur.execute("INSERT INTO documents (agency_id, document_type, url, raw_text, scraped_date, publication_date) VALUES (%s, %s, %s, %s, NOW(), %s)", (agency_id, doc_type, pdf_url, text, pub_date))
                    conn.commit()
            except requests.RequestException:
                pass
    except WebDriverException:
        pass

def scrape_all_agencies():
    print("  - Scraping agency documents...")
    driver = setup_webdriver()
    conn = database.get_db_connection()
    if not driver or not conn: return

    with conn.cursor() as cur:
        cur.execute("SELECT agency_id, name, planning_url, minutes_url FROM agencies")
        agencies = cur.fetchall()

    for agency_id, name, planning_url, minutes_url in agencies:
        if planning_url:
            download_documents_from_url(driver, agency_id, conn, planning_url, "Planning Document")

    driver.quit()
    conn.close()

def scrape_funding_sources():
    print("  - Scraping funding sources (Placeholder)...")
    pass

def scrape_news_for_agencies():
    print("  - Harvesting news articles...")
    api_key = os.environ.get('NEWS_API_KEY')
    if not api_key or 'YOUR_ACTUAL_API_KEY' in api_key:
        print("    - WARNING: NEWS_API_KEY not set. Skipping.")
        return

    conn = database.get_db_connection()
    if not conn: return

    with conn.cursor() as cur:
        cur.execute("SELECT agency_id, name FROM agencies ORDER BY RANDOM() LIMIT 20;")
        agencies_to_query = cur.fetchall()

    from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    for agency_id, agency_name in agencies_to_query:
        query = f'"{agency_name}" AND (transportation OR transit OR procurement)'
        url = f"https://newsapi.org/v2/everything?q={requests.utils.quote(query)}&from={from_date}&sortBy=relevancy&apiKey={api_key}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            articles = response.json().get('articles', [])
            if not articles: continue
            with conn.cursor() as cur:
                for a in articles[:5]:
                    cur.execute("INSERT INTO news_articles (agency_id, article_url, title, source_name, published_date, content) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT(article_url) DO NOTHING;",
                                (agency_id, a['url'], a['title'], a['source']['name'], a['publishedAt'], a.get('description')))
            conn.commit()
            time.sleep(1)
        except requests.RequestException:
            pass
    if conn: conn.close()
