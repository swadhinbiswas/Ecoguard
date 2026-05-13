import http from 'k6/http';
import { check, sleep, group } from 'k6';

export const options = {
  scenarios: {
    constant_load: {
      executor: 'constant-arrival-rate',
      rate: 20,
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 20,
      maxVUs: 50,
    },
    spike_test: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 10,
      maxVUs: 100,
      stages: [
        { target: 5, duration: '30s' },
        { target: 100, duration: '30s' },
        { target: 100, duration: '30s' },
        { target: 5, duration: '30s' },
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<2000', 'p(99)<5000'],
    http_req_failed: ['rate<0.01'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const HEADERS = { 'Content-Type': 'application/json' };

export default function () {
  group('Health Check', () => {
    let r = http.get(`${BASE_URL}/api/v1/health`);
    check(r, { 'health 200': (r) => r.status === 200 });
  });

  group('System Status', () => {
    let r = http.get(`${BASE_URL}/api/v1/system/status`);
    check(r, { 'status 200': (r) => r.status === 200 });
  });

  group('Cost Estimate', () => {
    let r = http.get(`${BASE_URL}/v1/cost/estimate?input_tokens=100&output_tokens=50`);
    check(r, { 'cost 200': (r) => r.status === 200 });
  });

  group('Guardrails Check', () => {
    let r = http.post(`${BASE_URL}/v1/guardrails/check?prompt=What+is+ML?`);
    check(r, { 'guardrails 200': (r) => r.status === 200 });
  });

  group('Leaderboard', () => {
    let r = http.get(`${BASE_URL}/api/v1/leaderboard`);
    check(r, { 'leaderboard 200': (r) => r.status === 200 });
  });

  group('Benchmarks List', () => {
    let r = http.get(`${BASE_URL}/api/v1/benchmarks`);
    check(r, { 'benchmarks 200': (r) => r.status === 200 });
  });

  group('Analytics Summary', () => {
    let r = http.get(`${BASE_URL}/api/v1/analytics/summary`);
    check(r, { 'analytics 200': (r) => r.status === 200 });
  });

  group('Predict (no model)', () => {
    let payload = JSON.stringify({ prompt: 'Hello', max_tokens: 10, temperature: 0 });
    let r = http.post(`${BASE_URL}/api/v1/predict`, payload, { headers: HEADERS });
    check(r, { 'predict called': (r) => r.status >= 200 && r.status < 600 });
  });

  sleep(1);
}
