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
    depth    = request.args.get("depth", "all")       # all | 1 | 2 | 3
    search_in = request.args.get(
        "in", "title,content,headers,meta,files"
    )
    # Same extensions as index.py (crawler) FILE_EXTENSIONS
    file_types_param = request.args.get("file_types", "").strip()
    page     = int(request.args.get("page", 1))
    per_page = 10
    offset   = (page - 1) * per_page

    if not query:
        return jsonify({"results": [], "total": 0, "query": ""})

    allowed_fields = {"title", "content", "headers", "meta", "files"}
    selected_fields = [
        f.strip() for f in search_in.split(",") if f.strip() in allowed_fields
    ]
    if not selected_fields:
        return jsonify({
            "results": [],
            "total": 0,
            "query": query,
            "page": page,
            "pages": 0,
            "search_in": [],
            "file_types": [],
        })

    file_type_list = []
    if file_types_param:
        file_type_list = [
            t.strip().lower().lstrip(".")
            for t in file_types_param.split(",")
            if t.strip()
        ]

    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    depth_filter = "" if depth == "all" else f"AND p.depth = {int(depth)}"

    if sort_by == "depth":
        order = "ORDER BY p.depth ASC, rank DESC"
    elif sort_by == "date":
        order = "ORDER BY p.indexed_at DESC"
    else:
        order = "ORDER BY rank DESC"

    page_field_expr = {
        "title": "COALESCE(p.title,'')",
        "content": "COALESCE(p.content,'')",
        "headers": "COALESCE(p.headers,'')",
        "meta": "COALESCE(p.meta_data,'')",
    }
    selected_page_exprs = [
        page_field_expr[k] for k in ("title", "content", "headers", "meta")
        if k in selected_fields
    ]
    page_text_expr = " || ' ' || ".join(selected_page_exprs) if selected_page_exprs else "''"
    page_vector_expr = f"to_tsvector('english', {page_text_expr})"

    type_clause = ""
    if file_type_list:
        type_clause = " AND f.file_type = ANY(%(ft)s)"

    file_match_expr = f"""
        EXISTS (
            SELECT 1
            FROM files f
            WHERE f.page_id = p.id
              {type_clause}
              AND to_tsvector(
                    'english',
                    COALESCE(f.file_name,'') || ' ' || COALESCE(f.file_type,'') || ' ' || COALESCE(f.file_url,'')
                  ) @@ plainto_tsquery('english', %(q)s)
        )
    """

    where_parts = []
    if selected_page_exprs:
        where_parts.append(
            f"{page_vector_expr} @@ plainto_tsquery('english', %(q)s)"
        )
    if "files" in selected_fields:
        where_parts.append(file_match_expr)

    if not where_parts:
        cur.close()
        conn.close()
        return jsonify({
            "results": [],
            "total": 0,
            "query": query,
            "page": page,
            "pages": 0,
            "search_in": selected_fields,
            "file_types": file_type_list,
        })

    where_expr = " OR ".join(where_parts)

    if "content" in selected_fields:
        snippet_source = "COALESCE(p.content,'')"
    elif "headers" in selected_fields:
        snippet_source = "COALESCE(p.headers,'')"
    elif "meta" in selected_fields:
        snippet_source = "COALESCE(p.meta_data,'')"
    elif "title" in selected_fields:
        snippet_source = "COALESCE(p.title,'')"
    else:
        snippet_source = "COALESCE(p.content,'')"

    rank_page = (
        f"ts_rank({page_vector_expr}, plainto_tsquery('english', %(q)s))"
        if selected_page_exprs
        else "0::float"
    )

    sql = f"""
        SELECT
            p.id,
            p.url,
            p.title,
            p.depth,
            p.indexed_at,
            (
                ({rank_page})
                + CASE WHEN {file_match_expr} THEN 0.15 ELSE 0 END
            ) AS rank,
            ts_headline(
                'english',
                {snippet_source},
                plainto_tsquery('english', %(q)s),
                'MaxWords=35, MinWords=20, StartSel=<mark>, StopSel=</mark>'
            ) AS snippet,
            (SELECT COUNT(*) FROM links WHERE to_page = p.id)   AS incoming_links,
            (SELECT COUNT(*) FROM links WHERE from_page = p.id) AS outgoing_links,
            (SELECT COUNT(*) FROM files  WHERE page_id  = p.id) AS file_count
        FROM pages p
        WHERE
            ({where_expr})
            {depth_filter}
        {order}
        LIMIT %(limit)s OFFSET %(offset)s
    """

    count_sql = f"""
        SELECT COUNT(*) AS count FROM pages p
        WHERE
            ({where_expr})
            {depth_filter}
    """

    params = {"q": query, "limit": per_page, "offset": offset}
    if file_type_list:
        params["ft"] = file_type_list

    cur.execute(sql, params)
    results = cur.fetchall()

    cur.execute(count_sql, {k: v for k, v in params.items() if k in ("q", "ft")})
    total = cur.fetchone()["count"]

    cur.close()
    conn.close()

    return jsonify({
        "results": [dict(r) for r in results],
        "total":   total,
        "query":   query,
        "search_in": selected_fields,
        "file_types": file_type_list,
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