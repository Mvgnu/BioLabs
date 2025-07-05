import requests

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


def search_pubmed(query: str, limit: int = 5):
    params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": limit}
    r = requests.get(BASE_URL + "esearch.fcgi", params=params, timeout=10)
    r.raise_for_status()
    ids = r.json()["esearchresult"].get("idlist", [])
    if not ids:
        return []
    r2 = requests.get(BASE_URL + "esummary.fcgi", params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"}, timeout=10)
    r2.raise_for_status()
    data = r2.json()["result"]
    articles = []
    for _id in ids:
        info = data.get(_id)
        if not info:
            continue
        articles.append({"id": info["uid"], "title": info.get("title", "")})
    return articles
