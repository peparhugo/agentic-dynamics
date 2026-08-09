import { watch, FSWatcher } from "chokidar";
import { SiteConfig } from "./types.js";
import { build } from "./build.js";
import { reloadClients } from "./dev-server.js";

export function startWatcher(config: SiteConfig): FSWatcher {
  build(config);
  console.log("Initial build complete.");

  const watcher = watch([config.sourceDir, config.templateDir], {
    ignoreInitial: true,
    ignored: /(^|[\/\\])\../,
  });

  let debounce: ReturnType<typeof setTimeout> | null = null;

  watcher.on("all", (event, path) => {
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => {
      console.log(`Change detected: ${event} ${path}`);
      build(config);
      reloadClients();
    }, 200);
  });

  return watcher;
}
