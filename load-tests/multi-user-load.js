import http from "k6/http";
import { check, fail, sleep } from "k6";
import { SharedArray } from "k6/data";
import { Rate } from "k6/metrics";
import exec from "k6/execution";

const baseUrl = __ENV.BASE_URL || "https://signaltrade.cloud";
const accounts = new SharedArray("load-test accounts", () =>
  JSON.parse(open("./accounts.local.json")),
);
const businessErrors = new Rate("business_errors");
let accessToken;

const scenarioType = (__ENV.SCENARIO || "constant").toLowerCase();
const targetVus = Number(__ENV.VUS || 50);
const steadyDuration = __ENV.DURATION || "5m";
const rampUpDuration = __ENV.RAMP_UP || "1m";
const loginMaxAttempts = Number(__ENV.LOGIN_MAX_ATTEMPTS || 3);
const loginBackoffSeconds = Number(__ENV.LOGIN_BACKOFF_SECONDS || 1);

if (!Number.isInteger(targetVus) || targetVus < 1 || targetVus > accounts.length) {
  throw new Error(`VUS must be between 1 and the ${accounts.length} available accounts`);
}
if (
  !Number.isInteger(loginMaxAttempts) ||
  loginMaxAttempts < 1 ||
  !Number.isFinite(loginBackoffSeconds) ||
  loginBackoffSeconds <= 0
) {
  throw new Error("LOGIN_MAX_ATTEMPTS must be a positive integer and LOGIN_BACKOFF_SECONDS must be positive");
}

const scenarios =
  scenarioType === "ramp"
    ? {
        distinct_authenticated_users: {
          executor: "ramping-vus",
          startVUs: 0,
          stages: [
            { duration: rampUpDuration, target: targetVus },
            { duration: steadyDuration, target: targetVus },
            { duration: "30s", target: 0 },
          ],
          gracefulRampDown: "30s",
        },
      }
    : {
        distinct_authenticated_users: {
          executor: "constant-vus",
          vus: targetVus,
          duration: steadyDuration,
        },
      };

export const options = {
  scenarios,
  thresholds: {
    checks: ["rate>0.99"],
    business_errors: ["rate<0.01"],
    http_req_failed: ["rate<0.01"],
    "http_req_duration{expected_response:true}": ["p(95)<1000", "p(99)<2000"],
  },
};

const routes = [
  { weight: 30, name: "paper_account", path: "/api/paper-account" },
  { weight: 20, name: "analytics_simulated", path: "/api/analytics?mode=simulated" },
  { weight: 20, name: "strategies", path: "/api/strategies?mode=simulated&market=KRW-BTC" },
  { weight: 15, name: "trades", path: "/api/trades" },
  { weight: 15, name: "current_user", path: "/api/users/me" },
];

function login() {
  const vuId = exec.vu.idInInstance;
  const accountIndex = vuId - 1;
  if (accountIndex >= accounts.length) {
    fail(`VU ${vuId} has no matching account; only ${accounts.length} accounts are available`);
  }
  const credential = accounts[accountIndex];

  for (let attempt = 1; attempt <= loginMaxAttempts; attempt += 1) {
    const response = http.post(`${baseUrl}/api/auth/login`, JSON.stringify(credential), {
      headers: { "Content-Type": "application/json" },
      tags: { endpoint: "login", login_attempt: String(attempt) },
    });
    let token;
    try {
      token = response.json("token.access_token");
    } catch (_) {
      token = null;
    }
    const succeeded = check(response, {
      "per-VU login returns 200": (result) => result.status === 200,
      "per-VU login returns a token": () => Boolean(token),
    });
    if (succeeded) {
      accessToken = token;
      return true;
    }
    if (attempt < loginMaxAttempts) {
      sleep(loginBackoffSeconds * (2 ** (attempt - 1)) + Math.random());
    }
  }

  // Avoid an immediate retry storm in the next iteration after all attempts fail.
  sleep(loginBackoffSeconds * 4 + Math.random() * 2);
  return false;
}

function chooseRoute() {
  const choice = Math.random() * 100;
  let cumulativeWeight = 0;
  for (const route of routes) {
    cumulativeWeight += route.weight;
    if (choice < cumulativeWeight) return route;
  }
  return routes[routes.length - 1];
}

export default function () {
  if (!accessToken && !login()) return;
  const route = chooseRoute();
  const response = http.get(`${baseUrl}${route.path}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    tags: { endpoint: route.name },
  });
  const succeeded = check(response, {
    [`${route.name} returns 200`]: (result) => result.status === 200,
  });
  businessErrors.add(!succeeded, { endpoint: route.name });
  sleep(0.5 + Math.random());
}
