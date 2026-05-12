# Login Numeric Captcha Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require a server-generated 6-digit numeric captcha during login.

**Architecture:** Add a dependency-free captcha service that signs captcha challenges as short-lived JWTs. The auth route exposes captcha generation and verifies captcha before password authentication. The login page fetches and displays the SVG captcha and submits the token/code with credentials.

**Tech Stack:** FastAPI, PyJWT, Vue 3, Pinia, Element Plus.

---

### Task 1: Backend Captcha Service

**Files:**
- Create: `backend/app/services/captcha_service.py`
- Modify: `backend/tests/unit/test_auth_service.py`

- [ ] **Step 1: Write failing tests**

Add tests for 6-digit generation, correct-code verification, wrong-code rejection, and malformed token rejection.

Run: `cd backend && python3 -m pytest tests/unit/test_auth_service.py -q`
Expected: FAIL because `app.services.captcha_service` does not exist.

- [ ] **Step 2: Implement service**

Create `CaptchaChallenge`, `create_captcha_challenge`, `verify_captcha`, and SVG rendering helpers.

- [ ] **Step 3: Verify service tests**

Run: `cd backend && python3 -m pytest tests/unit/test_auth_service.py -q`
Expected: PASS for captcha service tests.

### Task 2: Backend Auth Route Integration

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/api/routes/auth.py`
- Modify: `backend/tests/unit/test_auth_service.py`

- [ ] **Step 1: Write failing route tests**

Add tests for `GET /api/auth/captcha`, login without captcha returning 400, login with wrong captcha returning 400, and login with valid captcha/credentials returning 200.

- [ ] **Step 2: Implement route and schema changes**

Add `CaptchaResponse`, add `captcha_token` and `captcha_code` to `LoginRequest`, add `GET /captcha`, and call `verify_captcha` before `authenticate_user`.

- [ ] **Step 3: Verify auth tests**

Run: `cd backend && python3 -m pytest tests/unit/test_auth_service.py -q`
Expected: PASS.

### Task 3: Frontend Login UI

**Files:**
- Modify: `frontend/src/stores/auth.ts`
- Modify: `frontend/src/views/LoginView.vue`

- [ ] **Step 1: Add auth store captcha API**

Add `fetchCaptcha()` returning `{ captcha_token, image_data_url, expires_in_seconds }`. Extend `LoginPayload` with captcha fields.

- [ ] **Step 2: Add login page captcha controls**

Fetch captcha on mount, render input + image + refresh button, validate 6 digits, submit token/code, refresh captcha on failure.

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: PASS.

### Task 4: Full Verification

**Files:**
- No new source edits expected.

- [ ] **Step 1: Run backend tests**

Run: `cd backend && python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 3: Browser inspect login page**

Open `/login`, confirm captcha image, 6-digit input, and refresh action render in light/dark themes without horizontal overflow.
