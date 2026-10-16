# Contrato de paquete

La entrega oficial es .paessed; ZIP es un acompañante con bytes idénticos. Ambos son contenedores ZIP. Raíz: final.json, manifest.json y assets/ usados. PDFs, evidencia de auditoría, trazas y métricas quedan fuera en .work. No se incorpora contenido automáticamente al banco público.

manifest: format paessed-package, schema_version 0.1.0, files con path/bytes/SHA-256 excepto manifest.json. Rechazar rutas absolutas, .., separadores Windows, enlaces, duplicados incluso por mayúsculas, referencias rotas, hashes alterados y archivos inesperados.

Límites: 10.000 entradas, 256 MiB descomprimidos y 272 MiB comprimidos. Recursos PNG; texto literal y KaTeX trust=false. Verificar con el mismo lector JavaScript antes de publicar.

importer.py pack --run RUN publica <nombre>.paessed y su ZIP idéntico; bloquea auditoría independiente pendiente. baseline conserva el control en .work/base. verify consolidate publica el resultado de auditoría.

No sobrescribir resultados. Fallos conservan candidato/evidencia. inspect valida contenedor y resume comprueba fuentes, selección/configuración y release. No certifican calidad matemática.


## Contrato curricular 0.2.0

Toda nueva importación M1 incorpora questions[].curriculum = {eje, subeje, en_temario}. Clasificar automáticamente cada pregunta por su contenido usando los cuatro ejes y 16 subejes de shared/references/curriculum-m1.json; consultar shared/references/curriculum-contract.md para pertenencia, evidencia y pendientes. No copiar la taxonomía de TESLA ni inferir desde numeración. Cada lote añade curriculum_provenance[id] con reason y evidence [{source_id,page,observation}]. Clasificar también preguntas sin pauta o cuya resolución experimental se rechazó. Conservar la incertidumbre como dudoso; un par null requiere CURRICULUM_PENDING y entrega curricular parcial. Los lectores admiten finales históricos 0.1.0 sin inventar clasificación; el manifiesto del paquete sigue en 0.1.0.

## Fuente y distribución del contrato

La fuente canónica de mantenimiento es la carpeta `contrato/0.2.0` del espacio PAESSED. Este documento y los esquemas, catálogo y validadores incluidos son copias normativas distribuibles: el runtime los resuelve dentro del bundle y no necesita esa carpeta externa. El manifiesto `contrato/sincronizacion.json` fija sus hashes; `contrato/mantenimiento/contract.py check` detecta divergencias antes de publicar una release. Las nuevas entregas oficiales usan contenido `paessed-benchmark/0.2.0` y paquete `paessed-package/0.1.0`. La compatibilidad de lectura 0.1.0 no autoriza nueva emisión 0.1.0.
