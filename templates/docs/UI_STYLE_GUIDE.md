<!-- Template Version: 1.1.0 -->
# UI_STYLE_GUIDE.md

> **TEMPLATE_INTENT:** Document UI design patterns, component styles, and visual guidelines. The reference for consistent user interface implementation.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

## Design System

### Colors

| Name | Value | Usage |
|------|-------|-------|
| Primary | `#3B82F6` | Buttons, links, accents |
| Secondary | `#6B7280` | Secondary text, borders |
| Success | `#10B981` | Success states, confirmations |
| Warning | `#F59E0B` | Warnings, cautions |
| Error | `#EF4444` | Errors, destructive actions |
| Background | `#FFFFFF` | Page background |
| Surface | `#F9FAFB` | Card backgrounds, elevated surfaces |

### Typography

| Element | Font | Size | Weight |
|---------|------|------|--------|
| H1 | System | 2.25rem | 700 |
| H2 | System | 1.875rem | 600 |
| H3 | System | 1.5rem | 600 |
| Body | System | 1rem | 400 |
| Small | System | 0.875rem | 400 |
| Code | Monospace | 0.875rem | 400 |

---

## Spacing

Use consistent spacing scale:

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Tight spacing, icon gaps |
| sm | 8px | Related elements |
| md | 16px | Default spacing |
| lg | 24px | Section gaps |
| xl | 32px | Major sections |
| 2xl | 48px | Page sections |

---

## Components

### Buttons

**Variants:**
- **Primary:** Filled background, white text. Main actions.
- **Secondary:** Outlined, primary color. Secondary actions.
- **Ghost:** No background, text only. Tertiary actions.
- **Destructive:** Red variant for delete/remove actions.

**States:**
- Default, Hover, Active, Disabled, Loading

**Sizes:**
- sm (32px height), md (40px height), lg (48px height)

### Forms

**Input fields:**
- Border radius: 6px
- Border: 1px solid gray-300
- Focus: 2px primary ring
- Error: Red border + error message below

**Labels:**
- Position: Above input
- Required indicator: Red asterisk

### Cards

- Background: Surface color
- Border radius: 8px
- Shadow: sm (subtle elevation)
- Padding: md (16px)

---

## Layout

### Breakpoints

| Name | Width | Usage |
|------|-------|-------|
| sm | 640px | Mobile landscape |
| md | 768px | Tablets |
| lg | 1024px | Small laptops |
| xl | 1280px | Desktops |
| 2xl | 1536px | Large screens |

### Grid

- Max content width: 1280px
- Gutter: 24px (lg spacing)
- Columns: 12

---

## Icons

**Library:** [Specify icon library, e.g., Heroicons, Lucide]

**Sizes:**
- sm: 16px
- md: 20px
- lg: 24px

**Usage:**
- Use outlined icons for navigation
- Use solid icons for active/selected states
- Always include aria-label for accessibility

---

## Accessibility

### Color Contrast
- Normal text: 4.5:1 minimum
- Large text: 3:1 minimum
- UI components: 3:1 minimum

### Focus States
- All interactive elements must have visible focus indicator
- Use 2px ring with primary color

### Motion
- Respect `prefers-reduced-motion`
- Keep animations under 300ms
- Avoid auto-playing animations

---

## Dark Mode

[Document dark mode color mappings if applicable]

| Light | Dark | Usage |
|-------|------|-------|
| white | gray-900 | Background |
| gray-50 | gray-800 | Surface |
| gray-900 | white | Text |

---

## Component Library

[Reference to component library if using one, e.g., Shadcn, Radix, MUI]

**Documentation:** [Link to component docs]
**Storybook:** [Link to Storybook if available]
