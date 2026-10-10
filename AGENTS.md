# PAESSED portable skill

Use Python with -B. During implementation, keep new files, temporary files and caches in this checkout (tmp/ for generated artifacts). Resolve links and junctions before writing. External projects and user-provided PDFs/outputs are read-only. Do not install skills globally.

Resolve bundled scripts, schemas, references and validators from this skill's directory, never from a parent project or the caller's working directory. Python/Node and installed requirements are host prerequisites; source files and output destinations are supplied by the user. Do not distribute .venv, caches or generated runs.

Preserve the existing content/package schemas, identifiers and audit protocol. Historical names in those contracts are compatibility details, not dependencies on another checkout. Run the synthetic suite and release checks after changes; refresh release.json for intentional changes before starting new runs.

Tests and examples are synthetic. Do not run real AI imports to test implementation. A host's declared reading or independent review is not proof of comprehension or accuracy. Never hardcode private exam content or question-number exceptions in the engine.

Runtime users may explicitly select output folders outside the checkout; preserve the selected workspace boundary and existing results. Do not silently substitute a destination or overwrite a run.
