# Template Engine Implementation Summary

## Overview

Added complete Handlebars template engine support with layouts and partials to the static site generator. All changes maintain full backward compatibility.

## Files Created

### 1. `src/template-engine.ts` (130 lines)
Core template engine implementation with:
- **TemplateEngine class** - Main template processor
  - Constructor accepts templateDir path
  - Auto-discovers and registers partials from `templates/partials/`
  - Caches compiled templates and layouts for performance
  
- **Public Methods**:
  - `renderPage(page, templateName?, layoutName?)` - Render page with optional template/layout
  - `hasTemplate(name)` - Check if template exists
  - `hasLayout(name)` - Check if layout exists

- **Key Features**:
  - Handlebars.js support for templates
  - Triple-brace `{{{body}}}` syntax for raw HTML
  - Double-brace `{{var}}` syntax for escaped HTML
  - Conditional and loop support via Handlebars helpers
  - Partial includes via `{{> partialName}}`
  - Error handling for missing templates

### 2. `src/__tests__/template-engine.test.ts` (403 lines)
Comprehensive test suite with 19 test cases covering:
- Basic rendering without templates
- Template rendering with variables
- Layout wrapping with body placeholder
- Partial includes (header, footer, nav)
- Multiple partials in single layout
- Template caching verification
- Handlebars conditionals (if/else)
- Handlebars loops (each)
- Safe HTML rendering (escaped vs raw)
- Error handling for missing templates/layouts
- Edge cases (partials dir not existing)

### 3. `TEMPLATE_ENGINE_GUIDE.md` (180+ lines)
Complete user documentation including:
- Directory structure overview
- CLI usage examples
- Template syntax reference
- Available variables in templates
- Example templates, layouts, and partials
- API reference
- Troubleshooting guide

### 4. `.example-templates/` Directory
Reference implementation with:
- `templates/post.hbs` - Example post template
- `templates/layouts/blog.hbs` - Example blog layout
- `templates/partials/header.hbs` - Example header partial
- `templates/partials/footer.hbs` - Example footer partial

## Files Modified

### 1. `src/parser.ts`
**Changes**: Added two new optional fields to PageFrontmatter interface
```typescript
interface PageFrontmatter {
  template?: string;  // NEW
  layout?: string;    // NEW
  // ... existing fields
}
```
**Impact**: Pages can now specify template/layout in frontmatter
**Backward Compatibility**: ✅ Fully backward compatible (optional fields)

### 2. `src/generator.ts`
**Changes**: 
- Updated `generatePageHTML` to accept optional `TemplateEngine` parameter
- Moved existing HTML generation to `generatePageHTMLDefault` function
- Added template/layout rendering logic

```typescript
export function generatePageHTML(
  page: ParsedPage, 
  templateEngine?: TemplateEngine
): string {
  if (templateEngine) {
    return templateEngine.renderPage(page, templateName, layoutName);
  }
  return generatePageHTMLDefault(page);  // Original behavior
}
```
**Impact**: Optional template support, fallback to default if not provided
**Backward Compatibility**: ✅ Fully backward compatible (optional parameter)

### 3. `src/cli.ts`
**Changes**:
- Added `templates?: string` to CliOptions interface
- Added `--templates` command-line argument parsing
- Create TemplateEngine if templates directory exists
- Pass template engine to generatePageHTML

**New Usage**:
```bash
npx ssg build --templates ./templates
```
**Backward Compatibility**: ✅ Fully backward compatible (optional argument)

### 4. `package.json`
**Changes**: Added dependencies
```json
{
  "dependencies": {
    "handlebars": "^4.7.8"
  },
  "devDependencies": {
    "@types/handlebars": "^4.1.0"
  }
}
```

### 5. `README.md`
**Changes**: Updated with:
- New template features in feature list
- Template usage examples
- Updated project structure
- Documentation links to TEMPLATE_ENGINE_GUIDE.md
- Template, layout, and partial examples

## Architecture

```
Markdown Input (.md with YAML frontmatter)
    ↓
Parser (parseMarkdown)
    ↓
ParsedPage {frontmatter, html, slug}
    ↓
Generator (generatePageHTML)
    ├─ If templateEngine provided:
    │   ├─ Extract template/layout names from frontmatter
    │   ├─ Load and compile template
    │   ├─ Render content with template
    │   ├─ If layout specified, wrap with layout
    │   └─ Return final HTML
    └─ Else:
        └─ Return default HTML generation
    ↓
HTML Output (.html)
```

