# Web integration

The named local consumer paesseduiux uses the same bounded reader, contract validator,
DOM renderer and KaTeX 0.16.22 as the portable Skill. A future release updates shared
resources with Python -B scripts/sync_web_runtime.py --target PATH. Existing different
files require --replace. The script validates all destinations before writing and
rejects junctions escaping the explicitly selected target.

The consumer changes are in its own checkout: paessed-package.ts, paessed-export.ts,
exam-editing.ts, paessed-blocks.tsx and import/viewer/settings components. IndexedDB
records retain their full document and archive without database migration.

Bare PAESSED JSON is accepted only when no resources are required. Generic JSON
remains a separate compatibility path; ZIP and .paessed use strict validation.
Exports contain exactly final.json and declared resources, a newly hashed manifest,
and pass the bounded reader before download. Edits preserve IDs, update the declared
question number, invalidate dependent reviews and curriculum, and remove certified
run claims. Rich blocks are edited only when the selected field is a sole text block.

Run consumer tests with node tests/paessed.cjs and typecheck with tsc --noEmit.
The portable development/gold-review.html opens packages locally and exposes all
blocks and statuses. It does not certify source fidelity or mathematical accuracy.
