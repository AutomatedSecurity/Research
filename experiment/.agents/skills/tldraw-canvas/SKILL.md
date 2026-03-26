---
name: tldraw-canvas
description: >
  Interact with open tldraw desktop canvases via a local HTTP API at localhost:7236.
  Create, read, update, and delete shapes. Take screenshots. Build diagrams, flowcharts,
  wireframes, and visual layouts programmatically. Use when the user asks to draw, diagram,
  sketch, wireframe, create a visual, modify a canvas, add shapes, create a flowchart,
  create an architecture diagram, or work with tldraw. Also triggers on "draw on canvas",
  "add to canvas", "update the diagram", "show me on the canvas", or any reference to
  tldraw files (.tldr).
---

# tldraw Canvas

Local HTTP API at `http://localhost:7236` for reading and modifying open tldraw canvases.

For full shape types, actions, colors, and exec API details, read [references/api-reference.md](references/api-reference.md).

## Workflow

### 1. Find the document

```bash
# List all open docs
curl -s "http://localhost:7236/api/doc" | jq

# Filter by name
curl -s "http://localhost:7236/api/doc?name=my-file" | jq
```

Extract the `id` field for subsequent calls. If no docs are open, tell the user to open a .tldr file in tldraw desktop.

### 2. See what's on the canvas

```bash
# Screenshot (save and view with Read tool)
curl -s "http://localhost:7236/api/doc/DOC_ID/screenshot" --output /tmp/canvas.jpg

# Read all shapes as JSON
curl -s "http://localhost:7236/api/doc/DOC_ID/shapes" | jq
```

Always take a screenshot first to understand the current state before making changes.

### 3. Make changes

```bash
curl -s -X POST "http://localhost:7236/api/doc/DOC_ID/actions" \
  -H 'Content-Type: application/json' \
  -d '{"actions": [...]}'
```

All actions in one request form a single undo step. Prefer batching related changes.

### 4. Verify visually

After changes, take a screenshot to confirm correctness. Make incremental changes and verify frequently.

## Key Patterns

### Create a labeled box
```json
{"actions": [{"_type": "create", "shape": {"_type": "rectangle", "shapeId": "box1", "x": 100, "y": 100, "w": 200, "h": 80, "color": "blue", "fill": "solid", "text": "Service A", "note": ""}}]}
```

### Connect shapes with an arrow
```json
{"actions": [{"_type": "create", "shape": {"_type": "arrow", "shapeId": "arr1", "x1": 0, "y1": 0, "x2": 100, "y2": 0, "color": "black", "fromId": "box1", "toId": "box2", "text": "", "note": ""}}]}
```

Use `fromId`/`toId` to bind arrow endpoints to shapes — the arrow stays connected when shapes move.

### Position relative to another shape
```json
{"actions": [{"_type": "place", "shapeId": "box2", "referenceShapeId": "box1", "side": "right", "align": "center", "sideOffset": 40}]}
```

### Layout helpers
- **align**: Align shapes along an axis (`top`, `center-horizontal`, `bottom`, `left`, `center-vertical`, `right`)
- **distribute**: Space shapes evenly (`horizontal`, `vertical`)
- **stack**: Stack shapes with a fixed gap

### Exec API (advanced)
For operations not covered by the structured API:
```bash
curl -s -X POST "http://localhost:7236/api/doc/DOC_ID/exec" \
  -H 'Content-Type: application/json' \
  -d '{"code": "return editor.getCurrentPageShapes().length"}'
```

Note: In exec, text props use `richText` not `text`. Use `toRichText('...')` to set text.

## Tips

- Assign meaningful `shapeId` values (e.g., `"auth-service"`, `"db-arrow"`) for easy reference in updates.
- Use `place` action for relative positioning instead of computing coordinates manually.
- Batch related creates into a single request for atomicity.
- For large diagrams, use `setMyView` to navigate the viewport after placing shapes.
- Colors: red, light-red, green, light-green, blue, light-blue, orange, yellow, black, violet, light-violet, grey, white.
- Fill modes: none, tint, background, solid, pattern.
