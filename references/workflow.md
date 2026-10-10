# Operación portable

Trabaja con el bundle completo de esta skill. Python y Node realizan operaciones deterministas; el anfitrión aporta interpretación, lectura visual y solución. Instalación y comandos de prueba: [README](../README.md). Para formatos exactos de entradas: [interfaces](interfaces.md).

## Preparación

Antes de preparar, el anfitrión pregunta el destino y observa las capacidades. Guarda capabilities.json en su espacio de trabajo:

~~~json
{"pdf_visual":true,"crop":true,"execute":true,"zip":true,"validate":true,"observation":"Describe la prueba visual y las herramientas realmente disponibles"}
~~~

No uses el ejemplo como recibo de capacidad. Copia o adjunta el bundle completo; no solo SKILL.md.

Los comandos relativos de esta guía y de auditoría se ejecutan desde la carpeta que contiene SKILL.md, usando un Python con requirements.txt instalado. Desde otra carpeta, utiliza las rutas absolutas del intérprete y de scripts/importer.py. Los recursos internos se resuelven desde la skill; las rutas relativas de entrada se interpretan desde el directorio de ejecución. Usa rutas absolutas para los PDFs, JSON de trabajo y RUN cuando cambies de directorio:

~~~text
python -B scripts/importer.py prepare --exam /ruta/ensayo.pdf --solution /ruta/pauta.pdf --host cli --client codex --session-id SESION_REAL --model MODELO_OBSERVADO --effort ESFUERZO_OBSERVADO --destination documents --capabilities /ruta/capabilities.json
~~~

--solution es opcional; una pauta integrada no repite el mismo PDF. --destination downloads usa Descargas/EnsayosPaessedOutput. --destination custom --output-root /ruta/absoluta usa esa ruta directamente. Para chat web: --host web --destination custom --output-root DIRECTORIO_ESCRIBIBLE_WEB --suggested-save-location documents (o downloads/ruta elegida). La elección local es una recomendación de descarga.

prepare devuelve output y run. output es <raíz>/<nombre-normalizado>/<fecha-hora-id>; run es output/.work/base. --title cambia el nombre, únicamente con datos observados. --run-id permite un ID explícito nuevo. Un destino existente se rechaza. Falta de permisos exige otro destino; no hay fallback silencioso.

Se crean fuentes con hashes, catálogo, páginas PNG y plantilla de lectura. No se reconstruyen ni resuelven preguntas automáticamente. Las imágenes del catálogo son candidatas; los gráficos vectoriales necesitan crop explícito. Si prepare falla, conserva failed_preparation y usa una nueva ejecución tras corregir la causa.

## Mapa, pauta y selección de modo

Lee todas las fuentes. Escribe selection.json con expected_questions desde el ensayo, observación del mapa y observed_question_count. Luego:

~~~text
python -B scripts/importer.py map --run RUN --selection selection.json
python -B scripts/importer.py route --run RUN --answer-key key.json --subagents
~~~

Omite --answer-key si no hay pauta válida. --subagents solo se declara si se dispone de contexto independiente y lectura de imágenes en esos agentes. En CLI con pauta completa no genera auditoría. En chat web sin pauta completa, route devuelve needs_consent sin congelar la ruta. Tras respuesta real, repite con --experimental yes o no. El consentimiento se aplica a las preguntas sin pauta de esta ejecución.

La correspondencia de pauta es un juicio documentado del anfitrión, no una certificación automática. Una pauta incompatible/ambigua es rechazada por route; solicita aclaración o continúa sin ella, conservando la incidencia en issues. No modifiques el mapa congelado para aparentar correspondencia.

Completa direct-input.template.json como direct-input.json con modo native_pdf o page_images_fallback, reader, observación visual y pages_read de cada fuente. Registra solo páginas efectivamente inspeccionadas. Después:

~~~text
python -B scripts/importer.py record-input --run RUN --response direct-input.json
~~~

## Producción y cotejo

Escribe un JSON por lote con run_id, questions completas y explanation_provenance. Guarda versiones originales; ingest las archiva bajo raw y vincula automáticamente las respuestas de pauta. No puede inventarse origin=answer-key sin una entrada congelada.

~~~text
python -B scripts/importer.py crops --run RUN --requests crops.json
python -B scripts/importer.py ingest --run RUN --response batch.json
python -B scripts/importer.py check-template --run RUN
python -B scripts/importer.py record-check --run RUN --response cotejo.json
~~~

check-template imprime JSON; guárdalo con las herramientas de archivo disponibles y completa los IDs del lote. Cada cotejo tiene seis dimensiones y citas a imágenes con ID, hash y observación. Mantén independent=false y la sesión productora. Se guarda el original y se comprueba la versión de pregunta/solución; cambios posteriores exigen refrescar el cotejo afectado. No modifica estados semánticos.

Con pauta parcial solo se resuelve solve_question_ids. Si el usuario rechazó el modo experimental, pending_question_ids deben conservar answer missing, origin none y explanation missing. Se permiten dudas explícitas, con estructura válida; no se permiten recursos ausentes, fórmulas corruptas ni bloques mal serializados.

## Finalización

~~~text
python -B scripts/importer.py validate --run RUN
python -B scripts/importer.py pack --run RUN
~~~

pack publica directamente si no se requiere auditoría independiente. Si la requiere, bloquea publicación: usa baseline y [auditoría](audit.md). El ZIP contiene final.json, manifest.json y assets usados; no incluye PDFs, trazas, evidencias o carpetas de trabajo. También se produce un .paessed de bytes idénticos, compatible con el contenedor anterior.

El directorio final conserva final.json, candidate.json, recursos usados, ZIP, .paessed, run.json y .work. No se alteran ejecuciones publicadas. Resumen: cobertura, respuestas de pauta/IA/pendientes, explicaciones de pauta/IA, autorrevisión/independencia y dudas; no calcular precisión a partir de estados.

~~~text
python -B scripts/importer.py inspect --package ARCHIVO.zip
python -B scripts/importer.py resume --run RUN
python -B scripts/importer.py fail --run RUN --reason MOTIVO
~~~

resume verifica release, fuentes y mapa/configuración congelados. No reanuda automáticamente trabajo de IA. Para auditoría awaiting_reviews, conserva informes terminados, ejecuta verify check y completa solo lotes faltantes. Cambios de código o fuente requieren una ejecución nueva. Medidas no expuestas por el anfitrión son null; no inventar modelo, sesión, esfuerzo, tokens ni costo.
