# Inline emphasis implementation plan

**Goal:** Preserve PDF bold/italic prose with existing 0.2.0 text blocks.

**Architecture:** Recognize only balanced, case-sensitive, attribute-free b/i pairs within one text block. Construct DOM nodes without HTML parsing. Keep source extraction advisory, preserve the exact native text and flag uncertain font metadata. No changes to schemas, math or verification states.

**Tech stack:** PDFium/pypdfium2, Python, JavaScript DOM, Next.js, Playwright.

1. Synchronize Git remotes; fast-forward clean main only. Preserve dirty integration checkouts; base feature work on stable main. Leave draft/experimental branches unmerged.
2. Add synthetic parser/security regressions to PAESSED tests/inline-emphasis.cjs. Check malformed nesting, old plain strings, whitespace and math/table separation. Add the same parser helpers to both block-renderer.js consumers; compare behavior in tests.
3. Update imported-question-content.ts and playground-imports.ts plain text extraction for search/copy. Patch the draft AI handoff independently with the same helper; never merge its other changes into this feature.
4. Test PDFium font name/weight/flags using synthetic PDFs in tests/test_inline_emphasis.py. Extend pdf_assets.py and importer.py source-text to return native text, styled text, source runs and pending diagnostics; never rebuild questions automatically.
5. Document the optional prose convention in references/representation.md and SKILL.md. Keep normative schemas and canonical contract bytes unchanged; describe the semantic extension and old-reader limitation in development docs.
6. Run the stable development suite against the explicit feature runtime, update only its manifest hashes, and verify its physical tree. Test runtime renderers, old packages and app build.
7. Create synthetic source/result artifacts outside runtime; inspect desktop/mobile Ensayos and Playground screenshots and compare the PDF. Keep all fidelity/Gold statuses pending.
8. Commit explicit paths, push review branches, create PRs, inspect Vercel preview and report evidence and limits. No new implementation merges to main.
