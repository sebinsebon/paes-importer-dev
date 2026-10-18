# Revisión de pendientes — 2026-10-15

## Cambios verificados

- `1d0b457`: la prueba de benchmark crea su carpeta temporal; anteriormente fallaba en un checkout limpio.
- `d169aff`: Python admite directorios ZIP vacíos bajo `assets/` y `evidence/`, como el lector web. Los directorios no forman parte del inventario de archivos del manifiesto.
- Se mantienen los rechazos de rutas inseguras, directorios inesperados/con datos y duplicados sin distinguir mayúsculas. Se actualizó el checksum de `package_io.py` en `release.json`.
- La regresión nueva falló antes del cambio para 0.1.0 y 0.2.0, y pasó después. El candidato curricular TESLA rc1 reprodujo el mismo error `Unsafe relative path: 'assets/'`; ahora pasa el validador Python, que también ejecuta el lector JS.

## Pruebas

Windows, Python 3.14 del entorno existente y Node 22.22.3:

```text
python -B scripts/release.py
112 release files verified
python -B -m unittest discover -s tests -v
Ran 131 tests in 72.892s
OK (skipped=1)
```

La prueba omitida requiere privilegios para crear un enlace simbólico. No se acredita esa comprobación en este equipo. La matriz Linux/Python 3.12/3.14 corresponde al CI, no a estas pruebas locales.

## Ramas

`origin/main` inicial: `4f09874`. `chore/skill-runtime-vs-development` ya estaba integrado por PR #1; su árbol coincide exactamente con ese main.

La cadena `refactor/four-workflows` (`726d777`) → `fix/web-delivery-content-quality` (`f228850`) → `feat/paes-importer-contract-0.2.0` (`fa46867`) tiene relaciones de ancestro confirmadas. La integración conjunta incorpora los cuatro flujos, las correcciones de entrega/calidad y el contrato 0.2.0, además de los dos arreglos anteriores. La integración local es `b442f89` y su árbol coincide con `d169aff`.

Los validadores JS de esta rama y del renderizador web `101227f` son idénticos byte a byte. Las pruebas incluyen contrato 0.1.0, curriculum 0.2.0, fórmulas, alternativas, recursos, evidencia, recuperación y transporte JSON.

## Límites pendientes

No se realizó una nueva importación con IA en Codex Chat Web ni en AGY CLI. Las pruebas sintéticas y de empaquetado no demuestran fidelidad semántica en esos anfitriones. Siguen pendientes pruebas reales separadas de pérdida/sustitución de enunciados, radicales/fracciones/exponentes, alternativas completas y asociación visual contra el PDF.

Se verificaron estructura y hashes del candidato TESLA curricular rc1 y se confirmó que conserva cuatro recortes P41 antiguos e incompletos. Se generó una rc2 separada en `tmp/`, preservando originales y las 65 preguntas. Ni esta validación ni la reparación de los recortes certifican Gold: falta el cotejo individual completo contra ensayo y solucionario y su revisión visual final.
