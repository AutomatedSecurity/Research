# tldraw Canvas API Reference

Base URL: `http://localhost:7236`

## Document Endpoints

### GET /api/doc
List open documents. Filter with `?name=<substring>` (case-insensitive).

Response:
```json
{"docs": [{"id": "abc123", "filePath": "/path/to/file.tldr", "name": "file", "unsavedChanges": false, "windowId": 1, "shapeCount": 12, "pageCount": 1}]}
```

### GET /api/doc/:id/screenshot
Capture canvas as JPEG. Query params:
- `size`: `small` (768px, default), `medium` (1536px), `large` (3072px), `full` (5000px)
- `bounds`: `x,y,w,h` in page coords

Headers: `X-Image-Width`, `X-Image-Height`, `X-Page-Name`, `X-Viewport-Bounds`, `X-Capture-Bounds`, `X-Canvas-Empty`.

### GET /api/doc/:id/shapes
All shapes on current page. Response includes `page`, `viewport`, and `shapes` array.

### POST /api/doc/:id/actions
Execute actions (batched as one undo step). Body: `{"actions": [...]}`.

### POST /api/doc/:id/exec
Run arbitrary JS against the tldraw Editor. Body: `{"code": "return ..."}`.
Response: `{"success": true, "result": ...}` or `{"success": false, "error": "..."}`.

### GET /api/llms
Full tldraw SDK documentation (for advanced exec API usage).

---

## Shape Types

### Geo shapes
`_type`: `rectangle`, `ellipse`, `triangle`, `diamond`, `hexagon`, `pill`, `cloud`, `star`, `heart`, `pentagon`, `octagon`, `x-box`, `check-box`, `trapezoid`, `parallelogram-right`, `parallelogram-left`, `fat-arrow-right`, `fat-arrow-left`, `fat-arrow-up`, `fat-arrow-down`

```json
{"_type": "rectangle", "shapeId": "id", "x": 0, "y": 0, "w": 200, "h": 150, "color": "blue", "fill": "solid", "text": "Label", "note": "", "textAlign": "middle"}
```

### Text
```json
{"_type": "text", "shapeId": "id", "x": 0, "y": 0, "anchor": "top-center", "color": "black", "fontSize": null, "maxWidth": null, "text": "Hello", "note": ""}
```
Anchor: top-left, top-center, top-right, center-left, center, center-right, bottom-left, bottom-center, bottom-right

### Arrow
```json
{"_type": "arrow", "shapeId": "id", "x1": 0, "y1": 0, "x2": 200, "y2": 100, "color": "black", "fromId": "box1", "toId": "box2", "bend": 0, "text": "", "note": ""}
```
Use `fromId`/`toId` to bind arrow endpoints to shapes.

### Line
```json
{"_type": "line", "shapeId": "id", "x1": 0, "y1": 0, "x2": 200, "y2": 100, "color": "black", "note": ""}
```

### Note (sticky note)
```json
{"_type": "note", "shapeId": "id", "x": 0, "y": 0, "color": "yellow", "text": "Content", "note": ""}
```

### Read-only types
- **Pen/Draw**: `{"_type": "pen", "shapeId": "id", "color": "red", "fill": "none", "note": ""}`
- **Image**: `{"_type": "image", "shapeId": "id", "x": 0, "y": 0, "w": 100, "h": 100, "altText": "", "note": ""}`
- **Unknown**: `{"_type": "unknown", "shapeId": "id", "subType": "...", "x": 0, "y": 0, "note": ""}`

### Colors
red, light-red, green, light-green, blue, light-blue, orange, yellow, black, violet, light-violet, grey, white

### Fill modes
none, tint, background, solid, pattern

---

## Actions

### create
```json
{"_type": "create", "shape": {"_type": "rectangle", "shapeId": "box1", "x": 100, "y": 100, "w": 200, "h": 150, "color": "blue", "fill": "solid", "text": "", "note": ""}}
```

