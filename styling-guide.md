# BioLab Design System & Styling Guide

## Overview

This document defines the comprehensive design system for BioLab, a modern laboratory management application. The design system establishes consistent visual language, interaction patterns, and component standards to create a cohesive, accessible, and scalable user experience.

## Design Philosophy

### Core Principles
- **Scientific Precision**: Clean, precise design that reflects the accuracy needed in laboratory work
- **Accessibility First**: WCAG 2.1 AA compliance with focus on usability for all users
- **Modern Minimalism**: Clean, uncluttered interfaces that focus on functionality
- **Consistency**: Predictable patterns and interactions across all features
- **Scalability**: Design tokens and components that grow with the application

### Visual Identity
- **Professional**: Trustworthy and credible for scientific work
- **Intuitive**: Clear information hierarchy and navigation
- **Efficient**: Optimized for productivity and workflow efficiency
- **Collaborative**: Designed for team-based laboratory environments

## Color System

### Primary Palette
```css
:root {
  /* Primary - Scientific Blue */
  --color-primary-50: #eff6ff;
  --color-primary-100: #dbeafe;
  --color-primary-200: #bfdbfe;
  --color-primary-300: #93c5fd;
  --color-primary-400: #60a5fa;
  --color-primary-500: #3b82f6;  /* Main primary */
  --color-primary-600: #2563eb;
  --color-primary-700: #1d4ed8;
  --color-primary-800: #1e40af;
  --color-primary-900: #1e3a8a;
  --color-primary-950: #172554;
}
```

### Secondary Palette
```css
:root {
  /* Secondary - Laboratory Green */
  --color-secondary-50: #f0fdf4;
  --color-secondary-100: #dcfce7;
  --color-secondary-200: #bbf7d0;
  --color-secondary-300: #86efac;
  --color-secondary-400: #4ade80;
  --color-secondary-500: #22c55e;  /* Main secondary */
  --color-secondary-600: #16a34a;
  --color-secondary-700: #15803d;
  --color-secondary-800: #166534;
  --color-secondary-900: #14532d;
  --color-secondary-950: #052e16;
}
```

### Semantic Colors
```css
:root {
  /* Success */
  --color-success-50: #f0fdf4;
  --color-success-500: #22c55e;
  --color-success-600: #16a34a;
  --color-success-700: #15803d;

  /* Warning */
  --color-warning-50: #fffbeb;
  --color-warning-500: #f59e0b;
  --color-warning-600: #d97706;
  --color-warning-700: #b45309;

  /* Error */
  --color-error-50: #fef2f2;
  --color-error-500: #ef4444;
  --color-error-600: #dc2626;
  --color-error-700: #b91c1c;

  /* Info */
  --color-info-50: #f0f9ff;
  --color-info-500: #06b6d4;
  --color-info-600: #0891b2;
  --color-info-700: #0e7490;
}
```

### Neutral Palette
```css
:root {
  /* Neutral Grays */
  --color-neutral-50: #fafafa;
  --color-neutral-100: #f5f5f5;
  --color-neutral-200: #e5e5e5;
  --color-neutral-300: #d4d4d4;
  --color-neutral-400: #a3a3a3;
  --color-neutral-500: #737373;
  --color-neutral-600: #525252;
  --color-neutral-700: #404040;
  --color-neutral-800: #262626;
  --color-neutral-900: #171717;
  --color-neutral-950: #0a0a0a;
}
```

### Color Usage Guidelines
- **Primary**: Main actions, navigation, links, focus states
- **Secondary**: Success states, positive actions, completion indicators
- **Neutral**: Text, backgrounds, borders, disabled states
- **Semantic**: Status indicators, alerts, feedback messages

## Typography

### Font Stack
```css
:root {
  /* Primary font family - Modern sans-serif */
  --font-family-primary: "Inter", system-ui, -apple-system, sans-serif;
  
  /* Monospace font for code/data */
  --font-family-mono: "JetBrains Mono", "Fira Code", monospace;
}
```

