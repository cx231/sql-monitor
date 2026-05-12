# Login Background And Form Depth Design

## Goal

Improve the login screen visual quality by adding an IT operations themed background and increasing the hierarchy of the username, password, and captcha input area.

## Current Context

- The login screen is implemented in `frontend/src/views/LoginView.vue`.
- The page already includes username, password, captcha image, captcha refresh, error alert, and submit behavior.
- Theme variables support light and dark modes through `frontend/src/styles/theme.css`.
- The project has no current project-bound image assets for the login background.

## Visual Direction

- Use CSS-generated visual layers instead of an external raster image.
- The background should suggest SQL Server monitoring, database operations, and network observability through:
  - subtle grid lines,
  - node-like radial highlights,
  - panel silhouettes,
  - diagonal light bands.
- The background must stay restrained so the login form remains the primary focus.
- The implementation must adapt to light and dark themes using existing CSS variables.

## Layout

- Desktop: keep the login card in the first viewport, biased slightly to the right so the background scene has room to read.
- Tablet and mobile: center the login panel and reduce background complexity.
- The login panel keeps an 8px border radius to match the existing product UI.

## Form Hierarchy

- Add an inner form surface around username, password, captcha, alert, and submit controls.
- Separate the header from the form controls with spacing and a light divider-like contrast.
- The inner surface uses a muted background, border, and subtle inset/outer shadow.
- Inputs should read as a grouped authentication area while preserving Element Plus validation and autocomplete behavior.

## Behavior

- Do not change login request payloads, captcha fetching, captcha validation, or routing.
- Do not add new dependencies.
- Do not introduce external image loading.

## Testing

- Run `npm run build` to verify Vue type checking and Vite production bundling.
- Browser verify the login route at desktop and mobile widths:
  - background layers render,
  - login panel remains readable,
  - username/password/captcha controls are grouped in the inner surface,
  - captcha image and refresh remain usable,
  - no horizontal overflow.

## Out Of Scope

- Replacing the login flow.
- Adding brand illustrations, logos, or external stock photography.
- Adding a frontend testing framework.
