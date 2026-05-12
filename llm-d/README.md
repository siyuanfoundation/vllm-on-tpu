# Deploy Gemma4 on TPU using llm-d

## Prerequisite

- Checkout llm-d repo:
```bash
mkdir -p tmp
export branch="main" # branch, tag, or commit hash
git clone -b ${branch} https://github.com/llm-d/llm-d.git tmp/llm-d
```
- Set the following environment variables:
```bash
export GAIE_VERSION=v1.5.0
export GUIDE_NAME="pd-disaggregation"
export NAMESPACE="llm-d-pd-disaggregation"
export MODEL_NAME="google/gemma-4-31B-it"
```
- Install the Gateway API Inference Extension CRDs:
```bash
kubectl apply -k "https://github.com/kubernetes-sigs/gateway-api-inference-extension/config/crd?ref=${GAIE_VERSION}"
```
- Create a target namespace for the installation
```bash
kubectl create namespace ${NAMESPACE}

kubectl create secret generic hf-secret --from-literal=hf_token=$HF_TOKEN -n ${NAMESPACE}
```

## Installation Instructions

### 1. Deploy the llm-d Router

#### Standalone Mode

This deploys the llm-d Router with an Envoy sidecar, it doesn't set up a Kubernetes Gateway.

```bash
export REPO_ROOT=./tmp/llm-d
helm install ${GUIDE_NAME} \
    oci://registry.k8s.io/gateway-api-inference-extension/charts/standalone \
    -f ${REPO_ROOT}/guides/recipes/scheduler/base.values.yaml \
    -f ${REPO_ROOT}/guides/${GUIDE_NAME}/scheduler/${GUIDE_NAME}.values.yaml \
    -n ${NAMESPACE} --version ${GAIE_VERSION}
```

### 2. Deploy the Model Server

Once the router is deployed, apply the Kustomize overlays specifically configured for TPU v7 and vLLM. This configuration sets up heterogeneous KV caches (HMA) and configures the TPU workers.

```bash
kubectl apply -n ${NAMESPACE} -k gpu/
```

*(Note: If you have monitoring enabled, you can optionally apply the monitoring components as described in the [main guide](./README.md#3-enable-monitoring-optional)).*

## Verification

Retrieve the proxy IP address. 

```bash
export IP=$(kubectl get service ${GUIDE_NAME}-epp -n ${NAMESPACE} -o jsonpath='{.spec.clusterIP}')
echo $IP

# or do port forward
kubectl port-forward svc/${GUIDE_NAME}-epp -n ${NAMESPACE} 8000:80
```

When sending your test request, ensure you use the correct TPU model name:

```bash
# Send a completion request to the TPU deployment
curl -X POST http://localhost:8000/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{
    "model": "google/gemma-4-31B-it",
    "messages": [
        {"role": "user", "content": "How are you today?"}
    ],
    "max_tokens": 100
    }' | jq
```

## Benchmarking

The benchmark launches a pod (`llmdbench-harness-launcher`) that, in this case, uses `inference-perf` with a synthetic workload named `20_1_isl_osl`. For more details, refer to the [benchmark instructions doc](../../helpers/benchmark.md).


```bash
export BENCHMARK_PVC="benchmark-results-pvc"
export GCS_BUCKET_NAME="<bucket-name>"

cat <<YAML | kubectl apply -n ${NAMESPACE} -f -
apiVersion: v1
kind: PersistentVolume
metadata:
  name: gcs-benchmark-pv
spec:
  accessModes:
    - ReadWriteMany
  capacity:
    storage: 200Gi
  storageClassName: "" # Use empty string for direct PV binding
  csi:
    driver: gcp-storage-fuse.csi.storage.gke.io
    volumeHandle: ${GCS_BUCKET_NAME}
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ${BENCHMARK_PVC}
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 200Gi
  volumeName: gcs-benchmark-pv
  storageClassName: ""
YAML
```

### Execute Benchmark

```bash
envsubst < benchmark/gemma4_31b.yaml > benchmark/config.yaml
./benchmark/run_only.sh -c config.yaml -o ./results
```

## Cleanup

To remove the deployed components:

```bash
helm uninstall ${GUIDE_NAME} -n ${NAMESPACE}
kubectl delete -n ${NAMESPACE} -k guides/${GUIDE_NAME}/modelserver/gpu/vllm/${INFRA_PROVIDER}
```
