# Revisee login visual assets

Copy this folder into `frontend/public/assets/login/` (or adapt paths to the project's existing asset convention).

## Keep as files

- `revisee-logo.svg` — reusable dark wordmark with teal sparkle. Prefer real text for accessible headings; use this only where a visual logo is appropriate.
- `revisee-sparkle.svg` — small reusable brand accent.
- `login-panel-background.svg` — scalable gradient/blob backdrop for the illustration panel.
- `login-knowledge-illustration.png` — transparent notebook and generic knowledge-card composition. Use decorative `alt=""`.

## Do not store as image assets

- Particles: draw with the `KnowledgeParticles` canvas component.
- Orbital paths: draw on the same canvas so they move naturally.
- `Learn. Review. Remember.`: render as HTML so it remains crisp and responsive.
- Login headings, labels, inputs and buttons: real HTML only.

## Recommended layer order

1. CSS/SVG panel background
2. Canvas particles and orbital paths
3. Transparent notebook illustration
4. HTML headline
5. Login form panel

## Suggested HTML

```html
<section class="login-visual" aria-hidden="true">
  <img class="login-visual__background" src="assets/login/login-panel-background.svg" alt="">
  <app-knowledge-particles />
  <img class="login-visual__illustration" src="assets/login/login-knowledge-illustration.png" alt="">
  <p class="login-visual__message">
    <span>Learn. Review.</span>
    <strong>Remember.</strong>
  </p>
</section>
```

The canvas should respect `prefers-reduced-motion`, pause while the document is hidden, scale for device pixel ratio, and be removed or simplified on mobile.
