import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";

export interface Fixture {
  root: string;
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  cleanup(): Promise<void>;
}

/** Create an isolated temp site with source/template/output dirs. */
export async function makeFixture(files: Record<string, string> = {}): Promise<Fixture> {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "ssg-test-"));
  const sourceDir = path.join(root, "content");
  const templateDir = path.join(root, "templates");
  const outputDir = path.join(root, "out");
  await fs.mkdir(sourceDir, { recursive: true });
  await fs.mkdir(templateDir, { recursive: true });
  for (const [rel, content] of Object.entries(files)) {
    const full = path.join(root, rel);
    await fs.mkdir(path.dirname(full), { recursive: true });
    await fs.writeFile(full, content, "utf8");
  }
  return {
    root,
    sourceDir,
    templateDir,
    outputDir,
    cleanup: () => fs.rm(root, { recursive: true, force: true }),
  };
}

export const DEFAULT_LAYOUT = `<!doctype html>
<html>
<head><title>{{title}} - {{site.title}}</title></head>
<body>
{{> nav}}
<main>{{{content}}}</main>
</body>
</html>`;

export const NAV_PARTIAL = `<nav>home</nav>`;
