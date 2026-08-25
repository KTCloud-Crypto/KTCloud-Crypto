import http from "k6/http";
import { check, sleep } from "k6";

const baseUrl = __ENV.BASE_URL || "https://signaltrade.cloud";

export const options = {
  scenarios: {
    public_health_smoke: {
      executor: "constant-vus",
      vus: 2,
      duration: "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000"],
    checks: ["rate>0.99"],
  },
};

export default function () {
  const responses = http.batch([
    ["GET", `${baseUrl}/healthz`, null, { tags: { endpoint: "healthz" } }],
    ["GET", `${baseUrl}/api/health`, null, { tags: { endpoint: "api-health" } }],
  ]);

  check(responses[0], { "healthz returns 200": (response) => response.status === 200 });
  check(responses[1], { "api health returns 200": (response) => response.status === 200 });
  sleep(1);
}