### Type Scale
```css
:root {
  /* Font sizes */
  --text-xs: 0.75rem;     /* 12px */
  --text-sm: 0.875rem;    /* 14px */
  --text-base: 1rem;      /* 16px */
  --text-lg: 1.125rem;    /* 18px */
  --text-xl: 1.25rem;     /* 20px */
  --text-2xl: 1.5rem;     /* 24px */
  --text-3xl: 1.875rem;   /* 30px */
  --text-4xl: 2.25rem;    /* 36px */
  --text-5xl: 3rem;       /* 48px */

  /* Font weights */
  --font-light: 300;
  --font-normal: 400;
  --font-medium: 500;
  --font-semibold: 600;
  --font-bold: 700;

  /* Line heights */
  --leading-tight: 1.25;
  --leading-normal: 1.5;
  --leading-relaxed: 1.75;
}
```

### Typography Hierarchy
```css
/* Headings */
.text-h1 {
  font-size: var(--text-4xl);
  font-weight: var(--font-bold);
  line-height: var(--leading-tight);
  color: var(--color-neutral-900);
}

.text-h2 {
  font-size: var(--text-3xl);
  font-weight: var(--font-semibold);
  line-height: var(--leading-tight);
  color: var(--color-neutral-900);
}

.text-h3 {
  font-size: var(--text-2xl);
  font-weight: var(--font-semibold);
  line-height: var(--leading-normal);
  color: var(--color-neutral-800);
}

.text-h4 {
  font-size: var(--text-xl);
  font-weight: var(--font-medium);
  line-height: var(--leading-normal);
  color: var(--color-neutral-800);
}

/* Body text */
.text-body-lg {
  font-size: var(--text-lg);
  font-weight: var(--font-normal);
  line-height: var(--leading-relaxed);
  color: var(--color-neutral-700);
}

.text-body {
  font-size: var(--text-base);
  font-weight: var(--font-normal);
  line-height: var(--leading-normal);
  color: var(--color-neutral-700);
}

.text-body-sm {
  font-size: var(--text-sm);
  font-weight: var(--font-normal);
  line-height: var(--leading-normal);
  color: var(--color-neutral-600);
}

/* Utility text */
.text-caption {
  font-size: var(--text-xs);
  font-weight: var(--font-normal);
  line-height: var(--leading-normal);
  color: var(--color-neutral-500);
}

.text-code {
  font-family: var(--font-family-mono);
  font-size: var(--text-sm);
  background-color: var(--color-neutral-100);
  padding: 0.125rem 0.25rem;
  border-radius: 0.25rem;
}
```

## Spacing System

### Spacing Scale
```css
:root {
  /* Spacing units (based on 4px grid) */
  --space-0: 0;
  --space-1: 0.25rem;   /* 4px */
  --space-2: 0.5rem;    /* 8px */
  --space-3: 0.75rem;   /* 12px */
  --space-4: 1rem;      /* 16px */
  --space-5: 1.25rem;   /* 20px */
  --space-6: 1.5rem;    /* 24px */
  --space-8: 2rem;      /* 32px */
  --space-10: 2.5rem;   /* 40px */
  --space-12: 3rem;     /* 48px */
  --space-16: 4rem;     /* 64px */
  --space-20: 5rem;     /* 80px */
  --space-24: 6rem;     /* 96px */
  --space-32: 8rem;     /* 128px */
}
```

### Layout Spacing
```css
:root {
  /* Layout specific spacing */
  --space-page-padding: var(--space-6);
  --space-section-gap: var(--space-12);
  --space-component-gap: var(--space-8);
  --space-element-gap: var(--space-4);
  --space-content-gap: var(--space-3);
}
```

## Layout System

### Container Sizes
```css
:root {
  /* Container max widths */
  --container-sm: 640px;
  --container-md: 768px;
  --container-lg: 1024px;
  --container-xl: 1280px;
  --container-2xl: 1536px;
}
```

