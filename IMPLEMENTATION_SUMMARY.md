# Template Engine Implementation Summary

## What Was Added

### 1. Template Engine Module (`src/template.ts`)
- **TemplateEngine class**: Manages Handlebars template compilation and rendering
  - Loads templates from `templates/` directory
  - Loads layouts from `templates/layouts/` directory
  - Auto-registers partials from `templates/partials/` directory
  - Caches compiled templates for performance
  - Supports both `render()` for complete template/layout rendering and `renderWithLayout()` for content wrapping

- **Helper Functions**:
  - `createDefaultLayout()`: Creates default page layout with styling
  - `createDefaultIndexLayout()`: Creates default index/listing layout
  - `createDefaultNavPartial()`: Creates default navigation partial

### 2. Parser Enhancements (`src/parser.ts`)
- Extended `PageMetadata` interface to include:
  - `template?: string`: Custom template file
  - `layout?: string`: Custom layout file
- Pages can now specify templates/layouts in frontmatter

### 3. Generator Improvements (`src/generator.ts`)
- Extended `GeneratorOptions` with:
  - `templatesDir?: string` (default: `./templates`)
  - `layoutsDir?: string` (default: `./templates/layouts`)
  - `partialsDir?: string` (default: `./templates/partials`)

- **Key Features**:
  - Auto-detects if templates directory exists
  - Creates default templates if they don't exist
  - Passes all page metadata to templates for use in Handlebars expressions
  - Falls back to inline HTML generation if no templates directory (backward compatible)
  - Supports custom layouts per page via frontmatter

- **New Function**:
  - `ensureDefaultTemplates()`: Sets up default template files on first run

### 4. Comprehensive Tests
- **template.test.ts** (11 new tests):
  - Template rendering with data
  - Layout integration
  - Partial support
  - Conditional blocks
  - Loop iteration
  - Template caching
  - Error handling

- **generator.test.ts** (5 new tests):
  - Template directory detection
  - Custom layout usage
  - Default template creation
  - Metadata passing to templates

- **parser.test.ts** (4 new tests):
  - Template/layout metadata parsing
  - Validation of template and layout fields

## Backward Compatibility

✓ All 56 tests pass (including 15 original tests)
✓ Existing sites work without templates directory
✓ Falls back to inline HTML generation when templates not present
✓ No breaking changes to API

## Directory Structure Created

When templates are enabled:
```
./templates/
├── layouts/
│   ├── default.hbs (auto-created)
│   └── index.hbs (auto-created)
├── partials/
│   └── nav.hbs (auto-created)
└── index.hbs (auto-created)
```

## Features

✓ Handlebars template engine support
✓ Layout templates with body placeholder
✓ Partial includes/components
✓ Per-page custom layout specification
✓ Access to all page metadata in templates
✓ Conditional rendering (if, each blocks)
✓ Template caching for performance
✓ Default layouts with styling
✓ Auto-creation of default templates
✓ Backward compatible with non-template mode

## Usage Example

1. Create `templates/` directory
2. Generator automatically creates default templates
3. Customize templates as needed:
   - Edit `templates/layouts/default.hbs` for page styling
   - Edit `templates/partials/nav.hbs` for navigation
   - Add custom partials in `templates/partials/`
4. Specify custom layout per page (optional):
   ```markdown
   ---
   title: My Page
   layout: custom.hbs
   ---
   ```

## Test Results

```
Test Suites: 4 passed, 4 total
Tests:       56 passed, 56 total
```

All tests include:
- CLI tests (2 existing)
- Parser tests (9: 5 existing + 4 new)
- Generator tests (18: 13 existing + 5 new)
- Template tests (11: all new)
