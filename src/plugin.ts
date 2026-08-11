import { PageData, BuildOptions } from "./types";

export interface Plugin {
  name: string;
  onStart?(options: BuildOptions): Promise<void>;
  beforeBuild?(options: BuildOptions): Promise<void>;
  onFile?(page: PageData, options: BuildOptions): Promise<PageData>;
  afterBuild?(options: BuildOptions, pages: PageData[]): Promise<void>;
  onEnd?(options: BuildOptions): Promise<void>;
}

export async function runHook(
  plugins: Plugin[],
  hook: "onStart" | "beforeBuild" | "afterBuild" | "onEnd",
  options: BuildOptions,
  pages?: PageData[]
): Promise<void> {
  for (const plugin of plugins) {
    const fn = plugin[hook];
    if (fn) {
      if (hook === "afterBuild" && pages !== undefined) {
        await fn.call(plugin, options, pages);
      } else {
        await fn.call(plugin, options);
      }
    }
  }
}

export async function runFilePipeline(
  plugins: Plugin[],
  page: PageData,
  options: BuildOptions
): Promise<PageData> {
  let current = page;
  for (const plugin of plugins) {
    if (plugin.onFile) {
      current = await plugin.onFile(current, options);
    }
  }
  return current;
}
