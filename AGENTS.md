# PAES Importer development

Use Python with -B. This repository owns tests, maintenance tools and documentation. The sibling paes-importer-skill is the only maintained runtime. Select it explicitly with --runtime or PAES_IMPORTER_RUNTIME. Keep environments, generated files, caches and backups here, outside runtime. Resolve links and junctions before writing. Do not install skills globally.

Runtime scripts, schemas, references and validators resolve from the selected skill. Development tools must not maintain another runtime copy or fall back to archived code. Distributions use distribution.json and release.json. Never include .venv, caches, generated runs, private PDFs or browsers.

Preserve official content 0.2.0 and package 0.1.0, identifiers and traceability. Compare contract.lock.json with the canonical contract before releases. Update the normative source only after reviewing and backing up a proposed fix. TESLA RC3 is read-only. Run scripts/check.py against the selected runtime and check the physical tree, not only Git status.

Tests and examples are synthetic. Do not run real AI imports to test implementation. A host's declared reading or independent review is not proof of comprehension or accuracy. Never hardcode private exam content or question-number exceptions in the engine.

Preserve historical results and the pre-separation bundle/manifests. Audit all reachable history and public files before creating a public repository. No remote publication or merge without authorization. Runtime users choose an external workspace; preserve that boundary and never overwrite runs.
