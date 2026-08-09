import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

export async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), "ssg-test-"));
}

/** Write a tree of files: { "a/b.md": "contents", ... } under root. */
export async function writeTree(root: string, files: Record<string, string>): Promise<void> {
  for (const [rel, contents] of Object.entries(files)) {
    const full = path.join(root, rel);
    await fs.mkdir(path.dirname(full), { recursive: true });
    await fs.writeFile(full, contents, "utf8");
  }
}

export const MINIMAL_TEMPLATES: Record<string, string> = {
  "default.hbs": `<!doctype html>
<html>
<head><title>{{title}} | {{site.title}}</title></head>
<body>
{{> header}}
<main>{{content}}</main>
{{#if posts}}<ul class="posts">{{#each posts}}<li><a href="{{url}}">{{title}}</a></li>{{/each}}</ul>{{/if}}
</body>
</html>`,
  "post.hbs": `<!doctype html>
<html>
<head><title>{{title}}</title></head>
<body>
{{> header}}
<article>
<h1>{{title}}</h1>
<time>{{formatDate date}}</time>
<ul class="tags">{{#each tags}}<li><a href="/tags/{{this}}/">{{this}}</a></li>{{/each}}</ul>
{{content}}
</article>
</body>
</html>`,
  "tag.hbs": `<!doctype html>
<html>
<head><title>{{title}}</title></head>
<body>
<h1>Posts tagged {{tag}}</h1>
<ul>{{#each posts}}<li><a href="{{url}}">{{title}}</a></li>{{/each}}</ul>
</body>
</html>`,
  "partials/header.hbs": `<header class="site-header">{{site.title}}</header>`,
};

export const SAMPLE_CONTENT: Record<string, string> = {
  "posts/hello.md": `---
title: Hello World
date: 2024-01-15
tags: [intro, meta]
---
Welcome to **my site**.

\`\`\`js
const x = 1;
\`\`\`
`,
  "posts/second.md": `---
title: Second Post
date: 2024-03-02
tags: [meta]
---
Another *post*.
`,
  "posts/secret.md": `---
title: Secret
date: 2024-04-01
draft: true
tags: [intro]
---
Not published yet.
`,
  "about.md": `---
title: About
layout: default
---
About this site.
`,
};
