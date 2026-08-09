import * as fs from "fs";
import * as path from "path";
import * as yaml from "js-yaml";
import { PostFrontmatter, Post } from "./types";

interface FrontmatterResult {
  attributes: PostFrontmatter;
  body: string;
}

export function parseFrontmatter(source: string): FrontmatterResult {
  const lines = source.split("\n");
  if (lines[0]?.trim() !== "---") {
    return { attributes: { title: "" }, body: source };
  }

  let end = 0;
  for (let i = 1; i < lines.length; i++) {
    if (lines[i]?.trim() === "---") {
      end = i;
      break;
    }
  }

  if (end === 0) {
    return { attributes: { title: "" }, body: source };
  }

  const yamlBlock = lines.slice(1, end).join("\n");
  const body = lines.slice(end + 1).join("\n");

  const attributes = yaml.load(yamlBlock) as PostFrontmatter;
  return {
    attributes: attributes || { title: "" },
    body: body.trimStart(),
  };
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    || "post";
}

export function parseMarkdownFile(filePath: string, sourceDir: string): Post {
  const raw = fs.readFileSync(filePath, "utf-8");
  const { attributes: frontmatter, body } = parseFrontmatter(raw);

  const relPath = path.relative(sourceDir, filePath);
  const parsedPath = path.parse(relPath);
  const dirName = parsedPath.dir ? parsedPath.dir.replace(/\\/g, "/") : "";
  const baseName = parsedPath.name;

  const slugBase = frontmatter.title ? slugify(frontmatter.title) : slugify(baseName);
  const slug = dirName ? `${dirName}/${slugBase}` : slugBase;

  return {
    slug,
    sourcePath: filePath,
    frontmatter,
    body,
    html: "",
    url: `/${slug}.html`,
  };
}

export function collectPosts(sourceDir: string): Post[] {
  const files = walkDir(sourceDir);
  const mdFiles = files.filter(
    (f) => f.endsWith(".md") || f.endsWith(".markdown")
  );
  return mdFiles.map((f) => parseMarkdownFile(f, sourceDir));
}

function walkDir(dir: string): string[] {
  const results: string[] = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name.startsWith(".") || entry.name.startsWith("_")) continue;
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...walkDir(fullPath));
    } else {
      results.push(fullPath);
    }
  }
  return results;
}
