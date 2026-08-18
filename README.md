# MLOps - Self-Hosted RAG Assistant on EKS

## What is this?

This is a private "ask questions about me?" chatbot that runs entirely on my own infrastructure. 
<img width="1280" height="831" alt="ScreenRecording2026-08-07at14 32 48-ezgif com-video-to-gif-converter" src="https://github.com/user-attachments/assets/b13c363f-d5ae-4769-b5b8-7ca34a3d15f2" />

## How it works

- A user asks a question 
- The retrieval app turns it into an embedding (a list of numbers that captures its meaning).
- It asks Qdrant for the vector database to find the closest-matching note chunks. 
- Those chunks get added to the prompt as context
- vLLM sends the prompt through the language model on the GPU
- The answer comes back grounded in my actual notes instead of made up.

```
question -> embed -> Qdrant finds relevant notes -> build prompt with context -> vLLM (GPU) -> answer
```

I built this to go deep on the MLOps stack end to end: provisioning, GPU serving, retrieval, a model registry, evaluation, monitoring, and CI.
<img width="682" height="646" alt="image" src="https://github.com/user-attachments/assets/50eb69f3-cfb3-405b-9e1c-573cba058a59" />


## Tech Stack

| Layer | Tool |
|---|---|
| Infrastructure as code | Terraform (VPC, EKS, IAM) |
| Kubernetes | AWS EKS 1.31 |
| Node autoscaling | Karpenter |
| Vector database | Qdrant |
| LLM serving | vLLM, serving TinyLlama 1.1B |
| Embeddings | sentence-transformers, all-MiniLM-L6-v2 |
| Retrieval API and UI | FastAPI, a small chat page |
| Model registry and tracking | MLflow |
| Monitoring | Prometheus, Grafana, NVIDIA DCGM exporter |
| GPU | 1x NVIDIA T4 (g4dn.xlarge) |
| CI | GitHub Actions |

## Quick Start

Prerequisites: an AWS account, Terraform, kubectl, Helm, Python.

```
# Build the cluster
cd terraform/envs/dev
terraform init && terraform apply

# Point kubectl at it
aws eks update-kubeconfig --name abubker-eks-lab --region eu-west-2

# Storage class, GPU plugin, then the workloads
kubectl apply -f k8s/qdrant/04-storageclass.yaml
kubectl apply -f k8s/gpu/nvidia-device-plugin.yaml
kubectl apply -f k8s/qdrant/ -f k8s/vllm/ -f k8s/mlflow/

# Monitoring
bash k8s/monitoring/install.sh

# Ingest the notes and run the app locally
cd retrieval-app
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python ingest.py
uvicorn app:app --port 8000
```


## In Action 

**Serving.** the vLLM runs TinyLlama on a single T4 GPU node which is tainted so nothing else lands on it, only the model. Everything else runs on cheaper CPU nodes.

**Retrieval.** Qdrant holds the embedded notes. Retrieval is pretty good: across every test question, the right note comes back in the top results, with a similarity score per chunk. Here it is finding the car notes for "what cars does he like", with all the cluster pods running above it.

<img width="1292" height="456" alt="image" src="https://github.com/user-attachments/assets/f9a6881f-a574-4d90-97c1-24432ab5f093" />


**Model registry.** MLflow tracks the model that's actually being served. Its config is logged as a run and registered as `tinyllama-rag-assistant`, version 1, promoted to Production. So what's in the registry matches what's deployed.

<img width="1909" height="694" alt="image" src="https://github.com/user-attachments/assets/76eb80ef-1d47-4c17-bc14-bf5f2d8896fc" />


**Serving metrics.** I benchmarked vLLM with real prompts and logged latency and throughput to MLflow. Latency ran from around 0.1s to 2.2s and throughput from roughly 9 to 92 tokens per second, depending on how much text each prompt and response involved.

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/1519690a-ad6d-4461-a7cc-cd4a8efeaeeb" />


**Evaluation.** A set of 8 questions with reference answers. For each one it checks whether retrieval found the right document (recall@3) and how close the generated answer is to the reference (cosine similarity). Retrieval scored a perfect 1.00. Answer similarity sat around 0.56, which is honest for a 1.1B model that paraphrases rather than quotes.

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/6aaf7d2f-54d2-4c21-ab4e-b87f595acf8f" />

**Monitoring.** Prometheus and Grafana with NVIDIA's DCGM exporter for GPU metrics. Under a sustained load test the T4 held up to 99 percent utilisation, with the framebuffer memory, power draw, and temperature all visible live.

<img width="1918" height="956" alt="image" src="https://github.com/user-attachments/assets/bdf7d236-6ec1-4105-b336-27ae1f04df79" />


## Problems I actually hit

I came across a lot of obstacles when building.

**vLLM kept getting killed on the first build.** The pod would start then die. Turned out the GPU node's default 20GB disk wasn't enough for the vLLM image plus the model weights, so the node hit disk pressure and evicted the pod. The fix was a 100GB disk, but the EKS module ignores the normal `disk_size` setting once it uses a launch template, so it had to go through `block_device_mappings` instead. It took a while to find.

**Pods stuck Pending with no storage.** A fresh EKS cluster has no default StorageClass, and the EBS CSI driver needs its own IAM role (through IRSA) before it can create disks. Until both were in place, nothing with a volume would start.

**vLLM crash looping on an env var.** It failed parsing `VLLM_PORT` as a number, because Kubernetes auto-injects a service-discovery variable with the same name as the Service, and my Service was called `vllm`. Fixed with `enableServiceLinks: false`.

**The T4 doesn't support bfloat16.** vLLM defaults to it, the T4 is too old (compute capability 7.5), so the model wouldn't load. One flag, `--dtype half`, sorted it.

**Trying to use the model as its own evaluation judge failed, and that's a finding.** I first tried RAGAS, the standard RAG evaluation framework, using TinyLlama itself as the judge since everything is self-hosted. It didn't work, for two real reasons: the judge prompts overflowed the 2048 token context window, and a 1.1B model can't reliably produce the structured output RAGAS needs. So I swapped to a deterministic evaluation with no LLM judge. Knowing why the first approach failed is worth more than pretending it worked.


## Known limitations with this project

TinyLlama 1.1B was chosen to fit on one cheap GPU. On notes that are thin on detail it fills the gaps in which is not good Here it decides I work at a startup in Silicon Valley, which I don't. The retrieval underneath is correct, the model just embellishes on top of it. A bigger model would fix most of this at higher GPU cost.

<img width="1508" height="981" alt="Screenshot 2026-08-07 at 13 02 49" src="https://github.com/user-attachments/assets/a7775b92-3f46-45a8-888f-5f6d65145f79" />

There's one GPU node and no scale-to-zero yet, and the retrieval app runs locally against port-forwarded services rather than in-cluster. All of that is on the future list.

## What I'd add next

Right now everything is deployed with Terraform and kubectl/Helm applied by hand. That's fine for a solo project, but the next step is GitOps with ArgoCD: Git becomes the single source of truth, ArgoCD watches the repo and syncs the cluster to match, drift gets flagged or healed automatically, and a rollback is just a git revert.
<img width="1280" height="831" alt="ScreenRecording2026-08-07at14 32 48-ezgif com-video-to-gif-converter" src="https://github.com/user-attachments/assets/0bed6154-51c9-48f9-81ad-048380b14b97" />

Beyond that: in-cluster deployment of the retrieval app behind an ingress rather than a local port-forward, GPU autoscaling with Karpenter scaling down to zero when idle, serving metrics like tokens per second surfaced next to the GPU metrics in Grafana, and a larger model to lift answer quality.
