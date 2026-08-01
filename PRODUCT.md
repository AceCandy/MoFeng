# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

MoFeng serves long-form fiction writers, especially individual authors and online novel creators who need to move from early inspiration to structured blueprints, chapter drafting, review, and revision. They work in extended writing sessions, often returning to the same project repeatedly, so the product must support continuity, memory, and low-friction progress rather than one-off generation.

## Product Purpose

The product is an AI-assisted writing workspace for long novels. It helps writers turn rough ideas into coherent story projects, manage worldbuilding and character material, generate and evaluate chapters, track foreshadowing and emotional arcs, and configure the AI models behind those workflows. Success means writers can understand project state quickly, trust the next action, and keep creative momentum without fighting configuration or UI noise.

## Positioning

An end-to-end long-novel pipeline — inspiration dialogue, story blueprint, chapter outline, drafted text, evaluation, and revision — with foreshadowing and emotional-arc tracking persisted across sessions, running against model providers the writer configures themselves. Neighboring tools offer one-shot generation or generic chat; they do not carry a novel's structure, memory, and per-stage model routing through weeks of drafting.

## Operating Context

Writers return to the same project across many sessions, at desktop and mobile widths; the workspace must restore context (project state, next action, pending chapters) immediately. The product is self-hosted: a FastAPI + Postgres backend (Redis optional, SMTP for email codes) and a Vue 3 + Vite frontend, with AI capabilities routed through providers and models each writer registers in settings — text generation, retrieval/memory, text-to-speech, and per-stage overrides. Account system includes email-code registration, optional linux.do OAuth, and an admin role for governance screens.

## Capabilities and Constraints

- Inspiration mode → blueprint (world, characters, relationships, chapter outline, emotion curve, foreshadowing) → writing desk (chapter drafting, generation, evaluation, revision) as one continuous workflow.
- Model management: multiple providers, model pull/enable, primary text and retrieval models, per-stage routing, runtime metrics; writers must be able to verify and recover configuration without admin help.
- Chinese-first long-form reading and writing; copy and generated content are primarily Chinese.
- Technical constraints future work must respect: the frontend test suite pins specific class names, aria strings, breakpoints, and the all-serif font stack — visual changes must keep those contracts green.
- Terminology in copy follows the writing-desk metaphor already established in the product (e.g. project = 书卷, writer = 阁主).

## Brand Commitments

Name: 墨风 (MoFeng). Quiet, professional, and dependable. The interface should feel like a reliable writing desk: focused, calm, and competent. It should support imaginative work without becoming decorative, theatrical, or marketing-heavy. Copy should be direct and helpful, with enough warmth for creative flow but no exaggerated personality.

## Anti-references

Do not make the product feel like a SaaS landing page, game UI, novelty AI demo, or over-branded content site. Avoid oversized hero sections, decorative illustration-first layouts, purple-blue AI gradients, glassmorphism, noisy animations, and card grids that make operational screens harder to scan. Avoid hiding critical configuration or writing state behind vague labels.

## Evidence on Hand

Product and workflow documentation lives in `docs/` (architecture, novel workflow, RAG, deployment); generation prompts in `backend/prompts/`. No testimonials, user metrics, press, or external case studies exist — future surfaces must not fabricate them.

## Design Principles

1. Keep writing momentum visible: show the current project state, next action, and blocking requirements clearly.
2. Reduce configuration anxiety: model, provider, and route settings should be explicit, recoverable, and easy to verify.
3. Prefer calm density: operational screens should be compact enough for repeated work, but spaced well enough for long sessions.
4. Treat AI as a collaborator, not a spectacle: expose useful controls and outcomes without making the interface performative.
5. Preserve trust through clarity: errors, loading states, destructive actions, and generated outputs should explain what happened and what the writer can do next.

## Accessibility & Inclusion

Target WCAG 2.1 AA. The product should support keyboard operation, clear focus states, sufficient color contrast, readable Chinese long-form text, and predictable layouts at desktop and mobile widths. Motion should be restrained and nonessential, with no critical information conveyed by color alone. Forms and configuration controls should use explicit labels and recoverable destructive actions.
