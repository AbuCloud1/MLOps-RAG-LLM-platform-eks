#!/usr/bin/env bash
set -euo pipefail

# installs grafana/prometheus plus the gpu metrics exporter
# run from anywhere: bash k8s/monitoring/install.sh
cd "$(dirname "$0")"

kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add nvidia https://nvidia.github.io/dcgm-exporter/helm-charts
helm repo update

helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring -f kube-prometheus-stack-values.yaml

helm upgrade --install dcgm-exporter nvidia/dcgm-exporter \
  -n monitoring -f dcgm-exporter-values.yaml

# grafana sidecar picks this up automatically no manual import needed
kubectl apply -f dcgm-dashboard-configmap.yaml

echo "grafana: kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80"
echo "login admin / admin, dashboard is already there under general"
