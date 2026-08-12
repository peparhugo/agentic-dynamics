import { promises as fs } from "fs";
import path from "path";
import matter from "gray-matter";
import yaml from "js-yaml";
import MarkdownIt from "markdown-it";
import { PageData, BuildOptions, Frontmatter } from "../types";
import { Plugin } from "../plugin";

const matterOptions = {
  engines: {
    yaml: {
      parse: (input: string) => yaml.load(input, { schema: yaml.FAILSAFE_SCHEMA }) as Record<string, unknown>,
    },
  },
};

export function createMarkdownPlugin(): Plugin {
  const md = new MarkdownIt();

  return {
    name: "markdown",

    async onFile(page: PageData, options: BuildOptions): Promise<PageData> {
      const contentDir = path.resolve(options.contentDir);
      const absPath = path.join(contentDir, page.path);
      const raw = await fs.readFile(absPath, "utf-8");
      const { data, content } = matter(raw, matterOptions);
      const html = md.render(content);

      const frontmatter: Frontmatter = {};
      for (const [key, value] of Object.entries(data)) {
        frontmatter[key] = String(value ?? "");
      }

      return { path: page.path, frontmatter, html };
    },
  };
}

const mdSingleton = new MarkdownIt();

export async function parseMarkdownFile(
  contentDir: string,
  filePath: string
): Promise<PageData> {
  const absPath = path.join(contentDir, filePath);
  const raw = await fs.readFile(absPath, "utf-8");
  const { data, content } = matter(raw, matterOptions);
  const html = mdSingleton.render(content);

  const frontmatter: Frontmatter = {};
  for (const [key, value] of Object.entries(data)) {
    frontmatter[key] = String(value ?? "");
  }

  return { path: filePath, frontmatter, html };
}
