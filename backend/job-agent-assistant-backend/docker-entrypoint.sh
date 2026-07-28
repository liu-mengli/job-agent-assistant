#!/bin/bash
set -e

MODEL_DIR="${HF_HOME:-/app/models/huggingface}"

check_and_download() {
    local model_id=$1
    local safe_name=$(echo "$model_id" | tr '/' '_')
    if [ ! -d "$MODEL_DIR/models--$safe_name/snapshots" ] || \
       [ -z "$(ls -A "$MODEL_DIR/models--$safe_name/snapshots" 2>/dev/null)" ]; then
        echo "Model $model_id not found, downloading..."
        python -c "from huggingface_hub import snapshot_download; snapshot_download('$model_id')"
    else
        echo "Model $model_id already cached."
    fi
}

if [ "${HF_HUB_OFFLINE:-0}" != "1" ]; then
    check_and_download "BAAI/bge-small-zh-v1.5"
    check_and_download "BAAI/bge-m3"
    check_and_download "BAAI/bge-reranker-v2-m3"
fi

echo "Starting FastAPI..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
