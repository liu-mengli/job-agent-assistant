#!/usr/bin/env python3
"""下载所有 HF 模型到指定目录（用于 Docker 部署前初始化 models volume）

用法:
    # 下载到默认目录 ./models/huggingface
    python scripts/download_models.py

    # 下载到指定目录
    python scripts/download_models.py /path/to/models

    # 使用 HF 镜像
    HF_ENDPOINT=https://hf-mirror.com python scripts/download_models.py
"""

import os
import sys

MODELS = [
    "BAAI/bge-small-zh-v1.5",
    "BAAI/bge-m3",
    "BAAI/bge-reranker-v2-m3",
]


def download(target_dir: str, endpoint: str | None = None):
    os.environ["HF_HOME"] = target_dir
    from huggingface_hub import snapshot_download

    kwargs = {}
    if endpoint:
        kwargs["endpoint"] = endpoint

    for model_id in MODELS:
        print(f"Downloading {model_id}...")
        path = snapshot_download(model_id, **kwargs)
        print(f"  -> {path}")

    print("All models downloaded successfully.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "./models/huggingface"
    endpoint = os.environ.get("HF_ENDPOINT")
    download(target, endpoint)
