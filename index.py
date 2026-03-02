import requests
from bs4 import BeautifulSoup

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="crawler_db",
    user="postgres",
    password="your_password"
)

cursor = conn.cursor()
def save_page(url, title, headers, meta, images, depth):
    cursor.execute("""
        INSERT INTO pages(url, title, headers, meta_data, images, depth)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (url) DO NOTHING
        RETURNING id;
    """, (url, title, headers, meta, images, depth))

    result = cursor.fetchone()
    conn.commit()

    return result[0] if result else None

url = "https://univ-soukahras.dz/ar/"

visited = set()

def crawl(url, depth):

    if depth > 3 or url in visited:
        return

    visited.add(url)

    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    title = soup.title.text if soup.title else ""

    headers = " ".join(h.text for h in soup.find_all(["h1","h2","h3"]))
    images = " ".join(img.get("src","") for img in soup.find_all("img"))
    meta = " ".join(str(m) for m in soup.find_all("meta"))

    page_id = save_page(url, title, headers, meta, images, depth)

    for link in soup.find_all("a"):
        href = link.get("href")

        if href and href.startswith("http"):
            cursor.execute(
                "INSERT INTO links(from_page,to_page) VALUES(%s,%s)",
                (page_id, href)
            )
            conn.commit()

            crawl(href, depth + 1)
        
crawl("https://univ-soukahras.dz/ar/", 1)

# response = requests.get(url)

# soup = BeautifulSoup(response.text , 'html.parser')
# #code = response.text
# print(soup.title.text) 
# with open("link.html" ,"w" , encoding="utf-8") as f :
#     for link in soup.findAll('a') :
#         f.write(str(link))
#     f.close()
    
# with open("img.html" ,"w" , encoding="utf-8") as f :
#     for img in soup.findAll('img') :
#         f.write(str(img))
#     f.close()
    
# with open("head.html" ,"w" , encoding="utf-8") as f :
#     for head in soup.findAll('h1') :
#         f.write(str(head))
#     for head in soup.findAll('h2') :
#         f.write(str(head))
#     for head in soup.findAll('h3') :
#         f.write(str(head))
#     for head in soup.findAll('h4') :
#         f.write(str(head))
#     for head in soup.findAll('h5') :
#         f.write(str(head))
#     f.close()

# with open("meta.html" ,"w" , encoding="utf-8") as f :
#     for meta in soup.findAll('meta') :
#         f.write(str(meta))
#     f.close()
    


# # with open("page.html" ,"w" , encoding="utf-8") as f :
# #     f.write(str(soup))
# #     f.close()