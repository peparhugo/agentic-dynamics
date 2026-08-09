import fs from "fs";
import path from "path";

export function resolveConfigPath(customPath?: string): string {
  if (customPath) {
    if (fs.existsSync(customPath)) return customPath;
    throw new Error(`Config file not found: ${customPath}`);
  }
  const candidates = [
    path.join(process.cwd(), "staticsmith.json"),
    path.join(process.cwd(), "staticsmith.config.json"),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  throw new Error(
    "No config file found. Create staticsmith.json in your project root."
  );
}

export function loadConfig(configPath?: string): {
  site: {
    title: string;
    description: string;
    url: string;
    author?: string;
    language?: string;
  };
  sourceDir?: string;
  outputDir?: string;
  templatesDir?: string;
} {
  const resolved = resolveConfigPath(configPath);
  return JSON.parse(fs.readFileSync(resolved, "utf-8"));
}
