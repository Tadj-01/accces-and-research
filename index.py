# import requests
# from bs4 import BeautifulSoup
# from urllib.parse import urlparse, urljoin
# import psycopg2

# # ----------------------------
# # DATABASE CONNECTION
# # ----------------------------
# DB_HOST = "localhost"
# DB_NAME = "web_crawler"
# DB_USER = "postgres"
# DB_PASSWORD = "20050114"  

# conn = psycopg2.connect(
#     host=DB_HOST,
#     database=DB_NAME,
#     user=DB_USER,
#     password=DB_PASSWORD
# )
# cursor = conn.cursor()
# print("Connected to PostgreSQL!")

# # ----------------------------
# # DATABASE FUNCTIONS
# # ----------------------------
# def save_page(url, title, headers, meta, content, depth):
#     cursor.execute("""
#         INSERT INTO pages(url,title,headers,meta_data,content,depth)
#         VALUES (%s,%s,%s,%s,%s,%s)
#         ON CONFLICT (url) DO NOTHING
#         RETURNING id;
#     """, (url, title, headers, meta, content, depth))
#     result = cursor.fetchone()
#     conn.commit()
#     return result[0] if result else None

# def save_link(from_page_id, to_page_id):
#     cursor.execute("""
#         INSERT INTO links(from_page,to_page)
#         VALUES (%s,%s)
#         ON CONFLICT DO NOTHING;
#     """, (from_page_id, to_page_id))
#     conn.commit()

# def save_file(page_id, file_url, file_type, file_name, file_content):
#     cursor.execute("""
#         INSERT INTO files(page_id,file_url,file_type,file_name,file_content)
#         VALUES (%s,%s,%s,%s,%s);
#     """, (page_id, file_url, file_type, file_name, file_content))
#     conn.commit()

# # ----------------------------
# # CRAWLER
# # ----------------------------
# visited = set()

# def crawl(start_url, max_depth=3):
#     domain = urlparse(start_url).netloc
#     queue = [(start_url, 1)]  # tuple (url, depth)

#     while queue:
#         url, depth = queue.pop(0)
#         if url in visited or depth > max_depth:
#             continue
#         visited.add(url)

#         try:
#             response = requests.get(url, timeout=10)
#         except Exception as e:
#             print(f"Failed to fetch {url}: {e}")
#             continue

#         soup = BeautifulSoup(response.text, "html.parser")
#         title = soup.title.text if soup.title else ""
#         headers = " ".join(h.text for h in soup.find_all(["h1","h2","h3","h4","h5"]))
#         meta = " ".join(str(m) for m in soup.find_all("meta"))
#         content = soup.get_text(separator="\n", strip=True)

#         page_id = save_page(url, title, headers, meta, content, depth)
#         print(f"Saved page {url} (ID: {page_id}, depth: {depth})")

#         # --- FILES ---
#         for link_tag in soup.find_all("a"):
#             href = link_tag.get("href")
#             if not href:
#                 continue
#             href = urljoin(url, href)

#             # Skip external domains
#             href_domain = urlparse(href).netloc
#             if href_domain != domain:
#                 continue

#             # Files
#             if any(href.lower().endswith(ext) for ext in [".pdf", ".doc", ".docx"]):
#                 try:
#                     r = requests.get(href, timeout=10)
#                     file_name = href.split("/")[-1]
#                     file_type = href.split(".")[-1].lower()
#                     save_file(page_id, href, file_type, file_name, r.content)
#                     print(f"📄 Saved file: {file_name}")
#                 except:
#                     print(f"❌ Failed to download file {href}")
#                 continue

#             # Normal page → add to queue
#             if href not in visited:
#                 queue.append((href, depth + 1))

#         # --- LINKS BETWEEN PAGES ---
#         for a_tag in soup.find_all("a"):
#             href = a_tag.get("href")
#             if not href:
#                 continue
#             href = urljoin(url, href)
#             href_domain = urlparse(href).netloc
#             if href_domain != domain:
#                 continue

#             # save link if the target page exists
#             cursor.execute("SELECT id FROM pages WHERE url=%s", (href,))
#             res = cursor.fetchone()
#             if res:
#                 to_page_id = res[0]
#                 save_link(page_id, to_page_id)




# start_url = "https://univ-soukahras.dz/ar/"  
# crawl(start_url, max_depth=3)

# print("Crawling completed!")


import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urldefrag
import psycopg2


DB_HOST     = "localhost"
DB_NAME     = "web_crawler"
DB_USER     = "postgres"
DB_PASSWORD = "20050114"

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cursor = conn.cursor()
print("Connected to PostgreSQL!")



def save_page(url, title, headers, meta, content, depth):
    """Insert a page and return its ID. If URL already exists, return existing ID."""
    cursor.execute("""
        INSERT INTO pages (url, title, headers, meta_data, content, depth)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (url) DO NOTHING
        RETURNING id;
    """, (url, title, headers, meta, content, depth))
    result = cursor.fetchone()
    conn.commit()

    if result:
        return result[0]
    else:
        # URL already existed — fetch its ID
        cursor.execute("SELECT id FROM pages WHERE url = %s", (url,))
        row = cursor.fetchone()
        return row[0] if row else None


