# PAES Importer development

The only maintained runtime is https://github.com/sebinsebon/paes-importer-skill.
This checkout contains tests, synthetic examples, diagnostics and release tooling.
It never provides a fallback runtime implementation.

Use Python 3.12+ and Node 18+. Create `.venv` in this directory and install the
selected runtime's `requirements.txt` followed by this checkout's
`requirements-dev.txt`. Do not reuse virtual environments after relocation.

```powershell
.venv/Scripts/python.exe -B scripts/check.py --runtime ../paes-importer-skill --report results/check.json
```

The runner supplies `PAES_IMPORTER_RUNTIME` and `PAES_IMPORTER_WORK` to tests and
subprocesses. Direct maintenance commands require `PAES_IMPORTER_RUNTIME` too.
All results, caches, experimental imports, private sources and backups stay in
ignored directories. No private exam material is a test fixture or release input.

`backups/pre-separation.bundle` preserves the original Git history. File hash
manifests accompany the preserved tracked files, temporary results and old Python
environment. Historical runs retain original paths and hashes; they are not
silently rewritten or claimed resumable after relocation.

No public development repository has been created or published by this migration.
The reachable original history was screened before importing it into this local
repository and rechecked with the versioned scanner. Private reports remain in
`results/`; pattern screening alone is not a publication certificate.

See [architecture and CI](docs/architecture/separation.md) and the
[migration and reversal procedure](docs/architecture/migration.md).

```powershell
.venv/Scripts/python.exe -B scripts/contract.py --runtime ../paes-importer-skill --contract-root ../contrato
.venv/Scripts/python.exe -B scripts/make_bundle.py --runtime ../paes-importer-skill --output releases/unique-name.zip
```

The canonical directory is optional for everyday tests. Its reviewed lock is
versioned here; the runtime ships its own normative resources and works alone.
