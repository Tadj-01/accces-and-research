from flask import Flask, request, jsonify, send_from_directory
import psycopg2
import psycopg2.extras
import os

app = Flask(__name__, static_folder="static")

# ----------------------------
# DATABASE CONNECTION
# ----------------------------
DB_HOST     = "localhost"
DB_NAME     = "web_crawler"
DB_USER     = "postgres"
DB_PASSWORD = "20050114"

def get_conn():
    return psycopg2.connect(
        host=DB_HOST, database=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )

# ----------------------------
# ROUTES
# ----------------------------

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/search")
def search():
    query    = request.args.get("q", "").strip()
    sort_by  = request.args.get("sort", "relevance")   # relevance | depth | date
    depth    = request.args.get("depth", "all")         # all | 1 | 2 | 3
    page     = int(request.args.get("page", 1))
    per_page = 10
    offset   = (page - 1) * per_page

    if not query:
        return jsonify({"results": [], "total": 0, "query": ""})

    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Build depth filter
    depth_filter = "" if depth == "all" else f"AND depth = {int(depth)}"

    # Build ORDER BY
    if sort_by == "depth":
        order = "ORDER BY p.depth ASC, rank DESC"
    elif sort_by == "date":
        order = "ORDER BY p.indexed_at DESC"
    else:
        order = "ORDER BY rank DESC"

    sql = f"""
        SELECT
            p.id,
            p.url,
            p.title,
            p.depth,
            p.indexed_at,
            ts_rank(
                to_tsvector('english', COALESCE(p.title,'') || ' ' || COALESCE(p.content,'')),
                plainto_tsquery('english', %(q)s)
            ) AS rank,
            ts_headline(
                'english',
                COALESCE(p.content,''),
                plainto_tsquery('english', %(q)s),
                'MaxWords=35, MinWords=20, StartSel=<mark>, StopSel=</mark>'
            ) AS snippet,
            (SELECT COUNT(*) FROM links WHERE to_page = p.id)   AS incoming_links,
            (SELECT COUNT(*) FROM links WHERE from_page = p.id) AS outgoing_links,
            (SELECT COUNT(*) FROM files  WHERE page_id  = p.id) AS file_count
        FROM pages p
        WHERE
            to_tsvector('english', COALESCE(p.title,'') || ' ' || COALESCE(p.content,''))
            @@ plainto_tsquery('english', %(q)s)
            {depth_filter}
        {order}
        LIMIT %(limit)s OFFSET %(offset)s
    """

    count_sql = f"""
        SELECT COUNT(*) FROM pages p
        WHERE
            to_tsvector('english', COALESCE(p.title,'') || ' ' || COALESCE(p.content,''))
            @@ plainto_tsquery('english', %(q)s)
            {depth_filter}
    """

    cur.execute(sql,       {"q": query, "limit": per_page, "offset": offset})
    results = cur.fetchall()

    cur.execute(count_sql, {"q": query})
    total = cur.fetchone()["count"]

    cur.close()
    conn.close()

    return jsonify({
        "results": [dict(r) for r in results],
        "total":   total,
        "query":   query,
        "page":    page,
        "pages":   (total + per_page - 1) // per_page,
    })


@app.route("/api/stats")
def stats():
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT COUNT(*) AS c FROM pages")
    pages = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM links")
    links = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM files")
    files = cur.fetchone()["c"]

    cur.execute("SELECT depth, COUNT(*) AS c FROM pages GROUP BY depth ORDER BY depth")
    by_depth = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify({
        "pages":    pages,
        "links":    links,
        "files":    files,
        "by_depth": [dict(r) for r in by_depth],
    })


if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    app.run(debug=True, port=5000)