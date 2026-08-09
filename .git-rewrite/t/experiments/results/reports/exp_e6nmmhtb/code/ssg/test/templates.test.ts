import { describe, it, expect, beforeAll } from "vitest";
import { loadTemplates, renderString, renderPage } from "../src/templates.js";
import { parseMarkdown } from "../src/markdown.js";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { BuildContext } from "../src/types.js";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const fixtureTemplates = resolve(__dirname, "fixtures/templates");

const mockContext: BuildContext = {
  pages: [],
  tags: new Map(),
  config: {
    title: "Test Site",
    description: "A test",
    baseUrl: "http://localhost:3000",
    language: "en",
  },
  startTime: new Date(),
};

describe("templates", () => {
  beforeAll(async () => {
    await loadTemplates(fixtureTemplates);
  });

  it("renders a simple template", () => {
    const result = renderString("Hello {{name}}!", { name: "World" });
    expect(result).toBe("Hello World!");
  });

  it("formats dates with the formatDate helper", () => {
    const result = renderString("{{formatDate date}}", {
      date: "2025-03-15",
    });
    expect(result).toBe("2025-03-15");
  });

  it("handles missing dates gracefully", () => {
    const result = renderString("{{formatDate date}}", { date: null });
    expect(result).toBe("");
  });

  it("eq helper returns true for equal values", () => {
    const result = renderString("{{#if (eq a b)}}yes{{else}}no{{/if}}", {
      a: "foo",
      b: "foo",
    });
    expect(result).toBe("yes");
  });

  it("eq helper returns false for different values", () => {
    const result = renderString("{{#if (eq a b)}}yes{{else}}no{{/if}}", {
      a: "foo",
      b: "bar",
    });
    expect(result).toBe("no");
  });

  it("renders a page using the post template", () => {
    const raw = `---
title: Template Test
date: 2025-02-20
tags:
  - test
---

Post content.
`;
    const page = parseMarkdown(raw, "posts/template-test.md");
    const html = renderPage(page, mockContext);

    expect(html).toContain("Template Test");
    expect(html).toContain("Test Site");
    expect(html).toContain("<article>");
  });

  it("renders a page with the layout wrapping", () => {
    const raw = `---
title: With Layout
---

Layout content.
`;
    const page = parseMarkdown(raw, "posts/layout-test.md");
    const html = renderPage(page, mockContext);

    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain("<main>");
    expect(html).toContain("With Layout");
    expect(html).toContain("Test Site");
  });
});
