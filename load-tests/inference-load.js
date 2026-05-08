import http from "k6/http";
import { check, sleep, trend } from "k6";

export const options = {
    stages: [
        { duration: "30s", target: 10 },
        { duration: "1m", target: 50 },
        { duration: "30s", target: 100 },
        { duration: "1m", target: 100 },
        { duration: "30s", target: 0 },
    ],
    thresholds: {
        http_req_duration: ["p(95)<2000"],
        http_req_failed: ["rate<0.05"],
    },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const API_KEY = __ENV.API_KEY || "";

const PROMPTS = [
    "Explain quantum computing in one sentence.",
    "What is the capital of France?",
    "Write a haiku about machine learning.",
    "Summarize the theory of relativity.",
    "What are the benefits of renewable energy?",
    "Explain what Docker does in simple terms.",
    "Write a Python function to sort a list.",
    "How does a transformer neural network work?",
    "What is the difference between SQL and NoSQL?",
    "List three ways to reduce carbon emissions.",
];

const params = {
    headers: {
        "Content-Type": "application/json",
        ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
    },
};

export default function () {
    // Health check
    const health = http.get(`${BASE_URL}/api/v1/health`);
    check(health, { "health ok": (r) => r.status === 200 });

    // Metrics
    http.get(`${BASE_URL}/metrics`);

    // Root
    http.get(`${BASE_URL}/`);

    // Inference
    const prompt = PROMPTS[Math.floor(Math.random() * PROMPTS.length)];
    const payload = JSON.stringify({
        prompt: prompt,
        max_tokens: 32,
        temperature: 0.7,
    });

    const predict = http.post(`${BASE_URL}/api/v1/predict`, payload, params);
    if (predict.status === 503) {
        // Model not loaded, expected
    } else {
        check(predict, { "predict ok": (r) => r.status === 200 });
    }

    // Models list
    http.get(`${BASE_URL}/api/v1/models`);

    // Dashboard pages
    http.get(`${BASE_URL}/dashboard`);
    http.get(`${BASE_URL}/dashboard/inference`);

    sleep(1);
}

export function teardown() {
    console.log("Load test completed.");
}