### Grid System
```css
/* 12-column grid */
.grid-12 {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: var(--space-6);
}

/* Common grid layouts */
.grid-sidebar {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: var(--space-8);
}

.grid-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--space-6);
}
```

### Breakpoints
```css
:root {
  /* Responsive breakpoints */
  --breakpoint-sm: 640px;
  --breakpoint-md: 768px;
  --breakpoint-lg: 1024px;
  --breakpoint-xl: 1280px;
  --breakpoint-2xl: 1536px;
}
```

## Component Standards

### Border Radius
```css
:root {
  --radius-none: 0;
  --radius-sm: 0.125rem;   /* 2px */
  --radius-base: 0.25rem;  /* 4px */
  --radius-md: 0.375rem;   /* 6px */
  --radius-lg: 0.5rem;     /* 8px */
  --radius-xl: 0.75rem;    /* 12px */
  --radius-2xl: 1rem;      /* 16px */
  --radius-full: 9999px;
}
```

### Shadows
```css
:root {
  /* Box shadows */
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-base: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
  --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
  --shadow-2xl: 0 25px 50px -12px rgb(0 0 0 / 0.25);
}
```

### Transitions
```css
:root {
  /* Transition durations */
  --transition-fast: 150ms;
  --transition-base: 200ms;
  --transition-slow: 300ms;
  
  /* Transition easing */
  --ease-in: cubic-bezier(0.4, 0, 1, 1);
  --ease-out: cubic-bezier(0, 0, 0.2, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
}
```

## Button Component Standards

### Button Variants
```css
/* Primary Button */
.btn-primary {
  background-color: var(--color-primary-500);
  color: white;
  border: none;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  font-weight: var(--font-medium);
  font-size: var(--text-sm);
  transition: all var(--transition-base) var(--ease-in-out);
}

.btn-primary:hover {
  background-color: var(--color-primary-600);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.btn-primary:active {
  background-color: var(--color-primary-700);
  transform: translateY(0);
}

.btn-primary:disabled {
  background-color: var(--color-neutral-300);
  cursor: not-allowed;
  transform: none;
}

/* Secondary Button */
.btn-secondary {
  background-color: transparent;
  color: var(--color-primary-500);
  border: 1px solid var(--color-primary-500);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  font-weight: var(--font-medium);
  font-size: var(--text-sm);
  transition: all var(--transition-base) var(--ease-in-out);
}

.btn-secondary:hover {
  background-color: var(--color-primary-50);
  border-color: var(--color-primary-600);
}

/* Ghost Button */
.btn-ghost {
  background-color: transparent;
  color: var(--color-neutral-700);
  border: none;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  font-weight: var(--font-medium);
  font-size: var(--text-sm);
  transition: all var(--transition-base) var(--ease-in-out);
}

.btn-ghost:hover {
  background-color: var(--color-neutral-100);
  color: var(--color-neutral-900);
}

/* Button sizes */
.btn-sm {
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-xs);
}

.btn-lg {
  padding: var(--space-4) var(--space-6);
  font-size: var(--text-base);
}
```

## Form Component Standards

### Input Fields
```css
.form-input {
  width: 100%;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-neutral-300);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
  color: var(--color-neutral-900);
  background-color: white;
  transition: all var(--transition-base) var(--ease-in-out);
}

.form-input:focus {
  outline: none;
  border-color: var(--color-primary-500);
  box-shadow: 0 0 0 3px rgb(59 130 246 / 0.1);
}

.form-input:disabled {
  background-color: var(--color-neutral-50);
  color: var(--color-neutral-500);
  cursor: not-allowed;
}

.form-input.error {
  border-color: var(--color-error-500);
}

.form-input.error:focus {
  border-color: var(--color-error-500);
  box-shadow: 0 0 0 3px rgb(239 68 68 / 0.1);
}
```

