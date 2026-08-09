#!/usr/bin/env node
import { parseArgs, printHelp } from "./cli";
import { build } from "./build";
import { startDevServer } from "./server";

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    console.log(printHelp());
    process.exit(0);
  }

  const config = parseArgs(args);

  if (config.serve) {
    await build(config, true);
    startDevServer(config);
  } else if (config.watch) {
    await build(config);
    console.log("[statico] Build complete. Watching for changes...");

    const chokidar = await import("chokidar");
    const watcher = chokidar.watch([config.sourceDir, config.templateDir], {
      ignoreInitial: true,
    });

    watcher.on("all", async () => {
      try {
        await build(config);
        console.log("[statico] Rebuilt at", new Date().toLocaleTimeString());
      } catch (err) {
        console.error("[statico] Build error:", err);
      }
    });

    process.on("SIGINT", () => {
      watcher.close();
      process.exit(0);
    });
  } else {
    await build(config);
    console.log("[statico] Build complete.");
  }
}

main().catch((err) => {
  console.error("[statico] Error:", err);
  process.exit(1);
});
