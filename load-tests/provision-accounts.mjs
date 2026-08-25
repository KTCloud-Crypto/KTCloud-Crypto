import { randomBytes } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";

const baseUrl = process.env.BASE_URL || "https://signaltrade.cloud";
const accountCount = Number(process.env.ACCOUNT_COUNT || 50);
const outputPath = new URL("./accounts.local.json", import.meta.url);
let accounts = [];

try {
  accounts = JSON.parse(await readFile(outputPath, "utf8"));
} catch (error) {
  if (error.code !== "ENOENT") throw error;
}

function password() {
  return `K6a1_${randomBytes(12).toString("base64url")}`;
}

async function request(path, options) {
  const response = await fetch(`${baseUrl}${path}`, options);
  const body = await response.text();
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}: ${body}`);
  }
  return body ? JSON.parse(body) : null;
}

for (let index = accounts.length + 1; index <= accountCount; index += 1) {
  const suffix = String(index).padStart(3, "0");
  const credential = {
    username: `loadtest50_${suffix}`,
    password: password(),
  };

  await request("/api/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...credential,
      nickname: `부하${suffix}`,
    }),
  });

  const login = await request("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credential),
  });

  await request("/api/paper-account", {
    headers: { Authorization: `Bearer ${login.token.access_token}` },
  });

  accounts.push(credential);
  await writeFile(outputPath, `${JSON.stringify(accounts, null, 2)}\n`, { mode: 0o600 });
  console.log(`provisioned ${credential.username} (${index}/${accountCount})`);
  await new Promise((resolve) => setTimeout(resolve, 200));
}

console.log(`saved ${accounts.length} credentials to ${outputPath.pathname}`);
