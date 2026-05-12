# Login Background And Form Depth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a SQL monitoring themed login background and make the username/password/captcha control area visually layered.

**Architecture:** Keep the change scoped to `LoginView.vue`. Use semantic wrapper elements for the background scene and inner form surface, and CSS pseudo-elements/layers for the background image effect so no new asset pipeline or dependency is required.

**Tech Stack:** Vue 3 SFC, Element Plus, existing CSS theme variables, Vite build verification, browser visual verification.

---

### Task 1: Establish Baseline

**Files:**
- Verify: `frontend/src/views/LoginView.vue`

- [ ] **Step 1: Run the frontend build before editing**

Run: `cd frontend && npm run build`

Expected: build passes, with only existing Vite warnings about Rollup PURE comments or chunk size.

### Task 2: Add Login Scene And Form Surface Markup

**Files:**
- Modify: `frontend/src/views/LoginView.vue`

- [ ] **Step 1: Add background scene elements**

Inside `<main class="login-view">`, add a decorative background layer before the panel:

```vue
<div class="login-view__scene" aria-hidden="true">
  <div class="login-view__grid"></div>
  <div class="login-view__node login-view__node--primary"></div>
  <div class="login-view__node login-view__node--secondary"></div>
  <div class="login-view__panel login-view__panel--top"></div>
  <div class="login-view__panel login-view__panel--bottom"></div>
</div>
```

- [ ] **Step 2: Wrap form controls in an inner surface**

Keep the header outside. Wrap the `el-form` in:

```vue
<div class="login-panel__form-surface">
  <el-form ...>
    ...
  </el-form>
</div>
```

Expected: login logic is unchanged.

- [ ] **Step 3: Run build**

Run: `cd frontend && npm run build`

Expected: build passes.

### Task 3: Add Themed Background And Depth CSS

**Files:**
- Modify: `frontend/src/views/LoginView.vue`

- [ ] **Step 1: Update page layout styles**

Use fixed-format layers:

```css
.login-view {
  position: relative;
  min-height: 100vh;
  display: grid;
  place-items: center end;
  padding: 48px clamp(24px, 8vw, 112px);
  overflow: hidden;
  background:
    radial-gradient(circle at 18% 18%, color-mix(in srgb, var(--app-info) 18%, transparent), transparent 28%),
    radial-gradient(circle at 78% 76%, color-mix(in srgb, var(--app-primary) 16%, transparent), transparent 30%),
    linear-gradient(135deg, var(--app-bg), var(--app-surface-muted));
}
```

- [ ] **Step 2: Add scene layer styles**

Add `.login-view__scene`, grid, nodes, and panel silhouettes using CSS gradients and borders. Keep all layers `pointer-events: none`.

- [ ] **Step 3: Add form depth styles**

Add:

```css
.login-panel {
  position: relative;
  z-index: 1;
  width: min(430px, 100%);
  padding: 30px;
  background: color-mix(in srgb, var(--app-surface) 94%, transparent);
  border: 1px solid color-mix(in srgb, var(--app-divider) 86%, transparent);
  border-radius: 8px;
  box-shadow: 0 24px 72px rgb(2 6 23 / 18%), var(--app-shadow);
  backdrop-filter: blur(14px);
}

.login-panel__form-surface {
  padding: 18px;
  background: color-mix(in srgb, var(--app-surface-muted) 74%, var(--app-surface));
  border: 1px solid var(--app-divider);
  border-radius: 8px;
  box-shadow: inset 0 1px 0 rgb(255 255 255 / 28%);
}
```

Tune dark mode through existing variables, not separate hardcoded theme classes.

- [ ] **Step 4: Add responsive rules**

At `max-width: 760px`, center the panel, reduce padding, and hide the two panel silhouette blocks if they crowd the viewport.

- [ ] **Step 5: Run build**

Run: `cd frontend && npm run build`

Expected: build passes.

### Task 4: Browser Verification

**Files:**
- No code changes unless verification exposes visual bugs.

- [ ] **Step 1: Start Vite**

Run: `cd frontend && npm run dev -- --host 127.0.0.1 --port 5173`

- [ ] **Step 2: Verify desktop**

Open `/login` and verify:

- background scene is visible,
- login panel is readable,
- input controls are inside the inner form surface,
- captcha image renders and refresh link remains visible,
- no horizontal overflow.

- [ ] **Step 3: Verify mobile**

Set viewport around `390x844` and verify:

- panel fits the viewport,
- background does not obscure text,
- no horizontal overflow,
- captcha row stacks correctly as before.

- [ ] **Step 4: Stop Vite**

Stop the dev server.

### Task 5: Final Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run whitespace check**

Run: `git diff --check`

Expected: no output.

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`

Expected: build passes with only existing Vite warnings.

- [ ] **Step 3: Run backend tests**

Run: `cd backend && python3 -m pytest -q`

Expected: existing backend suite passes.

- [ ] **Step 4: Review status**

Run: `git status --short`

Expected: this task's intended `LoginView.vue` and docs changes are present alongside previous uncommitted requested work.
