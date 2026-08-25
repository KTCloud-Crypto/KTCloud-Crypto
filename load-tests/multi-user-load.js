import http from "k6/http";
import { check, fail, sleep } from "k6";
import { SharedArray } from "k6/data";
import { Rate } from "k6/metrics";

const baseUrl = __ENV.BASE_URL || "https://signaltrade.cloud";
const accounts = new SharedArray("load-test accounts", () =>
  JSON.parse(open("./accounts.local.json")),
);
const businessErrors = new Rate("business_errors");
let accessToken;

export const options = {
  scenarios: {
    distinct_authenticated_users: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 50),
      duration: __ENV.DURATION || "5m",
    },
  },
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
  if (__VU > accounts.length) {
    fail(`VU ${__VU} has no matching account; only ${accounts.length} accounts are available`);
  }
  const credential = accounts[__VU - 1];
  const response = http.post(`${baseUrl}/api/auth/login`, JSON.stringify(credential), {
    headers: { "Content-Type": "application/json" },
    tags: { endpoint: "login" },
  });
  const succeeded = check(response, {
    "per-VU login returns 200": (result) => result.status === 200,
    "per-VU login returns a token": (result) => Boolean(result.json("token.access_token")),
  });
  if (!succeeded) fail(`VU ${__VU} login failed with status ${response.status}`);
  accessToken = response.json("token.access_token");
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
  if (!accessToken) login();
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
