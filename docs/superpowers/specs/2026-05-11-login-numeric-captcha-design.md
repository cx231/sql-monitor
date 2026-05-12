# Login Numeric Captcha Design

## Goal

Add a server-generated 6-digit numeric captcha to the login flow.

## Scope

This change covers:

1. Add `GET /api/auth/captcha` to generate a 6-digit code.
2. Return a signed, expiring `captcha_token` and an SVG data URL that displays the code.
3. Require `captcha_token` and `captcha_code` in `POST /api/auth/login`.
4. Validate captcha before username/password authentication.
5. Add a captcha field and refresh action to the login page.

This change does not add a database table, Redis, rate limiting, Geetest, SMS, or email verification.

## Backend Design

The backend creates a 6-digit numeric code with `secrets.randbelow(1_000_000)`, zero-padded to length 6.

The captcha token is a JWT signed by the existing `SQLMON_SECRET_KEY`. It contains:

```text
type: captcha
captcha_hash: sha256(code + ":" + nonce + ":" + secret_key)
nonce: random hex string
exp: now + 5 minutes
```

The token does not include the raw code. Validation decodes the token, verifies `type == captcha`, checks expiration through JWT, and compares the hash with the user-provided code.

The SVG is returned as a `data:image/svg+xml;base64,...` URL. It is intentionally simple and dependency-free.

## Frontend Design

The login page adds a compact captcha row:

1. Left: input field, placeholder `请输入6位验证码`.
2. Right: clickable captcha image.
3. Below or beside: `换一张` button.

The page fetches a captcha on mount. It refreshes the captcha after login failure and when the user clicks the image or refresh button.

## Error Handling

1. Missing or invalid captcha returns 400 with `验证码错误或已过期`.
2. Wrong username/password still returns 401 with `用户名或密码错误`.
3. Frontend displays `验证码错误或已过期` separately from account/password failure.

## Testing

Backend tests cover:

1. Code generation is 6 digits.
2. Captcha token verifies the correct code.
3. Captcha token rejects wrong code.
4. Login route rejects missing or invalid captcha before authentication.
5. Login route accepts valid captcha and valid credentials.

Frontend verification covers:

1. Production build succeeds.
2. Login page renders the captcha image and input.
3. Refresh action changes the captcha token/image.
