import { describe, it, expect } from "vitest";
import { slugify, pathToUrl, formatDate, parseDate } from "../src/utils.js";

describe("utils", () => {
  describe("slugify", () => {
    it("converts text to lowercase slug", () => {
      expect(slugify("Hello World")).toBe("hello-world");
    });

    it("removes special characters", () => {
      expect(slugify("Foo & Bar!")).toBe("foo-bar");
    });

    it("trims dashes from edges", () => {
      expect(slugify("--hello--")).toBe("hello");
    });
  });

  describe("pathToUrl", () => {
    it("converts file paths to clean URLs", () => {
      expect(pathToUrl("/src/posts/hello.md", "/src")).toBe("/hello/");
    });

    it("handles index.md as root", () => {
      expect(pathToUrl("/src/index.md", "/src")).toBe("/");
    });
  });

  describe("formatDate", () => {
    it("formats date as YYYY-MM-DD", () => {
      expect(formatDate(new Date("2024-01-15"))).toBe("2024-01-15");
    });
  });

  describe("parseDate", () => {
    it("parses valid date strings", () => {
      const d = parseDate("2024-01-15");
      expect(d.getFullYear()).toBe(2024);
    });

    it("throws on invalid date", () => {
      expect(() => parseDate("not a date")).toThrow("Invalid date");
    });
  });
});
