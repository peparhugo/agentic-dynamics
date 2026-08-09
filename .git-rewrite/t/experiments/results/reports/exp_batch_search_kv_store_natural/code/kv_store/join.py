"Distributed join operations across sharded key-value stores.

Supports hash joins where left-side keys map to right-side lookups.
For a search engine, this enables joining keyword indices with
document metadata across shards.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from .store import DistributedKVStore


class JoinExecutor:
    def __init__(self, store: DistributedKVStore):
        self._store = store

    def hash_join(
        self,
        left_keys: List[str],
        right_prefix: str = "",
    ) -> List[Tuple[str, List[Any], List[Any]]]:
        left_results = self._store.multi_get(left_keys)
        doc_ids: Set[str] = set()
        key_docs: Dict[str, List[str]] = {}

        for key, values in left_results.items():
            if values:
                doc_list = [v for v in values]
                doc_ids.update(doc_list)
                key_docs[key] = doc_list

        right_keys = [f"{right_prefix}{did}" for did in doc_ids]
        right_results = self._store.multi_get(right_keys)

        doc_metadata: Dict[str, List[Any]] = {}
        for rk, values in right_results.items():
            did = rk[len(right_prefix):] if right_prefix else rk
            doc_metadata[did] = values or []

        result = []
        for key in left_keys:
            docs = key_docs.get(key, [])
            joined_docs = []
            for did in docs:
                metadata = doc_metadata.get(str(did), [])
                if metadata:
                    joined_docs.extend(metadata)
            result.append((key, docs, joined_docs))

        return result

    def nested_loop_join(
        self,
        left_keys: List[str],
        right_prefix: str = "",
    ) -> List[Tuple[str, Any]]:
        left_results = self._store.multi_get(left_keys)
        result = []
        for key, values in left_results.items():
            if not values:
                continue
            for v in values:
                right_key = f"{right_prefix}{v}"
                right_val = self._store.get(right_key)
                if right_val:
                    result.append((key, right_val))
        return result

    def index_merge_join(
        self,
        left_prefix: str,
        right_prefix: str,
    ) -> List[Tuple[str, List[Any], List[Any]]]:
        left_scan = self._store.prefix_scan(left_prefix)
        result = []
        for lkey, lvalues in left_scan:
            right_vals = []
            for v in lvalues:
                right_key = f"{right_prefix}{v}"
                rv = self._store.get(right_key)
                if rv:
                    right_vals.extend(rv)
            result.append((lkey, lvalues, right_vals))
        return result
