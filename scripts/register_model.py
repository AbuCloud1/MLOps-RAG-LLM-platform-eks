"""
logs the tinyllama serving config as an mlflow run then registers it and
bumps it to production so the registry actually matches whats deployed

port forward mlflow first
kubectl port-forward -n rag svc/mlflow 5001:5000
then just run this file
"""
import json
import os
import tempfile

import mlflow
from mlflow.tracking import MlflowClient

MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5001")
MODEL_NAME = "tinyllama-rag-assistant"

# mirrors k8s/vllm/01-deployment.yaml keep both in sync if this changes
SERVING_CONFIG = {
    "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "image": "vllm/vllm-openai:v0.6.6",
    "max_model_len": 2048,
    "gpu_memory_utilization": 0.9,
    "dtype": "half",
    "gpu": "1x NVIDIA T4 (g4dn.xlarge)",
}


def main():
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment("rag-platform")

    with mlflow.start_run(run_name="vllm-tinyllama-serving") as run:
        mlflow.log_params(SERVING_CONFIG)

        with tempfile.TemporaryDirectory() as tmp:
            config_path = os.path.join(tmp, "serving_config.json")
            with open(config_path, "w") as f:
                json.dump(SERVING_CONFIG, f, indent=2)
            mlflow.log_artifact(config_path)

        run_id = run.info.run_id

    model_uri = f"runs:/{run_id}/serving_config.json"
    result = mlflow.register_model(model_uri, MODEL_NAME)

    client = MlflowClient()
    client.transition_model_version_stage(
        name=MODEL_NAME,
        version=result.version,
        stage="Production",
    )

    print(f"registered {MODEL_NAME} v{result.version}, stage=Production, run_id={run_id}")


if __name__ == "__main__":
    main()
