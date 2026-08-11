"""
fires prompts at vllm and logs latency and tokens per sec to mlflow
port forward mlflow and vllm first then run this
"""
import os
import time

import mlflow
import requests

MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5001")
VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8001")
MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

# mix of sizes so runs spread out on the chart
PROMPTS = [
    ("Explain kubernetes in one sentence.", 50),
    ("What is a vector database and why would you use one for search.", 100),
    ("Describe how gpu scheduling works in kubernetes with taints and tolerations.", 150),
    ("Walk through the steps of a rag pipeline from question to answer.", 200),
    ("Explain the tradeoffs between sqlite and postgres for a small mlflow backend.", 150),
    ("What does the nvidia device plugin do in a kubernetes cluster.", 100),
    ("Explain what a model registry is and why mlflow is useful for it.", 150),
    ("Describe what happens when a pod requests nvidia.com/gpu as a resource.", 120),
]


def run_one(prompt, max_tokens):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    start = time.time()
    resp = requests.post(f"{VLLM_URL}/v1/completions", json=payload, timeout=60)
    latency = time.time() - start
    resp.raise_for_status()
    data = resp.json()
    usage = data["usage"]
    tokens_per_sec = usage["completion_tokens"] / latency if latency > 0 else 0

    mlflow.log_param("max_tokens_requested", max_tokens)
    mlflow.log_param("prompt_tokens", usage["prompt_tokens"])
    mlflow.log_metric("latency_seconds", latency)
    mlflow.log_metric("completion_tokens", usage["completion_tokens"])
    mlflow.log_metric("tokens_per_sec", tokens_per_sec)

    return latency, tokens_per_sec


def main():
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment("vllm-serving-benchmarks")

    for i, (prompt, max_tokens) in enumerate(PROMPTS, start=1):
        with mlflow.start_run(run_name=f"benchmark-{i}"):
            latency, tps = run_one(prompt, max_tokens)
            print(f"run {i}: latency={latency:.2f}s tokens_per_sec={tps:.1f}")


if __name__ == "__main__":
    main()