### Form Layout
```css
.form-group {
  margin-bottom: var(--space-4);
}

.form-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-neutral-700);
  margin-bottom: var(--space-2);
}

.form-error {
  display: block;
  font-size: var(--text-xs);
  color: var(--color-error-600);
  margin-top: var(--space-1);
}

.form-help {
  display: block;
  font-size: var(--text-xs);
  color: var(--color-neutral-500);
  margin-top: var(--space-1);
}
```

## Card Component Standards

```css
.card {
  background-color: white;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  transition: all var(--transition-base) var(--ease-in-out);
}

.card:hover {
  box-shadow: var(--shadow-md);
}

.card-header {
  padding: var(--space-6);
  border-bottom: 1px solid var(--color-neutral-200);
}

.card-body {
  padding: var(--space-6);
}

.card-footer {
  padding: var(--space-6);
  background-color: var(--color-neutral-50);
  border-top: 1px solid var(--color-neutral-200);
}
```

## Navigation Standards

### Primary Navigation
```css
.nav-primary {
  background-color: white;
  border-bottom: 1px solid var(--color-neutral-200);
  box-shadow: var(--shadow-sm);
}

.nav-item {
  padding: var(--space-4) var(--space-6);
  color: var(--color-neutral-700);
  text-decoration: none;
  font-weight: var(--font-medium);
  transition: all var(--transition-base) var(--ease-in-out);
}

.nav-item:hover {
  color: var(--color-primary-600);
  background-color: var(--color-primary-50);
}

.nav-item.active {
  color: var(--color-primary-600);
  background-color: var(--color-primary-50);
  border-bottom: 2px solid var(--color-primary-600);
}
```

### Breadcrumbs
```css
.breadcrumbs {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.breadcrumb-item {
  color: var(--color-neutral-500);
  font-size: var(--text-sm);
  text-decoration: none;
}

.breadcrumb-item:hover {
  color: var(--color-primary-600);
}

.breadcrumb-item.active {
  color: var(--color-neutral-900);
  font-weight: var(--font-medium);
}

.breadcrumb-separator {
  color: var(--color-neutral-400);
  font-size: var(--text-xs);
}
```

## Data Display Standards

### Tables
```css
.table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.table th {
  background-color: var(--color-neutral-50);
  color: var(--color-neutral-900);
  font-weight: var(--font-semibold);
  padding: var(--space-3) var(--space-4);
  text-align: left;
  border-bottom: 2px solid var(--color-neutral-200);
}

.table td {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-neutral-200);
  color: var(--color-neutral-700);
}

.table tbody tr:hover {
  background-color: var(--color-neutral-50);
}
```

### Lists
```css
.list-item {
  padding: var(--space-4);
  border-bottom: 1px solid var(--color-neutral-200);
  transition: all var(--transition-base) var(--ease-in-out);
}

.list-item:hover {
  background-color: var(--color-neutral-50);
}

.list-item:last-child {
  border-bottom: none;
}
```

## Feedback Components

### Alerts
```css
.alert {
  padding: var(--space-4);
  border-radius: var(--radius-md);
  border: 1px solid;
  font-size: var(--text-sm);
  margin-bottom: var(--space-4);
}

.alert-success {
  background-color: var(--color-success-50);
  border-color: var(--color-success-200);
  color: var(--color-success-800);
}

.alert-warning {
  background-color: var(--color-warning-50);
  border-color: var(--color-warning-200);
  color: var(--color-warning-800);
}

.alert-error {
  background-color: var(--color-error-50);
  border-color: var(--color-error-200);
  color: var(--color-error-800);
}

.alert-info {
  background-color: var(--color-info-50);
  border-color: var(--color-info-200);
  color: var(--color-info-800);
}
```

### Loading States
```css
.skeleton {
  background: linear-gradient(
    90deg,
    var(--color-neutral-200) 25%,
    var(--color-neutral-100) 50%,
    var(--color-neutral-200) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
}

@keyframes skeleton-loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-neutral-200);
  border-top: 2px solid var(--color-primary-500);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
```

