import path from "path";
import { promises as fs } from "fs";
import os from "os";
import { build } from "../index";

let testDir: string;

beforeEach(async () => {
  testDir = await fs.mkdtemp(path.join(os.tmpdir(), "ssg-test-"));
});

describe("ssg build", () => {
  test("creates output directory", async () => {
    const contentDir = path.resolve(__dirname, "..", "..", "content");
    const tmpOut = path.join(testDir, "out1");

    await build({ contentDir, outputDir: tmpOut });

    const content = await fs.readdir(tmpOut);
    expect(content.length).toBeGreaterThan(0);
  });

  test("generates index.html listing all pages", async () => {
    const contentDir = path.resolve(__dirname, "..", "..", "content");
    const tmpOut = path.join(testDir, "out2");

    await build({ contentDir, outputDir: tmpOut });

    const indexHtml = await fs.readFile(
      path.join(tmpOut, "index.html"),
      "utf-8"
    );
    expect(indexHtml).toContain("<title>Site Index</title>");
    expect(indexHtml).toContain("Hello World");
    expect(indexHtml).toContain("About");
    expect(indexHtml).toContain("No Date Page");
  });

  test("index.html lists pages in alphabetical order by path", async () => {
    const contentDir = path.resolve(__dirname, "..", "..", "content");
    const tmpOut = path.join(testDir, "out3");

    await build({ contentDir, outputDir: tmpOut });

    const indexHtml = await fs.readFile(
      path.join(tmpOut, "index.html"),
      "utf-8"
    );
    const aboutIdx = indexHtml.indexOf("About");
    const helloIdx = indexHtml.indexOf("Hello World");
    const notagsIdx = indexHtml.indexOf("No Date Page");
    expect(aboutIdx).toBeLessThan(helloIdx);
    expect(helloIdx).toBeLessThan(notagsIdx);
  });

  test("generates individual HTML pages", async () => {
    const contentDir = path.resolve(__dirname, "..", "..", "content");
    const tmpOut = path.join(testDir, "out4");

    await build({ contentDir, outputDir: tmpOut });

    const aboutHtml = await fs.readFile(
      path.join(tmpOut, "about.html"),
      "utf-8"
    );
    expect(aboutHtml).toContain("<title>About</title>");
    expect(aboutHtml).toContain("<h2>About This Site</h2>");

    const helloHtml = await fs.readFile(
      path.join(tmpOut, "hello.html"),
      "utf-8"
    );
    expect(helloHtml).toContain("<title>Hello World</title>");
    expect(helloHtml).toContain("<h1>Hello World</h1>");
  });

  test("index.html uses frontmatter as unescaped HTML strings", async () => {
    const contentDir = path.resolve(__dirname, "..", "..", "content");
    const tmpOut = path.join(testDir, "out5");

    await build({ contentDir, outputDir: tmpOut });

    const indexHtml = await fs.readFile(
      path.join(tmpOut, "index.html"),
      "utf-8"
    );
    expect(indexHtml).toContain("2024-01-15");
    expect(indexHtml).toContain("Tags: intro, hello");
    expect(indexHtml).toContain("2024-02-20");
    expect(indexHtml).toContain("Tags: meta");
  });

  test("pages with no date/tags omit those sections", async () => {
    const contentDir = path.resolve(__dirname, "..", "..", "content");
    const tmpOut = path.join(testDir, "out6");

    await build({ contentDir, outputDir: tmpOut });

    const notagsHtml = await fs.readFile(
      path.join(tmpOut, "notags.html"),
      "utf-8"
    );
    expect(notagsHtml).not.toContain("class=\"date\"");
    expect(notagsHtml).not.toContain("class=\"tags\"");
  });

  test("markdown body is rendered as HTML in page output", async () => {
    const contentDir = path.resolve(__dirname, "..", "..", "content");
    const tmpOut = path.join(testDir, "out7");

    await build({ contentDir, outputDir: tmpOut });

    const aboutHtml = await fs.readFile(
      path.join(tmpOut, "about.html"),
      "utf-8"
    );
    expect(aboutHtml).toContain("<li>Item one</li>");
    expect(aboutHtml).toContain("<li>Item two</li>");
  });

  test("error on missing content directory", async () => {
    const badDir = path.join(testDir, "nonexistent");
    const tmpOut = path.join(testDir, "out8");

    await expect(build({ contentDir: badDir, outputDir: tmpOut })).rejects.toThrow(
      "Content directory not found"
    );
  });

  test("creates subdirectory output for files in subdirectories", async () => {
    const contentDir = path.join(testDir, "content-nested");
    const subDir = path.join(contentDir, "posts");
    await fs.mkdir(subDir, { recursive: true });
    await fs.writeFile(
      path.join(subDir, "nested-post.md"),
      `---
title: Nested Post
---

# Nested

Content in a subdirectory.
`
    );
    await fs.writeFile(
      path.join(contentDir, "root-page.md"),
      `---
title: Root Page
---

# Root

Content at root level.
`
    );

    const tmpOut = path.join(testDir, "out9");
    await build({ contentDir, outputDir: tmpOut });

    const nestedExists = await fs
      .access(path.join(tmpOut, "posts", "nested-post.html"))
      .then(() => true)
      .catch(() => false);
    expect(nestedExists).toBe(true);

    const rootExists = await fs
      .access(path.join(tmpOut, "root-page.html"))
      .then(() => true)
      .catch(() => false);
    expect(rootExists).toBe(true);

    const nestedHtml = await fs.readFile(
      path.join(tmpOut, "posts", "nested-post.html"),
      "utf-8"
    );
    expect(nestedHtml).toContain("<title>Nested Post</title>");

    const indexHtml = await fs.readFile(
      path.join(tmpOut, "index.html"),
      "utf-8"
    );
    expect(indexHtml).toContain("Nested Post");
    expect(indexHtml).toContain("Root Page");
    expect(indexHtml).toContain('href="posts/nested-post.html"');
    expect(indexHtml).toContain('href="root-page.html"');
  });
});
