# Stack Knowledge Conformance

This review classifies the 12 distilled stack skills against their maintained implementation
surfaces. `repo-conformant` claims describe observable local behavior and carry source anchors.
`generic-guidance` claims remain useful external guidance, but they are not a framework practice.

| Subject | Conformance | Anchors | Claim edits |
| --- | --- | --- | --- |
| `skill/stack/chroma` | repo-conformant | `src/agentic_dynamics/knowledge/embeddings.py:233`, `src/agentic_dynamics/knowledge/retrieval.py:1764` | Replaced general Chroma result-shape, pagination, and document-filter advice with the local query, ID inventory, and hard scope-filter behavior. |
| `skill/stack/systemd` | generic-guidance | `infrastructure/agentic-dynamics-launch-broker.service:67`, `infrastructure/docs-drift-scan.service:42`, `infrastructure/fleet-bootstrap.service:17` | Retained lifecycle guidance but removed the implication that all current daemons configure stop and start-limit settings. |
| `skill/stack/web-svg-css` | repo-conformant | `apps/control_room/static/app.js:265`, `apps/control_room/static/app.js:299`, `apps/website/verify_svg_rendering.py:64` | Reduced the accessibility claim to the ARIA patterns and 4.5:1 text-contrast gate actually enforced. |
| `skill/stack/neo4j-cypher` | repo-conformant | `src/agentic_dynamics/knowledge/graph.py:135`, `src/agentic_dynamics/knowledge/graph.py:167`, `src/agentic_dynamics/knowledge/graph.py:1391` | Replaced broad Cypher style advice with parameterization, identifier validation, ACL traversal, and commit filtering contracts. |
| `skill/stack/celery-redis` | generic-guidance | `src/agentic_dynamics/runtime/story/builtins.py:76` | Marked Celery guidance as applicable to generated or user applications only; the framework has no maintained Celery task system. |
| `skill/stack/flask` | repo-conformant | `apps/control_room/server.py:35`, `apps/control_room/server.py:119`, `apps/control_room/server.py:197` | Corrected the application-factory and Blueprint claim to the module-global Control Room app and explicit route-registration seam. |
| `skill/stack/sqlite` | repo-conformant | `src/agentic_dynamics/control/control_db.py:1213`, `src/agentic_dynamics/control/control_db.py:1231`, `src/agentic_dynamics/control/control_db.py:1251`, `src/agentic_dynamics/control/control_db.py:1255` | Kept the configured WAL, timeout, and read-only contracts; removed unverified checkpoint and filesystem practices. |
| `skill/stack/python` | repo-conformant | `pyproject.toml:5`, `pyproject.toml:60`, `src/agentic_dynamics/knowledge/retrieval.py:1447` | Kept the interpreter, Ruff configuration, and observed retrieval executor; removed a repository-wide ProcessPoolExecutor policy. |
| `skill/stack/docker-compose` | repo-conformant | `infrastructure/docker-compose.ladder.yml:3`, `infrastructure/docker-compose.ladder.yml:31`, `infrastructure/docker-compose.ladder.yml:398`, `infrastructure/docker-compose.ladder.yml:447` | Replaced general Docker DNS/default-bridge assertions with the fleet network, named endpoints, Redis isolation, and loopback exposure contract. |
| `skill/stack/playwright` | repo-conformant | `apps/website/verify_svg_rendering.py:431`, `apps/website/verify_svg_rendering.py:441`, `apps/website/verify_svg_rendering.py:561` | Corrected pytest-playwright fixture guidance to the direct async_playwright harness and its explicit 700ms settle delay. |
| `skill/stack/firebase-hosting` | repo-conformant | `apps/website/firebase.json:1`, `apps/website/firebase.json:32`, `apps/website/.firebaserc:1`, `apps/website/CONTEXT.md:47` | Replaced general priority and preview-channel guidance with the local hosting root, redirects, aliases, and dual deployment requirement. |
| `skill/stack/redis-streams` | repo-conformant | `src/agentic_dynamics/knowledge/knowledge_stream.py:198`, `src/agentic_dynamics/knowledge/knowledge_stream.py:299`, `src/agentic_dynamics/knowledge/knowledge_stream.py:314`, `src/agentic_dynamics/knowledge/knowledge_stream.py:465`, `src/agentic_dynamics/control/projection_watermarks.py:223` | Corrected group creation from `$` to `id="0"` and removed the unsupported assertion that the publisher trims streams. |

The claim changes deliberately prefer narrow statements tied to the cited code. This keeps a
skill from converting vendor documentation into an unverified local convention.
