# Design System Strategy: Precision & Tonal Depth

## 1. Overview & Creative North Star: "The Industrial Architect"
This design system moves beyond the generic "SaaS dashboard" by embracing a philosophy of **Tonal Layering**. In construction, precision is non-negotiable, and the interface must mirror that reliability. Our Creative North Star is **"The Industrial Architect"**—a digital environment that feels built, not just rendered. 

We achieve a premium, custom feel by rejecting the standard 1px grid in favor of **intentional asymmetry** and **chromatic depth**. Instead of boxing data into outlines, we use a sophisticated hierarchy of grayscale and deep blues to "carve" the interface out of the screen. The result is a high-density financial environment that feels expansive and authoritative, ensuring complex construction data remains legible and actionable.

---

## 2. Colors: The Chromatic Foundation
The palette is anchored in deep, structural tones. We prioritize semantic clarity for financial health while maintaining an understated, high-end aesthetic.

### Surface Hierarchy & The "No-Line" Rule
**Strict Mandate:** Designers are prohibited from using 1px solid borders to section off major UI areas. 
Boundaries must be defined through **background color shifts**. For example:
- A Sidebar uses `surface_container_high` (#e7e8ea).
- The Main Content Area uses `surface` (#f8f9fb).
- Individual KPI modules use `surface_container_lowest` (#ffffff).

### The "Glass & Gradient" Rule
To elevate the "Industrial" personality into "Tech-Forward," use **Glassmorphism** for floating elements (modals, dropdowns). Use a `backdrop-blur` of 12px–20px with a semi-transparent `surface_container_lowest` at 80% opacity. 
*   **Signature Textures:** For primary CTAs and financial hero sections, use a subtle linear gradient transitioning from `primary` (#000000) to `primary_container` (#101b30) at a 135-degree angle. This adds "soul" and weight to the most critical actions.

---

## 3. Typography: Editorial Authority
We utilize a dual-typeface system to balance technical precision with modern high-end editorial standards.

*   **The Display Choice (Manrope):** Used for `display` and `headline` scales. Its geometric construction feels modern and industrial. It commands attention for high-level project names and total budget figures.
*   **The Technical Choice (Inter):** Used for `title`, `body`, and `label` scales. Inter is chosen for its exceptional legibility.
*   **The Financial Rule:** All numerical data in tables and KPI cards **must** use `font-variant-numeric: tabular-nums`. This ensures that decimal points and digits align perfectly across rows, a requirement for "Financial Clarity."

---

## 4. Elevation & Depth: Tonal Layering
In this system, depth is a function of color, not just shadow. We mimic the physical stacking of blueprints and architectural materials.

*   **The Layering Principle:** Stacking follows a logical progression. A `surface_container_lowest` card sitting on a `surface_container_low` section creates a "natural lift" that feels architectural.
*   **Ambient Shadows:** If a card requires a floating state (e.g., a dragged Gantt chart item), use a shadow with a 24px blur and 6% opacity. The shadow color should be a tinted version of `on_surface` (#191c1e) to ensure it looks like a soft, ambient occlusion rather than a "drop shadow."
*   **The "Ghost Border" Fallback:** If high-density data requires containment (like complex data table headers), use a "Ghost Border": the `outline_variant` (#c4c6cc) token at **15% opacity**. Never use 100% opaque borders.

---

## 5. Components: Precision Primitives

### Data Tables & Financial Lists
*   **The No-Divider Rule:** Forbid horizontal lines between rows. Use the Spacing Scale `4` (0.9rem) to create clear vertical separation.
*   **Conditional Formatting:** Financial status should be indicated by a subtle vertical "status bar" (4px wide) on the far left of the row using semantic tokens: `error` (#ba1a1a) for over-budget or `success` (#2e7d32) for on-track.

### KPI Cards
*   **Structure:** Title in `label-md` (Inter), Value in `headline-lg` (Manrope) with tabular figures.
*   **Progress Bars:** Use a thick 8px track. The background track should be `surface_variant` (#e1e2e4) and the progress fill should be the `secondary` (#47607e) or semantic status color.

### Multi-Select Sidebar
*   **Style:** Use `surface_container_high` for the background. Active states for filters should use a `primary_container` (#101b30) background with `primary_fixed` (#d7e2ff) text. No borders; use rounded corners `md` (0.375rem).

### Input Fields
*   **Design:** Use a "filled" style rather than an outlined style. Background: `surface_container_highest` (#e1e2e4). On focus, transition the bottom 2px to `primary` (#000000).

---

## 6. Do's and Don'ts

### Do
*   **Do** use `surface_container` tiers to separate the sidebar, header, and content.
*   **Do** use whitespace (Spacing `8` to `12`) to group related financial metrics.
*   **Do** ensure all currency values are right-aligned in tables for rapid scanning.
*   **Do** apply `backdrop-blur` to any element that overlaps a chart or image.

### Don't
*   **Don't** use 1px black or gray borders to separate dashboard widgets.
*   **Don't** use standard "drop shadows" with high opacity or small blur radii.
*   **Don't** use "Inter" for large display headers; it lacks the architectural weight of "Manrope."
*   **Don't** use pure white (#ffffff) for large background areas; use `surface` (#f8f9fb) to reduce eye strain in high-density environments.