## Test Coverage

**Total: 39 tests, all passing**

### Breakdown:
- **Parser Tests**: 6 tests
  - Markdown parsing
  - Frontmatter extraction
  - Default values
  - Custom properties

- **Generator Tests**: 10 tests
  - Page HTML generation
  - Index generation
  - Date sorting
  - XSS prevention
  - Error handling

- **CLI Tests**: 4 tests
  - Build process
  - Directory handling
  - File generation

- **Template Engine Tests**: 19 tests
  - Template rendering
  - Layout wrapping
  - Partial includes
  - Caching
  - Handlebars expressions
  - Error handling
  - Edge cases

## Features Implemented

✅ **Handlebars Template Support**
- Full .hbs file support
- Template caching for performance
- Variables accessible from frontmatter
- Conditional expressions (if/else/unless)
- Loop expressions (each)
- Nested helpers

✅ **Layout Support**
- Layout templates with {{{body}}} placeholder
- Separate templates/layouts/ directory
- Layouts wrap template output
- Multiple layouts supported

✅ **Partial Support**
- Partial templates in templates/partials/
- Auto-discovery and registration
- Include syntax: {{> partialName}}
- Used in layouts and templates
- Support for header, footer, nav partials

✅ **Security**
- HTML escaping with double braces {{}}
- Raw HTML only with triple braces {{{}}}
- XSS prevention maintained

✅ **Backward Compatibility**
- Works without templates (default behavior)
- Optional parameters throughout
- No breaking changes to existing API
- All existing tests continue to pass

✅ **Frontmatter Integration**
- template field specifies which template to use
- layout field specifies which layout to use
- Both optional - pages work without them
- All frontmatter properties available in templates

## Directory Structure Support

```
project/
├── src/
│   ├── cli.ts
│   ├── parser.ts
│   ├── generator.ts
│   ├── template-engine.ts
│   └── __tests__/
│       ├── parser.test.ts
│       ├── generator.test.ts
│       ├── cli.test.ts
│       └── template-engine.test.ts
├── templates/           # NEW
│   ├── post.hbs
│   ├── page.hbs
│   ├── layouts/        # NEW
│   │   ├── default.hbs
│   │   └── blog.hbs
│   └── partials/       # NEW
│       ├── header.hbs
│       ├── footer.hbs
│       └── nav.hbs
├── content/
│   └── *.md
└── dist/
    └── *.html
```

## Usage Example

### 1. Create template
```handlebars
<!-- templates/post.hbs -->
<article>
  <h1>{{title}}</h1>
  {{{body}}}
</article>
```

### 2. Create layout
```handlebars
<!-- templates/layouts/blog.hbs -->
<!DOCTYPE html>
<html>
  <body>{{> header}}{{{body}}}{{> footer}}</body>
</html>
```

### 3. Create partial
```handlebars
<!-- templates/partials/header.hbs -->
<header><h1>My Blog</h1></header>
```

### 4. Create content
```markdown
---
title: My Post
template: post
layout: blog
---

# Content

Post content here...
```

### 5. Build
```bash
npm run build
npx ssg build --templates ./templates
```

## Error Handling

- ✅ Clear error message if template file not found
- ✅ Clear error message if layout file not found
- ✅ Graceful fallback if templates directory doesn't exist
- ✅ Graceful fallback if partials directory doesn't exist
- ✅ Proper TypeScript type checking

## Performance

- ✅ Template compilation cached in memory
- ✅ Layout compilation cached in memory
- ✅ Partials registered once at engine init
- ✅ No recompilation of unchanged templates

## Code Quality

- ✅ TypeScript strict mode enabled
- ✅ Full type safety
- ✅ No any types (except in data spread)
- ✅ Proper error handling
- ✅ Clear separation of concerns
- ✅ Comprehensive comments for complex logic
- ✅ Follows existing code style

## Next Steps (Optional Future Enhancements)

- EJS template engine support
- Custom Handlebars helpers
- Template inheritance
- Conditional partials
- Environment variables in templates
- Template hot reload for development
