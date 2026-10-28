# Revisión de negrita y cursiva — 2026-10-28

Implementación sin fusionar a main: [PAESSED #10](https://github.com/sebinsebon/paessed.cl/pull/10), [skill #5](https://github.com/sebinsebon/paes-importer-skill/pull/5). El ajuste de texto para IA está en [#9](https://github.com/sebinsebon/paessed.cl/pull/9), que conserva el estado de borrador.

## Sincronización y ramas

- PAESSED: main local actualizado por fast-forward de 2d73d6d a d614fcd (12 commits). #8 ya estaba fusionado en GitHub. feat/ensayos-source-selector se conserva aunque ya pertenece a main. feat/ai-question-handoff sigue en borrador. feat/paes-m1-aventura-mvp diverge de main (147 commits solo en main, 20 solo en aventura) y no tiene aprobación vigente para fusionar.
- Skill: main y origin/main coinciden en f47bb4f. Las ramas históricas feat/source-fidelity-review-v1.3.0, fix/source-fidelity-review y fix/stable-1.4.1 ya están incluidas en main. integration/1.5.0 y optimization/documentary-quality conservan la revisión c0d0b71 pendiente, sin PR aprobado. No se integran en esta propuesta.
- Se conservan íntegros los siete archivos locales modificados en la skill original y contract.lock.json/test_source_absence.py en el desarrollo original. No se borran ramas ni se descarta trabajo. La implementación de la skill usa un worktree de su mismo repositorio; no se instala globalmente ni crea una segunda skill mantenida.
- Ningún PR pendiente cumplía todas las condiciones de terminado, aprobado y verificado. No se realizaron fusiones remotas.

## Contrato y comportamiento

El esquema ya admite etiquetas por ser cadenas `text.text`; no se añaden campos ni se modifican los esquemas, sus hashes canónicos, la versión de contenido 0.2.0 o el paquete 0.1.0. La convención amplía explícitamente la interpretación literal de la prosa; se documenta en references/representation.md y en docs/renderer-audit/inline-emphasis.md de la web. Solo pares exactos b/i, sin atributos, equilibrados dentro de un bloque; marcadores mal anidados o incompletos quedan literales. Las entidades HTML no se decodifican. Los cuatro marcadores quedan reservados y los lectores antiguos pueden mostrarlos.

El render crea DOM permitido sin HTML activo. Aplica en Ensayos, Playground, alternativas, explicación/solucionario donde la UI ya permite mostrarlo y texto de celdas. No altera los estados que determinan si se muestra una solución. Búsquedas y resúmenes retiran los marcadores válidos; selección/copias de DOM usan texto visible. La IA retira marcadores de prosa y conserva el LaTeX original.

La versión estable usa PDFium para páginas, glifos y extracción nativa, con transcripción estructurada por el agente. `source-text` ahora devuelve texto original, `styled_text`, runs con nombre/peso/flags de fuente, cajas y advertencias. Si no se alinea exactamente la extracción por carácter, devuelve el texto íntegro sin inventar estilo. Los metadatos desconocidos/contradictorios no fuerzan formato; `format_status` sigue pending. Las instrucciones exigen `TEXT_FORMAT_PENDING` si el cotejo no resuelve la duda.

## Archivos modificados

Skill (7): SKILL.md; references/representation.md; release.json; scripts/importer.py; shared/scripts/content_inventory.py; shared/scripts/pdf_assets.py; viewer/block-renderer.js.

PAESSED (11): lib/imported-question-content.ts; lib/paessed-runtime/block-renderer.js; lib/playground-imports.ts; package.json; tests/paessed-renderer.cjs; tests/playground-imports.cjs; tests/inline-emphasis-fixture.cjs; tests/inline-emphasis.cjs; tests/inline-emphasis.config.cjs; tests/inline-emphasis.spec.cjs; docs/renderer-audit/inline-emphasis.md.

Rama del borrador IA (3): lib/ai-assistance.ts; lib/paessed-runtime/block-renderer.js; tests/ai-assistance.test.mjs.

Desarrollo: tests/test_inline_emphasis.py; scripts/review_inline_emphasis.py; docs/plans/2026-10-28-inline-emphasis.md; este informe; runtime.lock.json. No se distribuyen pruebas, PDFs, capturas o informes con la skill.

## Validación

- Suite estable contra el runtime explícito: 242 pruebas, 4 omitidas por navegador opcional; salida OK. Release, enlaces/documentación, contrato canónico y árbol físico: correctos. Cero archivos cambiados por la suite dentro de runtime.
- Tras habilitar Chromium, 7 pruebas de captura/revisión aprobadas, incluidas las dos que antes requerían navegador.
- 5 regresiones específicas de importación aprobadas: fuentes digital normal/negrita/cursiva/ambas, conservación exacta, metadatos dudosos, PDF rasterizado sin texto nativo, paridad del contrato y ausencia de variables/encabezados falsos por marcadores.
- Web: 26 pruebas aprobadas (lector DOM/seguridad, texto, Playground y recursos), node tests/paessed.cjs correcto y build de producción correcto. Advertencia preexistente de experimental.viewTransition.
- 4 pruebas de UI sobre build de producción: Ensayos y Playground en escritorio/móvil y claro/oscuro, alternativas, fórmulas, celdas y explicación sintética. Capturas revisadas visualmente.
- IA: 6 pruebas aprobadas, incluidos texto marcado, etiquetas incompletas y LaTeX sin modificar. El resto del borrador permanece pendiente de su revisión propia.
- Cotejo PDF sintético/lector portable/PAESSED y pregunta sintética importada; todas las palabras y estilos visibles presentes. Lectura privada de página 5 del PDF local PAES-INVIERNO-M1 2026: los rótulos Paso 1–4 coinciden en negrita. Esta muestra privada solo prueba extracción; no se realizó una importación real por IA ni se publicó su contenido.

## Límites

Las propiedades de fuente pueden ser incompletas o no describir énfasis simulado con trazos, transformaciones o superposición. El extractor no reconstruye fracciones, tablas, columnas ni orden de lectura: el agente debe conservar la estructura mediante cotejo. Los escaneos no ofrecen propiedades tipográficas de texto; solo se admite estilo observado visualmente con claridad. Nunca se infiere por mayúsculas u OCR. La prueba de UI usa estados ficticios para mostrar explicaciones; no acredita revisión de un ensayo real. No se ha marcado contenido como Gold.

Los worktrees se basan en versiones estables; el desarrollo de integración 1.5.0 y sus cambios locales se mantiene separado. Las evidencias privadas y generadas se conservan bajo tmp fuera de Git y del runtime. Los informes de prueba incluyen el comando y los hashes para verificar la pareja exacta.
