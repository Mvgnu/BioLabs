from typing import List, Optional
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import os

from .models import InventoryItem

ES_URL = os.environ.get("ELASTICSEARCH_URL")
_es_client: Optional[Elasticsearch] = None

if ES_URL:
    _es_client = Elasticsearch(ES_URL)

INDEX_NAME = "inventory_items"


def index_item(item: InventoryItem):
    if not _es_client:
        return
    doc = {
        "id": str(item.id),
        "name": item.name,
        "item_type": item.item_type,
        "custom_data": item.custom_data,
        "status": item.status,
    }
    _es_client.index(index=INDEX_NAME, id=str(item.id), document=doc)


def delete_item(item_id: str):
    if not _es_client:
        return
    _es_client.delete(index=INDEX_NAME, id=item_id, ignore=[404])


def search_items(query: str, db_session) -> List[InventoryItem]:
    if _es_client:
        res = _es_client.search(
            index=INDEX_NAME,
            query={
                "multi_match": {
                    "query": query,
                    "fields": ["name", "item_type", "custom_data", "status"],
                }
            },
        )
        ids = [hit["_id"] for hit in res["hits"]["hits"]]
        if not ids:
            return []
        return db_session.query(InventoryItem).filter(InventoryItem.id.in_(ids)).all()
    else:
        # fallback simple LIKE search
        return db_session.query(InventoryItem).filter(InventoryItem.name.ilike(f"%{query}%")).all()

