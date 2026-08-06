import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";

export interface Fixture {
  root: string;
  source: string;
  templates: string;
  output: string;
  cleanup(): Promise<void>;
}

const DEFAULT_LAYOUT = `<!DOCTYPE html>
<html>
<head><title>{{title}} - {{site.title}}</title></head>
<body>
{{> header}}
<main>{{{content}}}</main>
</body>
</html>`;

const TAG_LAYOUT = `<!DOCTYPE html>
<html>
<head><title>{{title}}</title></head>
<body>
<h1>{{tag}}</h1>
<ul>{{#each pages}}<li><a href="{{url}}">{{title}}</a></li>{{/each}}</ul>
</body>
</html>`;

const HEADER_PARTIAL = `<header class="site-header">{{site.title}}</header>`;

/** Create a temp site with default templates; add content via `files`. */
export async function makeFixture(files: Record<string, string> = {}): Promise<Fixture> {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "ssg-test-"));
  const source = path.join(root, "content");
  const templates = path.join(root, "templates");
  const output = path.join(root, "out");

  await fs.mkdir(path.join(templates, "layouts"), { recursive: true });
  await fs.mkdir(path.join(templates, "partials"), { recursive: true });
  await fs.mkdir(source, { recursive: true });

  await fs.writeFile(path.join(templates, "layouts", "default.hbs"), DEFAULT_LAYOUT);
  await fs.writeFile(path.join(templates, "layouts", "tag.hbs"), TAG_LAYOUT);
  await fs.writeFile(path.join(templates, "partials", "header.hbs"), HEADER_PARTIAL);

  for (const [rel, contents] of Object.entries(files)) {
    const abs = path.join(source, rel);
    await fs.mkdir(path.dirname(abs), { recursive: true });
    await fs.writeFile(abs, contents);
  }

  return {
    root,
    source,
    templates,
    output,
    cleanup: () => fs.rm(root, { recursive: true, force: true }),
  };
}

export const POST = (
  title: string,
  extra: Record<string, string | boolean> = {},
  body = `# ${title}\n\nHello *world*.`
): string => {
  const lines = [`title: ${title}`];
  for (const [k, v] of Object.entries(extra)) lines.push(`${k}: ${v}`);
  return `---\n${lines.join("\n")}\n---\n\n${body}\n`;
};
