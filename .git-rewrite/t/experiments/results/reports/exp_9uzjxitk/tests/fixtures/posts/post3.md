---
title: Advanced TypeScript
date: 2024-03-10
tags:
  - typescript
  - javascript
---

## Advanced Patterns

Discussing advanced TypeScript patterns.

```typescript
type DeepReadonly<T> = {
  readonly [K in keyof T]: DeepReadonly<T[K]>;
};
```

No tags needed here.
