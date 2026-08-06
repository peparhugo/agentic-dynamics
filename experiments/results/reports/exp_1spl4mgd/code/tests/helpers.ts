import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

export interface Fixture {
  root: string;
  sourceDir: string;
  templateDir: string;
  outDir: string;
  cleanup: () => Promise<void>;
}

const DEFAULT_LAYOUT = `<!doctype html>
<html>
<head><title>{{page.title}} — {{site.title}}</title></head>
<body>
{{> header}}
<article>{{{content}}}</article>
</body>
</html>`;

const POST_LAYOUT = `<!doctype html>
<html>
<head><title>{{page.title}}</title></head>
<body>
{{> header}}
<article class="post">
<h1>{{page.title}}</h1>
<time>{{formatDate page.date}}</time>
{{{content}}}
<ul class="tags">{{#each page.tags}}<li>{{this}}</li>{{/each}}</ul>
</article>
</body>
</html>`;

const TAG_LAYOUT = `<!doctype html>
<html>
<head><title>{{page.title}}</title></head>
<body>
<h1>Posts tagged {{tag}}</h1>
<ul>{{#each pages}}<li><a href="{{url}}">{{title}}</a></li>{{/each}}</ul>
</body>
</html>`;

const TAGS_LAYOUT = `<!doctype html>
<html><body>
<h1>All tags</h1>
<ul>{{#each tags}}<li><a href="{{url}}">{{tag}} ({{count}})</a></li>{{/each}}</ul>
</body></html>`;

const HEADER_PARTIAL = `<header class="site-header">{{site.title}}</header>`;

export const FIXTURE_CONTENT: Record<string, string> = {
  "index.md": `---
title: Home
layout: default
---
# Welcome

This is the home page.
`,
  "posts/hello.md": `---
title: Hello World
date: 2026-01-15
tags: [intro, typescript]
layout: post
---
First post!

\`\`\`ts
const x: number = 42;
\`\`\`
`,
  "posts/second.md": `---
title: Second Post
date: 2026-02-01
tags: intro, news
layout: post
---
Another post.
`,
  "posts/secret.md": `---
title: Secret
date: 2026-03-01
draft: true
layout: post
---
Not published yet.
`,
  "style.css": `body { font-family: sans-serif; }`,
};

export async function makeFixture(
  content: Record<string, string> = FIXTURE_CONTENT
): Promise<Fixture> {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "statik-test-"));
  const sourceDir = path.join(root, "content");
  const templateDir = path.join(root, "templates");
  const outDir = path.join(root, "out");

  for (const [rel, body] of Object.entries(content)) {
    const file = path.join(sourceDir, rel);
    await fs.mkdir(path.dirname(file), { recursive: true });
    await fs.writeFile(file, body, "utf8");
  }

  const layouts = path.join(templateDir, "layouts");
  const partials = path.join(templateDir, "partials");
  await fs.mkdir(layouts, { recursive: true });
  await fs.mkdir(partials, { recursive: true });
  await fs.writeFile(path.join(layouts, "default.hbs"), DEFAULT_LAYOUT);
  await fs.writeFile(path.join(layouts, "post.hbs"), POST_LAYOUT);
  await fs.writeFile(path.join(layouts, "tag.hbs"), TAG_LAYOUT);
  await fs.writeFile(path.join(layouts, "tags.hbs"), TAGS_LAYOUT);
  await fs.writeFile(path.join(partials, "header.hbs"), HEADER_PARTIAL);

  return {
    root,
    sourceDir,
    templateDir,
    outDir,
    cleanup: () => fs.rm(root, { recursive: true, force: true }),
  };
}

export async function readOut(fixture: Fixture, rel: string): Promise<string> {
  return fs.readFile(path.join(fixture.outDir, rel), "utf8");
}

export async function exists(fixture: Fixture, rel: string): Promise<boolean> {
  try {
    await fs.access(path.join(fixture.outDir, rel));
    return true;
  } catch {
    return false;
  }
}
