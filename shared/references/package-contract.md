# Contrato de paquete

ZIP y .paessed son contenedores ZIP idénticos. Raíz: final.json, manifest.json y assets/ usados. PDFs, evidencia de auditoría, trazas y métricas quedan fuera en .work. No se incorpora contenido automáticamente al banco público.

manifest: format paessed-package, schema_version 0.1.0, files con path/bytes/SHA-256 excepto manifest.json. Rechazar rutas absolutas, .., separadores Windows, enlaces, duplicados incluso por mayúsculas, referencias rotas, hashes alterados y archivos inesperados.

Límites: 10.000 entradas, 256 MiB descomprimidos y 272 MiB comprimidos. Recursos PNG; texto literal y KaTeX trust=false. Verificar con el mismo lector JavaScript antes de publicar.

importer.py pack --run RUN publica <nombre>.zip y .paessed; bloquea auditoría independiente pendiente. baseline conserva el control en .work/base. verify consolidate publica el resultado de auditoría.

No sobrescribir resultados. Fallos conservan candidato/evidencia. inspect valida contenedor y resume comprueba fuentes, selección/configuración y release. No certifican calidad matemática.
