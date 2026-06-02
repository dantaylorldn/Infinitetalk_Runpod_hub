#!/bin/bash
set -e

echo "Starting ComfyUI in the background..."
python /ComfyUI/main.py --listen 127.0.0.1 --port 8188 --use-sage-attention &

echo "Waiting for ComfyUI to be ready..."
max_wait="${COMFYUI_START_TIMEOUT:-300}"
wait_count=0
while [ "$wait_count" -lt "$max_wait" ]; do
    if curl -s http://127.0.0.1:8188/ > /dev/null 2>&1; then
        echo "ComfyUI is ready."
        break
    fi
    echo "Waiting for ComfyUI... ($wait_count/$max_wait)"
    sleep 2
    wait_count=$((wait_count + 2))
done

if [ "$wait_count" -ge "$max_wait" ]; then
    echo "Error: ComfyUI failed to start within $max_wait seconds"
    exit 1
fi

echo "Starting InfiniteTalk Salad API..."
exec python -m uvicorn salad_server:app --host :: --port "${PORT:-8000}"
