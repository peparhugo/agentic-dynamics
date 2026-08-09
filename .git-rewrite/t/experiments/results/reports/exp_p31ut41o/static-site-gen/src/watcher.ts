import { watch, FSWatcher } from "chokidar";
import type { SiteConfig } from "./types.js";
import { build } from "./generator.js";

export function createWatcher(
  config: SiteConfig,
  onRebuild: () => void,
): FSWatcher {
  const watcher = watch([config.sourceDir, config.templateDir], {
    ignoreInitial: true,
    awaitWriteFinish: {
      stabilityThreshold: 200,
      pollInterval: 100,
    },
  });

  let timeout: ReturnType<typeof setTimeout> | null = null;

  const scheduleRebuild = async () => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(async () => {
      try {
        await build(config);
        onRebuild();
      } catch (err) {
        console.error("Rebuild error:", err);
      }
    }, 150);
  };

  watcher.on("add", scheduleRebuild);
  watcher.on("change", scheduleRebuild);
  watcher.on("unlink", scheduleRebuild);

  return watcher;
}
