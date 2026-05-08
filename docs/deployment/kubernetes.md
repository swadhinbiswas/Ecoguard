# Kubernetes Deployment

Eco-Guard provides Kubernetes manifests and a Helm chart for production cluster deployment.

## Kubernetes Manifests

The `k8s/` directory contains:

```
k8s/
├── deployment.yaml    # Deployment with 2 replicas, probes, resource limits
├── service.yaml       # ClusterIP service + PVC for model storage
├── hpa.yaml           # HorizontalPodAutoscaler (CPU + memory)
└── configmap.yaml     # ConfigMap + Secret for configuration
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: eco-guard-api
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  template:
    metadata:
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      terminationGracePeriodSeconds: 30
      containers:
        - name: api
          image: eco-guard:latest
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: eco-guard-config
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: eco-guard-secrets
                  key: DATABASE_URL
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2000m"
              memory: "2Gi"
          volumeMounts:
            - name: model-volume
              mountPath: /app/models
              readOnly: true
```

### Liveness and Readiness Probes

```yaml
livenessProbe:
  httpGet:
    path: /api/v1/health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 15
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /api/v1/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
```

- **Liveness**: Checks `/api/v1/health`. If the pod is running but unhealthy, Kubernetes restarts it.
- **Readiness**: Checks `/api/v1/ready` (model loaded). If not ready, the pod is removed from the service's load balancer.

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: eco-guard-service
spec:
  selector:
    app: eco-guard
  ports:
    - name: http
      port: 80
      targetPort: 8000
  type: ClusterIP
```

Internal-only `ClusterIP` type — use an Ingress or LoadBalancer for external access.

### PersistentVolumeClaim

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: eco-guard-models-pvc
spec:
  accessModes:
    - ReadOnlyMany
  resources:
    requests:
      storage: 20Gi
```

Models are stored on a shared PVC mounted read-only to all pods.

### HorizontalPodAutoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: eco-guard-hpa
spec:
  scaleTargetRef:
    name: eco-guard-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 2
          periodSeconds: 30
```

Scale behavior:
- **Scale up**: Add up to 2 pods every 30 seconds
- **Scale down**: Remove 1 pod every 60 seconds after 5 minutes of stabilization

### ConfigMap and Secret

```yaml
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: eco-guard-config
data:
  MODEL_PATH: "/app/models/tinyllama.gguf"
  ENVIRONMENT: "production"
  LOG_LEVEL: "INFO"
  RATE_LIMIT_ENABLED: "true"
  RATE_LIMIT_REQUESTS: "100"
  METRICS_ENABLED: "true"
---
apiVersion: v1
kind: Secret
metadata:
  name: eco-guard-secrets
type: Opaque
stringData:
  DATABASE_URL: "postgresql+asyncpg://postgres:password@eco-guard-db-service:5432/ecoguard"
```

> **Note:** In production, use a secrets manager (Vault, Sealed Secrets, External Secrets) rather than plain `stringData`.

## Helm Chart

A Helm chart is available at `helm/eco-guard/`:

### Chart Structure

```
helm/eco-guard/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── _helpers.tpl
    └── all.yaml
```

### Installing

```bash
# Add values override
cat > my-values.yaml << 'EOF'
config:
  jwtSecret: "your-production-secret"
  authEnabled: true
  apiKeys:
    - "your-production-key"
  adminPassword: "secure-password"

postgresql:
  enabled: true
  auth:
    password: "strong-postgres-password"

modelVolume:
  enabled: true
  size: 20Gi
EOF

# Install
helm install eco-guard ./helm/eco-guard \
  -f my-values.yaml \
  --namespace eco-guard \
  --create-namespace
```

### Helm Values Reference

```yaml
replicaCount: 2

image:
  repository: eco-guard
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80
  targetPort: 8000

ingress:
  enabled: false
  className: nginx
  host: eco-guard.local

resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 2000m
    memory: 2Gi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPU: 70
  targetMemory: 80

config:
  environment: production
  logLevel: INFO
  authEnabled: false
  apiKeys: []
  rateLimitEnabled: true
  rateLimitRequests: 100
  rateLimitWindowSeconds: 60
  metricsEnabled: true
  cacheEnabled: false
  maxConcurrentInference: 4
  modelWarmupEnabled: true
  autoMigrate: true
  driftAlertThreshold: 0.8
  requestTimeoutSeconds: 120
  shutdownDrainTimeout: 15

postgresql:
  enabled: true
  auth:
    username: postgres
    password: ecoguard
    database: ecoguard

modelVolume:
  enabled: true
  storageClass: ""
  size: 20Gi
  accessMode: ReadOnlyMany

monitoring:
  serviceMonitor:
    enabled: false
  prometheus:
    scrape: true
    port: 8000
    path: /metrics

tracing:
  enabled: false
  otlpEndpoint: ""
```

## Prometheus Annotations

The deployment template includes Prometheus scrape annotations:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/metrics"
```

With the Prometheus Operator, enable the ServiceMonitor:

```yaml
monitoring:
  serviceMonitor:
    enabled: true
```

## Resource Requirements

### Per-Pod Baseline

| Resource | Request | Limit | Rationale |
|----------|---------|-------|-----------|
| CPU | 500m | 2000m | GGUF inference is CPU-bound; more cores = faster |
| Memory | 512Mi | 2Gi | Model loading may require significant RAM |

### Model Size Impact

| Model Size | Recommended Memory Limit |
|------------|-------------------------|
| < 1B params (Q4) | 512Mi |
| 1B–3B params (Q4) | 1Gi |
| 3B–7B params (Q4) | 2Gi |
| 7B–13B params (Q4) | 4Gi+ |

## Deployment Steps

```bash
# 1. Create namespace
kubectl create namespace eco-guard

# 2. Apply ConfigMap and Secret
kubectl apply -f k8s/configmap.yaml -n eco-guard

# 3. Create PVC for models
kubectl apply -f k8s/service.yaml -n eco-guard

# 4. Deploy the application
kubectl apply -f k8s/deployment.yaml -n eco-guard

# 5. Create HPA
kubectl apply -f k8s/hpa.yaml -n eco-guard

# 6. Check status
kubectl get pods -n eco-guard
kubectl logs -f deployment/eco-guard-api -n eco-guard

# 7. Port-forward for testing
kubectl port-forward svc/eco-guard-service 8000:80 -n eco-guard
curl http://localhost:8000/api/v1/health
```

## Ingress Configuration

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: eco-guard-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-read-timeout: "120"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - api.eco-guard.example.com
      secretName: eco-guard-tls
  rules:
    - host: api.eco-guard.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: eco-guard-service
                port:
                  number: 80
```

Note the `proxy-read-timeout: "120"` annotation matching `REQUEST_TIMEOUT_SECONDS`.
