# Desarrollo y runtime

`paes-importer-skill` es la única fuente mantenida del runtime. Este repositorio contiene pruebas, fuentes sintéticas y mantenimiento. `--runtime` selecciona explícitamente qué árbol se comprueba; `PAES_IMPORTER_RUNTIME` permite invocar herramientas históricas y pruebas directamente. Ninguna herramienta busca otra instalación como alternativa.

## Pruebas locales

Desde esta carpeta:

```text
python -B scripts/setup_dev.py --runtime ../paes-importer-skill
.venv/Scripts/python.exe -B scripts/check.py --runtime ../paes-importer-skill --report results/verification-UNICO.json
```

En Linux/macOS el intérprete es `.venv/bin/python`. `--tests-only` permite una etapa aislada; `--pattern test_development.py` limita pruebas. El informe identifica ambos commits, hash de release, dependencias, comandos y cambios del árbol físico operativo. Incluye archivos ignorados y directorios vacíos, sin seguir enlaces ni recorrer `.git`.

Los tests importan y ejecutan módulos del árbol operativo seleccionado. Las únicas copias de runtime son artefactos de distribución o respaldos identificados, nunca otra fuente editable. Los temporales, cachés, experimentos e informes permanecen aquí y están excluidos de Git público.

## Distribución

```text
python -B scripts/release.py --runtime ../paes-importer-skill
python -B scripts/make_bundle.py --runtime ../paes-importer-skill --output releases/paes-importer-UNICO.zip
```

`distribution.json` enumera exactamente los archivos permitidos; añadir un recurso requiere revisión explícita. El manifiesto debe coincidir con sus bytes. `release.py --write` es la única actualización deliberada de hashes: conserva la versión y protocolo declarados en la release. La comprobación y construcción ordinarias no editan fuentes.

El ZIP ordena nombres POSIX, usa almacenamiento sin compresión, fecha fija y permisos fijos. Dos construcciones del mismo árbol deben tener igual SHA-256. El payload incluye dependencias operativas distribuidas, nunca navegador, venv, tests o PDFs privados.

## Git y CI

La copia Git local conserva el historial de origen. Antes de publicar cualquier repositorio nuevo, ejecuta history_audit.py sobre todas las referencias y revisa sus candidatos. El reporte es redactado y no prueba por sí mismo ausencia de información privada. No se ha publicado este repositorio como parte de la migración local.

Ambos workflows son manuales y exigen el SHA completo del otro repositorio. No pueden ejecutarse remotamente hasta publicar los commits auditados. `runtime.lock.json` identifica la base y el hash del candidato local, sin atribuirle un commit inexistente. Antes de activar push/pull_request se debe registrar una pareja inmutable que haya pasado la matriz, fijar su SHA y quitar el estado pendiente del lock. No se usa la base anterior con pruebas nuevas que requieren otro protocolo.

El repositorio de desarrollo conserva el historial completo de origen y la eliminación versionada de los archivos operativos en su árbol actual. Esos blobs históricos son respaldos Git; el desarrollo activo usa únicamente `--runtime`. La alternativa de filtrar historial reduciría tamaño pero cambiaría SHAs y trazabilidad, por eso no se aplica sin necesidad demostrada. Las carpetas privadas ignoradas no se publican.

## Contrato normativo

`scripts/contract.py --runtime ../paes-importer-skill --contract-root ../contrato` compara el runtime, el manifiesto canónico y `contract.lock.json`. Sin `--contract-root`, CI verifica los mismos bytes fijados en el lock. La herramienta no modifica el contrato ni el runtime. `--write-lock` es una operación explícita después de revisar y sincronizar la fuente normativa. Una modificación del esquema requiere decisión normativa, nunca regeneración automática del lock para silenciar un fallo.

Los tests locales no acreditan ejecución remota de Actions, compatibilidad real de cada anfitrión ni fidelidad de una importación real.
