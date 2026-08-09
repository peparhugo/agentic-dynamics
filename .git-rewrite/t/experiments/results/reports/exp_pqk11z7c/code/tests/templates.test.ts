import { describe, it, expect, beforeAll, afterAll } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createTemplateEngine } from "../src/templates.js";

let dir: string;

beforeAll(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), "ssg-tpl-"));
  fs.mkdirSync(path.join(dir, "layouts"));
  fs.mkdirSync(path.join(dir, "partials"));
  fs.writeFileSync(
    path.join(dir, "layouts", "default.hbs"),
    `<html><title>{{title}}</title><body>{{> header}}{{{body}}}</body></html>`
  );
  fs.writeFileSync(
    path.join(dir, "layouts", "wide.hbs"),
    `<html><body class="wide">{{{body}}}</body></html>`
  );
  fs.writeFileSync(path.join(dir, "partials", "header.hbs"), `<header>{{site.title}}</header>`);
  fs.writeFileSync(path.join(dir, "post.hbs"), `<article>{{page.frontmatter.title}}:{{{page.html}}}</article>`);
});

afterAll(() => fs.rmSync(dir, { recursive: true, force: true }));

describe("template engine", () => {
  it("renders a template inside its layout with partials", () => {
    const engine = createTemplateEngine(dir);
    const html = engine.render("post", {
      title: "T",
      site: { title: "Site" },
      page: { frontmatter: { title: "Post" }, html: "<p>hi</p>" },
    });
    expect(html).toContain("<title>T</title>");
    expect(html).toContain("<header>Site</header>");
    expect(html).toContain("<article>Post:<p>hi</p></article>");
  });

  it("supports selecting an alternate layout", () => {
    const engine = createTemplateEngine(dir);
    const html = engine.render(
      "post",
      { page: { frontmatter: { title: "P" }, html: "" } },
      "wide"
    );
    expect(html).toContain('class="wide"');
  });

  it("falls back to default layout for unknown layout names", () => {
    const engine = createTemplateEngine(dir);
    const html = engine.render(
      "post",
      { title: "X", site: {}, page: { frontmatter: { title: "P" }, html: "" } },
      "nope"
    );
    expect(html).toContain("<title>X</title>");
  });

  it("provides built-in fallbacks when template dir is empty", () => {
    const empty = fs.mkdtempSync(path.join(os.tmpdir(), "ssg-empty-"));
    const engine = createTemplateEngine(empty);
    const html = engine.render("tag", {
      tag: "ts",
      pages: [{ url: "/a/", frontmatter: { title: "A" } }],
    });
    expect(html).toContain("Tag: ts");
    expect(html).toContain('<a href="/a/">A</a>');
    fs.rmSync(empty, { recursive: true, force: true });
  });

  it("does not escape triple-stash HTML but escapes double-stash", () => {
    const engine = createTemplateEngine(dir);
    const html = engine.render("post", {
      page: { frontmatter: { title: "<b>" }, html: "<em>ok</em>" },
    });
    expect(html).toContain("&lt;b&gt;");
    expect(html).toContain("<em>ok</em>");
  });

  it("formatDate helper formats dates", () => {
    const empty = fs.mkdtempSync(path.join(os.tmpdir(), "ssg-fd-"));
    fs.writeFileSync(path.join(empty, "index.hbs"), `{{formatDate d}}|{{formatDate d "iso"}}`);
    const engine = createTemplateEngine(empty);
    const out = engine.render("index", { d: new Date("2024-01-02T03:04:05Z") });
    expect(out).toContain("2024-01-02|2024-01-02T03:04:05.000Z");
    fs.rmSync(empty, { recursive: true, force: true });
  });

  it("throws on unknown template names", () => {
    const engine = createTemplateEngine(dir);
    expect(() => engine.render("missing", {})).toThrow(/Unknown template/);
  });
});
