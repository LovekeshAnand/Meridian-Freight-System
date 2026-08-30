"""Epsilon Sparse Attention KV Cache Engine.

Ported from Nyaya AI core/engine/inference/kv_cache.py.
Ring-buffer KV cache using INT8 quantization and top-k sparse attention
for memory-efficient context caching during long-running multi-turn queries.
"""

import numpy as np
import math
from typing import Tuple, Dict, Any

class SparseKVCache:
    """
    Ring-buffer KV cache using INT8 quantization.
    Stores key and value tensors for all layers in a compact INT8 format.
    """
    def __init__(self, n_layers: int = 32, n_heads: int = 32, max_tokens: int = 512, d_head: int = 64):
        self.n_layers = n_layers
        self.n_heads = n_heads
        self.max_tokens = max_tokens
        self.d_head = d_head
        self.pos = 0
        self.n_tokens = 0

        self.k = np.zeros((n_layers, n_heads, max_tokens, d_head), dtype=np.int8)
        self.v = np.zeros((n_layers, n_heads, max_tokens, d_head), dtype=np.int8)

    def write(self, layer: int, keys: np.ndarray, values: np.ndarray) -> None:
        self.k[layer, :, self.pos] = np.clip(keys, -127, 127).astype(np.int8)
        self.v[layer, :, self.pos] = np.clip(values, -127, 127).astype(np.int8)

    def advance(self) -> None:
        self.n_tokens = min(self.n_tokens + 1, self.max_tokens)
        self.pos = (self.pos + 1) % self.max_tokens

    def read(self, layer: int) -> Tuple[np.ndarray, np.ndarray]:
        valid = self.n_tokens
        keys = self.k[layer, :, :valid].astype(np.float32)
        values = self.v[layer, :, :valid].astype(np.float32)
        return keys, values

    def reset(self) -> None:
        self.pos = 0
        self.n_tokens = 0

    def memory_used_mb(self) -> float:
        bytes_per_token = self.n_layers * self.n_heads * self.d_head * 2
        return (self.n_tokens * bytes_per_token) / (1024 ** 2)

    def utilisation(self) -> float:
        return self.n_tokens / self.max_tokens if self.max_tokens > 0 else 0.0


class SparseAttentionKVCache(SparseKVCache):
    """
    Extends SparseKVCache with top-k sparse attention.
    Attends only to the top_k most relevant tokens scored by dot-product similarity.
    """
    def __init__(self, top_k: int = 64, **kwargs):
        super().__init__(**kwargs)
        self.top_k = top_k

    def sparse_read(self, layer: int, query: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        all_keys, all_values = self.read(layer)
        valid = self.n_tokens

        if valid <= self.top_k or valid == 0:
            return all_keys, all_values

        scores = np.einsum("hd,hnd->hn", query, all_keys) / math.sqrt(self.d_head)
        avg_scores = scores.mean(axis=0)

        top_idx = np.argpartition(avg_scores, -self.top_k)[-self.top_k:]
        top_idx = top_idx[np.argsort(avg_scores[top_idx])[::-1]]

        return all_keys[:, top_idx, :], all_values[:, top_idx, :]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "tokens_cached": self.n_tokens,
            "max_tokens": self.max_tokens,
            "utilisation_pct": round(self.utilisation() * 100, 1),
            "memory_used_mb": round(self.memory_used_mb(), 2),
            "sparse_top_k": self.top_k,
            "attention_savings": f"{self.max_tokens // self.top_k}x" if self.top_k > 0 else "1x"
        }