def save_link(from_page_id, to_page_id):
    """Record a directed link edge between two pages."""
    if from_page_id and to_page_id and from_page_id != to_page_id:
        cursor.execute("""
            INSERT INTO links (from_page, to_page)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (from_page_id, to_page_id))
        conn.commit()


def save_file(page_id, file_url, file_type, file_name, file_content):
    """Store a downloaded file as binary in the database."""
    cursor.execute("""
        INSERT INTO files (page_id, file_url, file_type, file_name, file_content)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (file_url) DO NOTHING;
    """, (page_id, file_url, file_type, file_name, psycopg2.Binary(file_content)))
    conn.commit()


def get_page_id(url):
    """Return the DB id of a page if it was already saved, else None."""
    cursor.execute("SELECT id FROM pages WHERE url = %s", (url,))
    row = cursor.fetchone()
    return row[0] if row else None




# File extensions to download and store
FILE_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; UniCrawler/1.0)"
}

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB limit per file


def is_same_domain(url, domain):
    return urlparse(url).netloc == domain


def get_file_extension(url):
    path = urlparse(url).path.lower()
    for ext in FILE_EXTENSIONS:
        if path.endswith(ext):
            return ext.lstrip(".")
    return None


def normalize_url(url):
    """Remove URL fragment (#section) to avoid crawling the same page twice."""
    url, _ = urldefrag(url)
    return url.rstrip("/")


def extract_title(soup):
    return soup.title.get_text(strip=True) if soup.title else ""


def extract_headers(soup):
    parts = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
        text = tag.get_text(strip=True)
        if text:
            parts.append(f"[{tag.name.upper()}] {text}")
    return "\n".join(parts)


def extract_meta(soup):
    parts = []
    for m in soup.find_all("meta"):
        name    = m.get("name", m.get("property", ""))
        content = m.get("content", "")
        if name and content:
            parts.append(f"{name}: {content}")
    return "\n".join(parts)


def extract_content(soup):
    """Visible text only — strip scripts, styles, nav, footer."""
    for tag in soup(["script", "style", "noscript", "nav", "footer", "aside"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())


def download_file(url):
    """Download a file, respecting the size limit. Returns bytes or None."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        r.raise_for_status()
        chunks, total = [], 0
        for chunk in r.iter_content(8192):
            total += len(chunk)
            if total > MAX_FILE_SIZE:
                print(f"    File too large, skipped: {url}")
                return None
            chunks.append(chunk)
        return b"".join(chunks)
    except Exception as e:
        print(f"  Failed to download file {url}: {e}")
        return None



visited = set()  # tracks URLs already added to the queue


def crawl(start_url, max_depth=3):
    domain = urlparse(start_url).netloc
    queue  = [(normalize_url(start_url), 1)]  # (url, depth)
    visited.add(normalize_url(start_url))

    while queue:
        url, depth = queue.pop(0)

        if depth > max_depth:
            continue

        print(f"\n🌐 [{depth}/{max_depth}] Crawling: {url}")

        # ── Fetch the page ──────────────────────────────────────────────────
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"   Failed to fetch: {e}")
            continue

        # ── Parse HTML ──────────────────────────────────────────────────────
        soup    = BeautifulSoup(response.content, "html.parser")
        title   = extract_title(soup)
        headers = extract_headers(soup)
        meta    = extract_meta(soup)
        content = extract_content(soup)

        # ── Save page to DB ─────────────────────────────────────────────────
        page_id = save_page(url, title, headers, meta, content, depth)
        if page_id:
            print(f"  💾 Saved page (id={page_id}): {title or '(no title)'}")
        else:
            print(f"  ⚠️  Could not save page, skipping links.")
            continue

        # ── Process all <a href> links ──────────────────────────────────────
        seen_on_page = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "").strip()
            if not href or href.startswith("mailto:") or href.startswith("tel:"):
                continue

            href = normalize_url(urljoin(url, href))

            if href in seen_on_page:
                continue
            seen_on_page.add(href)

            # Stay on the same domain
            if not is_same_domain(href, domain):
                continue

            ext = get_file_extension(href)

            # ── It's a file (pdf / doc / image) ────────────────────────────
            if ext:
                print(f"  📥 Downloading {ext.upper()}: {href.split('/')[-1]}")
                data = download_file(href)
                if data:
                    file_name = href.split("/")[-1] or "file"
                    save_file(page_id, href, ext, file_name, data)
                    print(f"  ✅ Stored {file_name} ({len(data):,} bytes)")
                continue

            # ── It's a normal page ──────────────────────────────────────────

            # Record the link edge if the target page is already in the DB
            to_id = get_page_id(href)
            if to_id:
                save_link(page_id, to_id)

            # Add to queue if not visited yet and within depth
            if href not in visited and depth < max_depth:
                visited.add(href)
                queue.append((href, depth + 1))

        # Polite crawling — don't hammer the server
        time.sleep(0.5)

    print("\n Crawling completed!")
    print(f"   Pages visited : {len(visited)}")

    # ── Summary stats ───────────────────────────────────────────────────────
    cursor.execute("SELECT COUNT(*) FROM pages")
    print(f"   Pages in DB   : {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM links")
    print(f"   Links in DB   : {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*), file_type FROM files GROUP BY file_type")
    rows = cursor.fetchall()
    for count, ftype in rows:
        print(f"   {ftype.upper():8s} files : {count}")



start_url = "https://univ-soukahras.dz/ar/"
crawl(start_url, max_depth=3)

cursor.close()
conn.close()