## Accessibility Standards

### Focus Management
```css
/* Focus visible styles */
.focus-visible {
  outline: 2px solid var(--color-primary-500);
  outline-offset: 2px;
}

/* Skip link */
.skip-link {
  position: absolute;
  top: -40px;
  left: 6px;
  background: var(--color-primary-500);
  color: white;
  padding: 8px;
  text-decoration: none;
  border-radius: 4px;
  z-index: 1000;
}

.skip-link:focus {
  top: 6px;
}
```

### Color Contrast Requirements
- **Normal text**: 4.5:1 contrast ratio minimum
- **Large text**: 3:1 contrast ratio minimum
- **Interactive elements**: 3:1 contrast ratio minimum
- **Focus indicators**: 3:1 contrast ratio minimum

## Dark Mode Support

### Dark Mode Variables
```css
@media (prefers-color-scheme: dark) {
  :root {
    /* Dark mode overrides */
    --color-neutral-50: #1a1a1a;
    --color-neutral-100: #262626;
    --color-neutral-200: #404040;
    --color-neutral-300: #525252;
    --color-neutral-400: #737373;
    --color-neutral-500: #a3a3a3;
    --color-neutral-600: #d4d4d4;
    --color-neutral-700: #e5e5e5;
    --color-neutral-800: #f5f5f5;
    --color-neutral-900: #fafafa;
  }
}
```

## Implementation Guidelines

### Tailwind CSS Configuration
```javascript
// tailwind.config.js
module.exports = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
        // ... other colors
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      spacing: {
        // Custom spacing values
      },
      borderRadius: {
        // Custom border radius values
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
```

### Component Architecture
- **Atomic Design**: Atoms → Molecules → Organisms → Templates → Pages
- **Composition Pattern**: Flexible, reusable components
- **Prop Interfaces**: Strong TypeScript typing for all props
- **Accessibility**: Built-in ARIA attributes and keyboard navigation

### Performance Considerations
- **Component Lazy Loading**: Dynamic imports for non-critical components
- **CSS-in-JS Optimization**: Minimal runtime styles
- **Asset Optimization**: Optimized fonts and images
- **Bundle Splitting**: Separate vendor and app bundles

## Quality Assurance

### Testing Standards
- **Unit Tests**: Jest + React Testing Library
- **Integration Tests**: Component interaction testing
- **E2E Tests**: Playwright for user workflows
- **Accessibility Tests**: axe-core integration
- **Visual Regression**: Chromatic for UI changes

### Code Quality
- **ESLint**: Code linting with accessibility rules
- **Prettier**: Code formatting
- **TypeScript**: Strict type checking
- **Husky**: Pre-commit hooks for quality gates

### Documentation
- **Storybook**: Component documentation and testing
- **Design Tokens**: Documented token usage
- **Pattern Library**: Usage examples and guidelines
- **Accessibility Guide**: WCAG compliance documentation

## Migration Strategy

### Phase 1: Foundation (Weeks 1-2)
- Implement design tokens in CSS variables
- Update Tailwind configuration
- Create base component library (Button, Input, Card)

### Phase 2: Components (Weeks 3-4)
- Build remaining UI components
- Implement accessibility features
- Add dark mode support

### Phase 3: Integration (Weeks 5-6)
- Migrate existing pages to new components
- Implement responsive design
- Add Storybook documentation

### Phase 4: Optimization (Weeks 7-8)
- Performance optimization
- Accessibility audit and fixes
- Final testing and refinement

## Maintenance

### Regular Reviews
- **Monthly**: Design system usage audit
- **Quarterly**: Component performance review
- **Annually**: Complete design system refresh

### Documentation Updates
- Keep component documentation current
- Update usage examples
- Maintain accessibility guidelines
- Document new patterns and components

This styling guide provides the foundation for creating a consistent, modern, and accessible design system for BioLab. It should be treated as a living document that evolves with the application's needs while maintaining consistency and quality standards.