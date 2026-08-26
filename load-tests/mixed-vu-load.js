import http from "k6/http";
import { check, fail, sleep } from "k6";
import { SharedArray } from "k6/data";
import { Rate } from "k6/metrics";

const baseUrl = __ENV.BASE_URL || "https://signaltrade.cloud";
const vus = Number(__ENV.VUS || 25);
const duration = __ENV.DURATION || "5m";
const writeRatio = Number(__ENV.WRITE_RATIO || 0.1);
const accounts = new SharedArray("load-test accounts", () =>
  JSON.parse(open("./accounts.local.json")),
);
const businessErrors = new Rate("business_errors");
const writeRequestRatio = new Rate("write_request_ratio");

if (!Number.isInteger(vus) || vus < 1) {
  throw new Error(`VUS must be a positive integer; received ${__ENV.VUS}`);
}
if (vus > accounts.length) {
  throw new Error(`VUS ${vus} exceeds the ${accounts.length} available accounts`);
}
if (!Number.isFinite(writeRatio) || writeRatio < 0 || writeRatio > 1) {
  throw new Error(`WRITE_RATIO must be between 0 and 1; received ${__ENV.WRITE_RATIO}`);
}

export const options = {
  scenarios: {
    distinct_authenticated_mixed_users: {
      executor: "constant-vus",
      vus,
      duration,
    },
  },
  thresholds: {
    checks: ["rate>0.99"],
    business_errors: ["rate<0.01"],
    "http_req_failed{phase:measurement}": ["rate<0.01"],
    "http_req_failed{phase:measurement,operation:read}": ["rate<0.01"],
    "http_req_failed{phase:measurement,operation:write}": ["rate<0.01"],
    "http_req_duration{phase:measurement,expected_response:true}": [
      "p(95)<1000",
      "p(99)<2000",
    ],
    "http_req_duration{phase:measurement,operation:read,expected_response:true}": [
      "p(95)<1000",
      "p(99)<2000",
    ],
    "http_req_duration{phase:measurement,operation:write,expected_response:true}": [
      "p(95)<1000",
      "p(99)<2000",
    ],
  },
};

const readRoutes = [
  { weight: 25, name: "paper_account", path: "/api/paper-account" },
  { weight: 20, name: "analytics_simulated", path: "/api/analytics?mode=simulated" },
  {
    weight: 20,
    name: "strategies",
    path: "/api/strategies?mode=simulated&market=KRW-BTC",
  },
  { weight: 15, name: "trades", path: "/api/trades" },
  { weight: 10, name: "current_user", path: "/api/users/me" },
  { weight: 10, name: "active_strategies", path: "/api/strategies/active?mode=simulated" },
];

let accessToken;
let strategyId;
let writeSequence = 0;

function chooseReadRoute() {
  const choice = Math.random() * 100;
  let cumulativeWeight = 0;
  for (const route of readRoutes) {
    cumulativeWeight += route.weight;
    if (choice < cumulativeWeight) return route;
  }
  return readRoutes[readRoutes.length - 1];
}

function initializeVu() {
  const credential = accounts[__VU - 1];
  const loginResponse = http.post(
    `${baseUrl}/api/auth/login`,
    JSON.stringify(credential),
    {
      headers: { "Content-Type": "application/json" },
      tags: { endpoint: "login", phase: "setup", operation: "write" },
    },
  );
  const token = loginResponse.json("token.access_token");
  const loginSucceeded = check(loginResponse, {
    "per-VU login returns 200": (result) => result.status === 200,
    "per-VU login returns a token": () => Boolean(token),
  });
  if (!loginSucceeded) {
    fail(`VU ${__VU} login failed with status ${loginResponse.status}`);
  }
  accessToken = token;

  const strategiesResponse = http.get(
    `${baseUrl}/api/strategies?mode=simulated&market=KRW-BTC`,
    {
      headers: { Authorization: `Bearer ${accessToken}` },
      tags: { endpoint: "strategy_discovery", phase: "setup", operation: "read" },
    },
  );
  const firstStrategyId = strategiesResponse.json("0.id");
  const discoverySucceeded = check(strategiesResponse, {
    "strategy discovery returns 200": (result) => result.status === 200,
    "strategy discovery returns at least one strategy": () =>
      Number.isInteger(firstStrategyId),
  });
  if (!discoverySucceeded) {
    fail(`VU ${__VU} could not select a simulated strategy`);
  }
  strategyId = firstStrategyId;
}

function readRequest() {
  const route = chooseReadRoute();
  const response = http.get(`${baseUrl}${route.path}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    tags: { endpoint: route.name, phase: "measurement", operation: "read" },
  });
  const succeeded = check(response, {
    [`${route.name} returns 200`]: (result) => result.status === 200,
  });
  businessErrors.add(!succeeded, { endpoint: route.name, operation: "read" });
}

function writeRequest() {
  const investRatio = writeSequence % 2 === 0 ? 0.05 : 0.06;
  writeSequence += 1;
  const response = http.put(
    `${baseUrl}/api/strategies/${strategyId}/subscription?mode=simulated&market=KRW-BTC`,
    JSON.stringify({
      enabled: true,
      invest_ratio: investRatio,
      timeframe_minutes: 15,
      stop_loss_rate: 0.03,
      take_profit_rate: 0.05,
    }),
    {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      tags: {
        endpoint: "strategy_subscription_update",
        phase: "measurement",
        operation: "write",
      },
    },
  );
  const succeeded = check(response, {
    "strategy subscription update returns 200": (result) => result.status === 200,
    "strategy subscription remains enabled": (result) =>
      result.status === 200 && result.json("selected") === true,
    "strategy subscription saves the requested ratio": (result) =>
      result.status === 200 &&
      Math.abs(Number(result.json("invest_ratio")) - investRatio) < 0.000001,
    "strategy subscription stays in the safe timeframe": (result) =>
      result.status === 200 && result.json("selected_timeframe_minutes") === 15,
  });
  businessErrors.add(!succeeded, {
    endpoint: "strategy_subscription_update",
    operation: "write",
  });
}

export default function () {
  if (!accessToken || !strategyId) initializeVu();

  const isWrite = Math.random() < writeRatio;
  writeRequestRatio.add(isWrite);
  if (isWrite) {
    writeRequest();
  } else {
    readRequest();
  }

  sleep(0.5 + Math.random());
}
