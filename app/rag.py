"""RAG 检索 —— sentence-transformers 向量检索(带磁盘缓存)

语料来自 rag_corpus.build_corpus()(94 条)。
首次构建索引编码后 pickle 缓存到 data/rag_index/,后续秒级加载。
检索 top-k 返回最相关 chunk,供 Agent / 问答拼接 context。
"""
import os
import pickle
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_DIR = os.path.join(_PROJ_ROOT, "data", "rag_index")
INDEX_PATH = os.path.join(INDEX_DIR, "rag_index.pkl")

_MODEL = None
_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_corpus = None
_embeddings = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        import os
        # 离线模式:模型已缓存到本地,不每次联网检查更新(避免比赛现场网络慢)
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer(_MODEL_NAME)
    return _MODEL


def _normalize(mat: np.ndarray) -> np.ndarray:
    """L2 归一化,便于余弦相似度=点积"""
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return mat / norms


def build_index(force: bool = False):
    """构建或加载索引。返回 (corpus, embeddings_normalized)"""
    global _corpus, _embeddings
    if _corpus is not None and _embeddings is not None:
        return _corpus, _embeddings

    # 尝试从缓存加载
    if not force and os.path.exists(INDEX_PATH):
        try:
            with open(INDEX_PATH, "rb") as f:
                _corpus, _embeddings = pickle.load(f)
            logger.info(f"RAG 索引从缓存加载: {len(_corpus)} 条")
            return _corpus, _embeddings
        except Exception as e:
            logger.warning(f"缓存加载失败,重建: {e}")

    # 重新构建
    from app.rag_corpus import build_corpus
    _corpus = build_corpus()
    model = _get_model()
    texts = [c["text"] for c in _corpus]
    emb = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    _embeddings = _normalize(emb.astype(np.float32))

    os.makedirs(INDEX_DIR, exist_ok=True)
    with open(INDEX_PATH, "wb") as f:
        pickle.dump((_corpus, _embeddings), f)
    logger.info(f"RAG 索引构建完成并缓存: {len(_corpus)} 条 → {INDEX_PATH}")
    return _corpus, _embeddings


def retrieve(query: str, k: int = 4) -> list:
    """检索 top-k 相关 chunk。返回 list[dict],每条加 score 字段"""
    corpus, emb = build_index()
    model = _get_model()
    q = model.encode([query], show_progress_bar=False, convert_to_numpy=True)
    q = _normalize(q.astype(np.float32))
    scores = (emb @ q.T).ravel()  # 余弦相似度
    top = np.argsort(scores)[::-1][:k]
    results = []
    for i in top:
        c = dict(corpus[i])
        c["score"] = round(float(scores[i]), 4)
        results.append(c)
    return results


def retrieve_text(query: str, k: int = 4) -> str:
    """检索并拼成纯文本 context(供大模型 system prompt 注入)"""
    rs = retrieve(query, k=k)
    parts = [f"[{r['category']}] {r['title']}\n{r['text']}" for r in rs]
    return "\n\n".join(parts)


def retrieve_for_marketing(segment: str, k: int = 5) -> str:
    """营销专用检索:按群体拼查询词"""
    q = f"{segment}会员营销策略 万泰商铺 {segment}群体"
    return retrieve_text(q, k=k)


if __name__ == "__main__":
    print("--- 构建/加载索引 ---")
    import time
    t = time.time()
    corpus, _ = build_index()
    print(f"语料 {len(corpus)} 条,耗时 {time.time()-t:.1f}s")

    for q in ["沉睡会员怎么激活", "L1有哪些餐饮", "商铺评分怎么算", "高价值会员营销"]:
        print(f"\nQ: {q}")
        for r in retrieve(q, k=3):
            print(f"  [{r['score']:.3f}] [{r['category']}] {r['title']}: {r['text'][:60]}...")
