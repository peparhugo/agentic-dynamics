import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export function makeTmpDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "ssg-test-"));
}

/** Write a tree of files: { "a/b.md": "content", ... } */
export function writeTree(root: string, files: Record<string, string>): void {
  for (const [rel, content] of Object.entries(files)) {
    const full = path.join(root, rel);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, content);
  }
}

export const BASIC_TEMPLATES: Record<string, string> = {
  "layouts/default.hbs": "<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>",
  "partials/header.hbs": "<header>{{site.title}}</header>",
  "post.hbs": "{{> header}}<article><h1>{{title}}</h1>{{{content}}}</article>",
  "index.hbs":
    "{{> header}}<ul>{{#each posts}}<li><a href=\"{{url}}\">{{frontmatter.title}}</a></li>{{/each}}</ul>" +
    "<div class=\"tags\">{{#each tags}}<a href=\"{{url}}\">{{tag}} ({{count}})</a>{{/each}}</div>",
  "tag.hbs": "<h1>Tag: {{tag}}</h1><ul>{{#each posts}}<li>{{frontmatter.title}}</li>{{/each}}</ul>",
};