### update
Provide `shapeId` + `_type` + only changed properties:
```json
{"_type": "update", "shape": {"_type": "rectangle", "shapeId": "box1", "color": "red", "text": "Updated"}}
```

### delete
```json
{"_type": "delete", "shapeId": "box1"}
```

### clear
Delete all shapes on current page:
```json
{"_type": "clear"}
```

### move
Move to absolute position:
```json
{"_type": "move", "shapeId": "box1", "x": 300, "y": 200, "anchor": "center"}
```
Anchor: top-left (default), top-center, top-right, center-left, center, center-right, bottom-left, bottom-center, bottom-right

### place
Position relative to another shape:
```json
{"_type": "place", "shapeId": "box2", "referenceShapeId": "box1", "side": "right", "align": "center", "sideOffset": 20, "alignOffset": 0}
```
Side: top, bottom, left, right. Align: start, center, end.

### label
```json
{"_type": "label", "shapeId": "box1", "text": "New label"}
```

### align
```json
{"_type": "align", "shapeIds": ["box1", "box2", "box3"], "alignment": "center-horizontal"}
```
Alignment: top, center-vertical, bottom, left, center-horizontal, right

### distribute
```json
{"_type": "distribute", "shapeIds": ["a", "b", "c"], "direction": "horizontal"}
```

### stack
```json
{"_type": "stack", "shapeIds": ["a", "b", "c"], "direction": "vertical", "gap": 20}
```

### bringToFront / sendToBack
```json
{"_type": "bringToFront", "shapeIds": ["box1"]}
{"_type": "sendToBack", "shapeIds": ["box1"]}
```

### resize
```json
{"_type": "resize", "shapeIds": ["box1"], "scaleX": 2, "scaleY": 1.5, "originX": 100, "originY": 100}
```

### rotate
```json
{"_type": "rotate", "shapeIds": ["box1"], "degrees": 45, "originX": 200, "originY": 200}
```

### pen
```json
{"_type": "pen", "shapeId": "path1", "points": [{"x":100,"y":100},{"x":150,"y":80}], "color": "red", "style": "smooth", "closed": false, "fill": "none"}
```
Style: smooth, straight. Closed: true connects last→first.

### setMyView
```json
{"_type": "setMyView", "x": 0, "y": 0, "w": 1000, "h": 800}
```

---

## Exec API Helpers

Available in exec code scope:
- `editor` — tldraw Editor instance
- `toRichText(plainText)` — convert string to TLRichText
- `renderPlaintextFromRichText(editor, richText)` — extract plain text
- `createShapeId(id?)` — create TLShapeId
- `createBindingId(id?)` — create TLBindingId
- `createArrowBetweenShapes(fromId, toId, opts?)` — bound arrow. Options: `{bend?, arrowheadStart?, arrowheadEnd?, richText?}`
- `Box`, `Vec`, `Mat` — geometry classes
- `clamp(n, min, max)`, `degreesToRadians()`, `radiansToDegrees()`
- `getDefaultColorTheme(opts)`, `getArrowBindings(editor, arrow)`, `fitFrameToContent(editor, frameId, opts?)`

Key Editor methods:
- `editor.getCurrentPageShapes()` → TLShape[]
- `editor.getShape(id)` → TLShape
- `editor.getShapePageBounds(id)` → Box
- `editor.createShape({type, x, y, props})`
- `editor.updateShape({id, type, ...})`
- `editor.deleteShape(id)`
- `editor.getPages()` / `editor.setCurrentPage(pageId)` / `editor.createPage({name})`
- `editor.zoomToFit()` / `editor.zoomToSelection()` / `editor.centerOnPoint(point)`
- `editor.groupShapes(ids)` / `editor.ungroupShapes(ids)`
- `editor.undo()` / `editor.redo()`

Note: In exec, text props use `richText` not `text`. Use `toRichText('...')` to set, `renderPlaintextFromRichText(editor, shape.props.richText)` to read.
