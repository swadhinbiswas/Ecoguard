# Eco-Guard

Eco-Guard is an automated LLM inference gateway and observability platform engineered for high-performance, resource-efficient local LLM serving. 

## Value Proposition
- **Resource Efficient**: Built on `llama-cpp-python` for highly optimized CPU inference, heavily reducing cloud infrastructure costs.
- **Production Ready**: Kubernetes-native design, asynchronous SQLAlchemy 2.0 with PostgreSQL, and strict Pydantic payload validation.
- **Built-in Observability**: Statistical drift detection, structured JSON logging, and robust latency monitoring.

## Architecture Goals
- **Clean Architecture**: Separation of concerns across API routing, business logic, persistence layers, and external model services.
- **Scalability**: Stateless inference gateway engineered for horizontal scaling (HPA definitions included).
- **Security**: Robust prompt sanitization, null-byte injection prevention, and strict token bound limits.

## Observability Goals
- End-to-end request tracing via custom UUID injection middleware.
- Comprehensive inference logging mapping inputs, outputs, tokens, and hardware latency to a PostgreSQL data warehouse.
- Simple Statistical Drift Detection for tracking model behavior distributions over time.

## Automated Retraining Roadmap
- **Phase 1 (Current)**: Data ingestion and continuous inference metrics logging.
- **Phase 2**: Asynchronous Kubernetes workers processing inference logs for anomaly and semantic drift labeling.
- **Phase 3**: Automated fine-tuning (LoRA/QLoRA) pipelines triggered dynamically by drift thresholds.

## Local Setup Instructions

1. **Install Poetry**:
   ```bash
   pip install poetry
   ```
2. **Install Dependencies**:
   ```bash
   poetry install
   ```
3. **Provision Model Weights**:
   Place a GGUF model (e.g., TinyLlama) in the `./models/` directory.
   ```bash
   mkdir -p models
   wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf -O models/tinyllama.gguf
   ```
4. **Run Application**:
   ```bash
   poetry run uvicorn src.main:app --reload
   ```

## Docker Compose Deployment
```bash
docker-compose up --build
```
This orchestrates the FastAPI application and a PostgreSQL 15 instance, automatically mapping volumes for long-term database persistence and model weights.

## API Examples

### Health Check (K8s Probe)
```bash
curl -X GET http://localhost:8000/api/v1/health
```

### Run Inference
```bash
curl -X POST http://localhost:8000/api/v1/predict \
-H "Content-Type: application/json" \
-d '{
  "prompt": "Explain quantum computing in one sentence.", 
  "max_tokens": 64, 
  "temperature": 0.7
}'
```

## Future Technical Improvements
- Implement distributed tracing with OpenTelemetry standard.
- Migrate drift detection computations to background Celery workers.
- Add Redis semantic caching for high-frequency duplicated queries.
- Expand security layer to include Presidio PII anonymization.
