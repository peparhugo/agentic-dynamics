import chokidar from "chokidar";
import { Generator } from "./generator";
import { GeneratorConfig } from "./types";

export function watch(config: GeneratorConfig, onRebuild: () => void): () => void {
  const generator = new Generator(config);

  const watcher = chokidar.watch(
    [config.sourceDir, config.templateDir],
    {
      ignoreInitial: true,
      ignored: [
        /(^|[\/\\])\../,
        "**/node_modules/**",
      ],
    },
  );

  let rebuildTimer: NodeJS.Timeout | null = null;

  function rebuild(): void {
    if (rebuildTimer) clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(() => {
      try {
        generator.build();
        console.log("[watcher] Site rebuilt");
        onRebuild();
      } catch (err) {
        console.error("[watcher] Build error:", err);
      }
    }, 300);
  }

  watcher.on("add", rebuild);
  watcher.on("change", rebuild);
  watcher.on("unlink", rebuild);

  return () => {
    watcher.close();
  };
}
