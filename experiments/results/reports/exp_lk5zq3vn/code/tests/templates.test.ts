import { describe, it, expect, beforeAll, afterAll } from "vitest";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { loadTemplates } from "../src/templates.js";

let dir: string;

beforeAll(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), "ssgen-tpl-"));
  fs.mkdirSync(path.join(dir, "partials"));
  fs.writeFileSync(
    path.join(dir, "default.hbs"),
    `<html><head><title>{{title}}</title></head><body>{{> header}}<main>{{{content}}}</main></body></html>`
  );
  fs.writeFileSync(path.join(dir, "post.hbs"), `<article>{{> header}}{{{content}}}<p>{{formatDate date}}</p></article>`);
  fs.writeFileSync(path.join(dir, "partials", "header.hbs"), `<header>{{title}}</header>`);
});

afterAll(() => fs.rmSync(dir, { recursive: true, force: true }));

describe("loadTemplates", () => {
  it("renders a layout with partials and triple-stash content", () => {
    const t = loadTemplates(dir);
    const html = t.renderLayout("default", { title: "Hi", content: "<p>body</p>" });
    expect(html).toContain("<title>Hi</title>");
    expect(html).toContain("<header>Hi</header>");
    expect(html).toContain("<main><p>body</p></main>"); // not escaped
  });

  it("falls back to default layout for unknown names", () => {
    const t = loadTemplates(dir);
    const html = t.renderLayout("nonexistent", { title: "X", content: "" });
    expect(html).toContain("<title>X</title>");
  });

  it("uses named layouts and the formatDate helper", () => {
    const t = loadTemplates(dir);
    const html = t.renderLayout("post", { title: "P", content: "<b>c</b>", date: new Date("2026-02-03T00:00:00Z") });
    expect(html).toContain("<b>c</b>");
    expect(html).toContain("2026-02-03");
  });

  it("escapes HTML in double-stash expressions", () => {
    const t = loadTemplates(dir);
    const html = t.renderLayout("default", { title: "<script>", content: "" });
    expect(html).toContain("&lt;script&gt;");
  });

  it("throws when no default layout exists", () => {
    const empty = fs.mkdtempSync(path.join(os.tmpdir(), "ssgen-empty-"));
    try {
      expect(() => loadTemplates(empty).renderLayout("anything", {})).toThrow(/default/);
    } finally {
      fs.rmSync(empty, { recursive: true, force: true });
    }
  });
});
