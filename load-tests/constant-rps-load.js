import http from "k6/http";
import { check, fail } from "k6";
import { SharedArray } from "k6/data";
import { Rate } from "k6/metrics";

const baseUrl = __ENV.BASE_URL || "https://signaltrade.cloud";
const rate = Number(__ENV.RATE || 10);
const duration = __ENV.DURATION || "5m";
const accounts = new SharedArray("load-test accounts", () =>
  JSON.parse(open("./accounts.local.json")),
);
const businessErrors = new Rate("business_errors");

if (!Number.isInteger(rate) || rate < 1) {
  throw new Error(`RATE must be a positive integer; received ${__ENV.RATE}`);
}
if (accounts.length < 1) {
  throw new Error("accounts.local.json must contain at least one account");
}

export const options = {
  scenarios: {
    authenticated_read_throughput: {
      executor: "constant-arrival-rate",
      rate,
      timeUnit: "1s",
      duration,
      preAllocatedVUs: accounts.length,
      maxVUs: accounts.length,
    },
  },
  thresholds: {
    checks: ["rate>0.99"],
    business_errors: ["rate<0.01"],
    dropped_iterations: ["count==0"],
    "http_req_failed{phase:measurement}": ["rate<0.01"],
    "http_req_duration{phase:measurement,expected_response:true}": [
      "p(95)<1000",
      "p(99)<2000",
    ],
  },
};

const routes = [
  { weight: 30, name: "paper_account", path: "/api/paper-account" },
  { weight: 20, name: "analytics_simulated", path: "/api/analytics?mode=simulated" },
  {
    weight: 20,
    name: "strategies",
    path: "/api/strategies?mode=simulated&market=KRW-BTC",
  },
  { weight: 15, name: "trades", path: "/api/trades" },
  { weight: 15, name: "current_user", path: "/api/users/me" },
];

function chooseRoute() {
  const choice = Math.random() * 100;
  let cumulativeWeight = 0;
  for (const route of routes) {
    cumulativeWeight += route.weight;
    if (choice < cumulativeWeight) return route;
  }
  return routes[routes.length - 1];
}

export function setup() {
  const tokens = [];

  for (const credential of accounts) {
    const response = http.post(
      `${baseUrl}/api/auth/login`,
      JSON.stringify(credential),
      {
        headers: { "Content-Type": "application/json" },
        tags: { endpoint: "login", phase: "setup" },
      },
    );
    const token = response.json("token.access_token");
    const succeeded = check(response, {
      "setup login returns 200": (result) => result.status === 200,
      "setup login returns a token": () => Boolean(token),
    });
    if (!succeeded) {
      fail(`setup login failed for ${credential.username} with status ${response.status}`);
    }
    tokens.push(token);
  }

  return { tokens };
}

export default function (data) {
  const token = data.tokens[(__VU - 1) % data.tokens.length];
  const route = chooseRoute();
  const response = http.get(`${baseUrl}${route.path}`, {
    headers: { Authorization: `Bearer ${token}` },
    tags: { endpoint: route.name, phase: "measurement" },
  });
  const succeeded = check(response, {
    [`${route.name} returns 200`]: (result) => result.status === 200,
  });
  businessErrors.add(!succeeded, { endpoint: route.name });
}
