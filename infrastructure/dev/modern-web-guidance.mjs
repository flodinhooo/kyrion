// Development guidance only; never imported by an application bundle.
import { spawnSync } from "node:child_process";

const args = process.argv.slice(2);
if (!args.length || args[0] === "--help" || args[0] === "-h") {
  console.log(
    "Use pnpm mwg <search|retrieve|list|legacy-scan> [arguments]. CLI 1.0.0; telemetry disabled.",
  );
  process.exit(0);
}
if (
  !process.env.npm_execpath ||
  !["search", "retrieve", "list", "legacy-scan"].includes(args[0])
) {
  console.error("Use pnpm mwg <search|retrieve|list|legacy-scan> [arguments].");
  process.exit(2);
}
const result = spawnSync(
  process.execPath,
  [process.env.npm_execpath, "dlx", "modern-web-guidance@1.0.0", ...args],
  {
    stdio: "inherit",
    env: { ...process.env, DISABLE_TELEMETRY: "1" },
  },
);
if (result.error) console.error("Modern Web Guidance could not start.");
process.exit(result.status ?? 1);
