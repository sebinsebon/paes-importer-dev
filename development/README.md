# Documentación de mantenimiento

Este directorio **no forma parte de la skill para agentes** ni del ZIP distribuible. Conserva informes y decisiones históricas, no instrucciones para importar ensayos.

La fuente versionada de la herramienta canónica es [contract-maintenance.py](contract-maintenance.py). La copia instalada vive en `contrato/mantenimiento/contract.py`. Desde el clon: `python -B development/contract-maintenance.py check --contract-root RUTA_CONTRATO --importer . --web RUTA_WEB`. El contrato local conserva sus especificaciones e informes privados; Git distribuye los esquemas, validadores y referencias normativas portables, sin paquetes TESLA ni capturas de auditoría.

- [VERIFICATION.md](VERIFICATION.md): resultados históricos de pruebas.
- [PORTABILITY.md](PORTABILITY.md): informe de portabilidad.
- [DECISIONS.md](DECISIONS.md): decisiones durante el desarrollo.

Las instrucciones operativas están en [SKILL.md](../SKILL.md), [references/](../references/workflow.md) y los contratos de [shared/references/](../shared/references/content-contract.md).

## Pruebas para mantenedores

Con Python/Node y dependencias de desarrollo, desde el clon:

~~~sh
python -B scripts/setup.py --dev
.venv/bin/python -B -m unittest discover -s tests -v
.venv/bin/python -B scripts/release.py
~~~

En Windows utiliza `.venv/Scripts/python.exe`; si ya existe `.venv`, instala `requirements-dev.txt` y no vuelvas a ejecutar setup.py.

`tests/`, `examples/`, `.github/` y `AGENTS.md` son solo de mantenimiento: no se incluyen en la skill distribuida. La prueba de portabilidad extrae el bundle mínimo en otra carpeta y verifica sus enlaces, CLI y preparación de un PDF ficticio sin IA. La suite completa del importador continúa ejecutándose desde GitHub.
