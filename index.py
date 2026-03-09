import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import psycopg2

# ----------------------------
# DATABASE CONNECTION
# ----------------------------
DB_HOST = "localhost"
DB_NAME = "web_crawler"
DB_USER = "postgres"
DB_PASSWORD = "20050114"  

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cursor = conn.cursor()
print("Connected to PostgreSQL!")

# ----------------------------
# DATABASE FUNCTIONS
# ----------------------------
def save_page(url, title, headers, meta, content, depth):
    cursor.execute("""
        INSERT INTO pages(url,title,headers,meta_data,content,depth)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (url) DO NOTHING
        RETURNING id;
    """, (url, title, headers, meta, content, depth))
    result = cursor.fetchone()
    conn.commit()
    return result[0] if result else None

def save_link(from_page_id, to_page_id):
    cursor.execute("""
        INSERT INTO links(from_page,to_page)
        VALUES (%s,%s)
        ON CONFLICT DO NOTHING;
    """, (from_page_id, to_page_id))
    conn.commit()

def save_file(page_id, file_url, file_type, file_name, file_content):
    cursor.execute("""
        INSERT INTO files(page_id,file_url,file_type,file_name,file_content)
        VALUES (%s,%s,%s,%s,%s);
    """, (page_id, file_url, file_type, file_name, file_content))
    conn.commit()

# ----------------------------
# CRAWLER
# ----------------------------
visited = set()

def crawl(start_url, max_depth=3):
    domain = urlparse(start_url).netloc
    queue = [(start_url, 1)]  # tuple (url, depth)

    while queue:
        url, depth = queue.pop(0)
        if url in visited or depth > max_depth:
            continue
        visited.add(url)

        try:
            response = requests.get(url, timeout=10)
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.text if soup.title else ""
        headers = " ".join(h.text for h in soup.find_all(["h1","h2","h3","h4","h5"]))
        meta = " ".join(str(m) for m in soup.find_all("meta"))
        content = soup.get_text(separator="\n", strip=True)

        page_id = save_page(url, title, headers, meta, content, depth)
        print(f"Saved page {url} (ID: {page_id}, depth: {depth})")

        # --- FILES ---
        for link_tag in soup.find_all("a"):
            href = link_tag.get("href")
            if not href:
                continue
            href = urljoin(url, href)

            # Skip external domains
            href_domain = urlparse(href).netloc
            if href_domain != domain:
                continue

            # Files
            if any(href.lower().endswith(ext) for ext in [".pdf", ".doc", ".docx"]):
                try:
                    r = requests.get(href, timeout=10)
                    file_name = href.split("/")[-1]
                    file_type = href.split(".")[-1].lower()
                    save_file(page_id, href, file_type, file_name, r.content)
                    print(f"📄 Saved file: {file_name}")
                except:
                    print(f"❌ Failed to download file {href}")
                continue

            # Normal page → add to queue
            if href not in visited:
                queue.append((href, depth + 1))

        # --- LINKS BETWEEN PAGES ---
        for a_tag in soup.find_all("a"):
            href = a_tag.get("href")
            if not href:
                continue
            href = urljoin(url, href)
            href_domain = urlparse(href).netloc
            if href_domain != domain:
                continue

            # save link if the target page exists
            cursor.execute("SELECT id FROM pages WHERE url=%s", (href,))
            res = cursor.fetchone()
            if res:
                to_page_id = res[0]
                save_link(page_id, to_page_id)




start_url = "https://univ-soukahras.dz/ar/"  
crawl(start_url, max_depth=3)

print("Crawling completed!")