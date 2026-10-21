from typing import List, Dict, Any, Optional
import os
import sys
import asyncio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Silence HuggingFace progress bars and tokenizer warnings
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import numpy as np
import faiss
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

try:
    from pythainlp.tokenize import word_tokenize
    def tokenize_thai(text: str) -> List[str]:
        return [w.strip().lower() for w in word_tokenize(text or "", engine="newmm") if w.strip()]
except ImportError:
    import re
    def tokenize_thai(text: str) -> List[str]:
        return [w.lower() for w in re.findall(r"\w+", text or "") if w]

# Global shared SentenceTransformer model instance for efficiency (Singleton)
_EMBEDDING_MODEL: Optional[SentenceTransformer] = None

def get_embedding_model() -> SentenceTransformer:
    """Loads and caches the intfloat/multilingual-e5-small model (384 dimensions)."""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        _EMBEDDING_MODEL = SentenceTransformer("intfloat/multilingual-e5-small")
    return _EMBEDDING_MODEL


class MongoDBAtlasVectorSearch:
    """
    Dual-Mode Hybrid Search Engine:
    1. 'in_memory' (Default): In-Memory FAISS (IndexFlatIP) + BM25Okapi with Reciprocal Rank Fusion (RRF).
       Ultra-low latency (<20ms), ideal for high throughput and rapid interactive queries.
    2. 'atlas': Live MongoDB Atlas $vectorSearch (Cosine Similarity, 384-dim) Aggregation Pipeline.
    """
    # Shared in-memory catalog and indexes across instances
    _catalog: List[Dict[str, Any]] = []
    _faiss_index: Optional[faiss.IndexFlatIP] = None
    _bm25_index: Optional[BM25Okapi] = None
    _is_warmed_up: bool = False

    def __init__(
        self,
        mongo_uri: Optional[str] = None,
        db_name: Optional[str] = None,
        collection_name: str = "loan_products",
        index_name: str = "vector_index"
    ):
        self.mongo_uri = mongo_uri or settings.MONGO_URI
        self.db_name = db_name or settings.MONGO_DB_NAME
        self.collection_name = collection_name
        self.index_name = index_name
        self.client: Optional[AsyncIOMotorClient] = None

    def _get_collection(self):
        if self.client is None:
            self.client = AsyncIOMotorClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
        return self.client[self.db_name][self.collection_name]

    def encode_query(self, query_text: str) -> List[float]:
        """Encodes query using E5 standard prefix 'query: ' and normalized embeddings."""
        model = get_embedding_model()
        formatted_query = f"query: {query_text.strip()}"
        return model.encode(formatted_query, normalize_embeddings=True).tolist()

    async def warm_up_catalog(self) -> int:
        """
        Pre-computes and caches the entire loan products catalog in RAM:
        - Pre-warms the embedding model (intfloat/multilingual-e5-small) with dummy encode.
        - Fetches all documents from MongoDB Atlas 'loan_products'.
        - Constructs an in-memory FAISS IndexFlatIP (Inner Product = Cosine Similarity for normalized vectors).
        - Constructs an in-memory BM25Okapi sparse lexical search index.
        """
        # Pre-warm embedding model to prevent Cold-Start on first search
        try:
            model = get_embedding_model()
            _ = model.encode("query: warm up", normalize_embeddings=True)
        except Exception as e:
            print(f"Warning: Failed to pre-warm embedding model in warm_up_catalog: {e}")

        collection = self._get_collection()
        cursor = collection.find({}, {"_id": 0})
        raw_docs = await cursor.to_list(length=None)

        if not raw_docs:
            print("⚠️ [Warm-up Warning] No documents found in 'loan_products' collection on Atlas.")
            return 0

        valid_catalog = []
        embeddings_list = []
        tokenized_corpus = []

        for doc in raw_docs:
            emb = doc.get("embedding")
            if emb and len(emb) == 384:
                embeddings_list.append(emb)
                # Store clean document without duplicating embedding in catalog dictionary
                clean_doc = {k: v for k, v in doc.items() if k != "embedding"}
                valid_catalog.append(clean_doc)

                # Tokenize for BM25 (including Contextual Summary for RAG)
                corpus_text = f"{clean_doc.get('product_name', '')} {clean_doc.get('bank', '')} {clean_doc.get('type', '')} {clean_doc.get('content', '')} {clean_doc.get('contextual_summary', '')}"
                tokenized_corpus.append(tokenize_thai(corpus_text))

        if not embeddings_list:
            print("⚠️ [Warm-up Warning] No valid 384-dimensional embeddings found.")
            return 0

        # 1. Build FAISS IndexFlatIP
        np_embeddings = np.array(embeddings_list, dtype=np.float32)
        faiss_idx = faiss.IndexFlatIP(384)
        faiss_idx.add(np_embeddings)

        # 2. Build BM25 Index
        bm25_idx = BM25Okapi(tokenized_corpus)

        # Update class-level shared state
        MongoDBAtlasVectorSearch._catalog = valid_catalog
        MongoDBAtlasVectorSearch._faiss_index = faiss_idx
        MongoDBAtlasVectorSearch._bm25_index = bm25_idx
        MongoDBAtlasVectorSearch._is_warmed_up = True

        print(f"✅ [Catalog Warmed Up] Loaded {len(valid_catalog)} products into FAISS (IndexFlatIP) and BM25Okapi (In-Memory RRF)")
        return len(valid_catalog)

    @classmethod
    def is_warmed_up(cls) -> bool:
        return cls._is_warmed_up and cls._faiss_index is not None and cls._bm25_index is not None

    async def _search_atlas(
        self,
        query: str,
        limit: int = 5,
        num_candidates: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Executes live MongoDB Atlas $vectorSearch aggregation stage.
        """
        query_vector = self.encode_query(query)
        collection = self._get_collection()

        pipeline = [
            {
                "$vectorSearch": {
                    "index": self.index_name,
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": num_candidates,
                    "limit": limit
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "id": 1,
                    "bank": 1,
                    "product_name": 1,
                    "content": 1,
                    "type": 1,
                    "interest_rate": 1,
                    "max_limit": 1,
                    "extra_rules": 1,
                    "required_documents": 1,
                    "contextual_summary": 1,
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ]

        try:
            cursor = collection.aggregate(pipeline)
            results = await cursor.to_list(length=limit)
            return results
        except Exception as e:
            print(f"Error executing Atlas $vectorSearch ({type(e).__name__}): {e}")
            cursor = collection.find({}, {"_id": 0, "embedding": 0}).limit(limit)
            return await cursor.to_list(length=limit)

    async def vector_search(self, query: str, limit: int = 5, num_candidates: int = 20) -> List[Dict[str, Any]]:
        """Direct vector search endpoint (delegates to _search_atlas)."""
        return await self._search_atlas(query=query, limit=limit, num_candidates=num_candidates)

    async def hybrid_search(
        self,
        query: str,
        limit: int = 5,
        filter_criteria: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Dual-Mode Hybrid Search:
        - If settings.RETRIEVAL_MODE == 'in_memory':
            Computes Dense Rank (FAISS) + Sparse Rank (BM25) and combines with RRF:
            RRF_Score = 1 / (60 + dense_rank) + 1 / (60 + sparse_rank)
            (Gracefully falls back to Atlas if not yet warmed up).
        - If settings.RETRIEVAL_MODE == 'atlas':
            Directly executes Atlas $vectorSearch aggregation.
        """
        retrieval_mode = getattr(settings, "RETRIEVAL_MODE", "in_memory").lower()

        if retrieval_mode == "in_memory":
            if not self.is_warmed_up():
                print("⚠️ [Retrieval Fallback] In-Memory Catalog not yet warmed up. Falling back to MongoDB Atlas $vectorSearch...", flush=True)
                return await self._search_atlas(query=query, limit=limit)

            # 1. FAISS Dense Search
            query_vector = np.array([self.encode_query(query)], dtype=np.float32)
            catalog_size = len(self._catalog)
            top_k = min(catalog_size, max(limit * 4, 20))
            _, faiss_indices = self._faiss_index.search(query_vector, k=top_k)

            # 2. BM25 Sparse Search
            query_tokens = tokenize_thai(query)
            bm25_scores = self._bm25_index.get_scores(query_tokens)
            bm25_sorted_indices = np.argsort(-bm25_scores)[:top_k]

            # 3. Reciprocal Rank Fusion (RRF) with 1-based ranks
            # Formula: RRF_Score = 1 / (60 + dense_rank) + 1 / (60 + sparse_rank)
            rrf_scores: Dict[int, float] = {}

            for rank_1b, idx in enumerate(faiss_indices[0], start=1):
                idx = int(idx)
                if 0 <= idx < catalog_size:
                    rrf_scores[idx] = rrf_scores.get(idx, 0.0) + (1.0 / (60.0 + rank_1b))

            for rank_1b, idx in enumerate(bm25_sorted_indices, start=1):
                idx = int(idx)
                if 0 <= idx < catalog_size:
                    rrf_scores[idx] = rrf_scores.get(idx, 0.0) + (1.0 / (60.0 + rank_1b))

            # Sort descending by RRF score
            sorted_indices = sorted(rrf_scores.keys(), key=lambda i: rrf_scores[i], reverse=True)

            results = []
            for idx in sorted_indices[:limit]:
                doc_copy = dict(self._catalog[idx])
                doc_copy["score"] = round(rrf_scores[idx], 6)
                results.append(doc_copy)

            return results

        # Fallback / explicit Atlas mode
        return await self._search_atlas(query=query, limit=limit)


# Backward compatibility alias
LoanVectorStore = MongoDBAtlasVectorSearch
