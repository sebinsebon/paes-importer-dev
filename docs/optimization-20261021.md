# Optimización documental del importador

El candidato se mantiene en `paes-importer-skill`, rama `integration/1.5.0`;
las pruebas y herramientas permanecen en `paes-importer-dev`, en la rama del
mismo nombre. La [consolidación de los worktrees](worktree-consolidation-20261021.md)
conserva commits y artefactos históricos. No se incluyen PDFs privados, importaciones reales
ni modificaciones de TESLA RC3. La referencia de fidelidad requiere adjudicación
documental: el Gold declarado por ejecuciones anteriores no la sustituye.

## Trabajo implementado

- P0: operaciones con identificador, intervalos, resultado semántico y preguntas;
  recibos de proveedor separados de llamadas totales desconocidas; importación de
  eventos del anfitrión y tiempo desde la solicitud.
- P0: índice nativo por hash, consulta regional y contexto completo por lote con
  plantillas, pauta e inventario del desarrollo; máximo habitual cinco preguntas,
  reducción por complejidad y conservación de aceptados.
- P0: prueba inicial observable de renderer; artefacto visual obligatorio tanto
  para HTML como imágenes; citas prellenadas con veredictos pendientes; señales
  nativas adjudicadas individualmente antes de aprobar.
- P0: adopción explícita de checkpoint parcial compatible en carpeta nueva;
  verificación de ambos runtimes y fuentes; continuaciones de cualquier fuente
  registrada, sin límite arbitrario de páginas, con invalidación localizada.
- P1: candidatos de figura por objetos, trazos y rótulos, límites de exclusión y
  diagnósticos de bordes/texto ajeno; ninguna heurística concede fidelidad.
- P1: señales de matemática en prosa/tablas/alternativas/desarrollos y comparación
  de cobertura textual contra regiones de solucionario; renderer conservado.
- P1: vistas por pregunta y dependencias, páginas renderizadas en caché por hash,
  regiones pertinentes con contexto completo y capturas reanudables sin alterar
  constancias anteriores.
- P2: imágenes nativas candidatas sin materialización por defecto, materialización
  selectiva, exportación autosuficiente y reproducibilidad de distribución.

Los paths de recursos publicados permanecen únicos como exige el contrato.
Materializar solo lo usado evita copias de logos sin modificar ese contrato.
Los checkpoints preservan originales e informes históricos; excluir copias no
referenciadas del archivo exportado no borra el historial de la ejecución.

El validador canónico `shared/scripts/package_io.py` conserva todas sus reglas y
admite un contexto de caché opcional por operación. La ingestión usa ese contexto
para propuestas individuales y vuelve a validar el candidato completo con bytes
frescos antes del commit. Se revisó la diferencia y se respaldaron validador,
manifiesto y lock originales en `backups/normative-validation-cache-20261021/`
antes de sincronizar la copia canónica y actualizar `contract.lock.json`.
Los esquemas, contratos documentales y versiones 0.2.0/0.1.0 no cambiaron.

## Medición reproducible

El evaluador `scripts/benchmark.py` acepta `requested_at`, `finished_at`,
`importer_events` y `host_events` por ejecución. Las fechas incluyen zona horaria;
los archivos de eventos son JSON con lista/objeto `events`, o JSONL. Se conservan
hashes de los registros importados. Cada intervalo observado contiene categoría
`importer`, `auxiliary`, `provider`, `backoff` o `pause`, `started_at` y
`finished_at`. `operation_id` identifica una operación y `phase:start` no se suma
de nuevo. `retry_count` y `announced_backoff_seconds` son observaciones separadas;
backoff anunciado no acredita tiempo dormido. Los mensajes de logs sin intervalos
pueden conservarse como observaciones; no se inventan tiempos a partir de ellos.

Los archivos `.log` admiten los registros de reintento AGY `Run: attempt ...
failed (...), retrying in ...s`. Conservan causa, línea, intento y backoff anunciado,
con intervalos desconocidos. `host_log_context:{year,utc_offset}` permite fechar
el registro local sin adivinar año/zona; omitirlo mantiene timestamp `null`.
Otros anfitriones exportan los eventos normalizados JSON/JSONL.

El tiempo de pared parte de la solicitud del usuario. Sin sus extremos permanece
`null`; los tiempos de comandos y proveedor no lo reemplazan. Los solapamientos
entre categorías y los huecos permanecen sin atribuir. `calls` se conserva como
alias histórico del número de recibos; `provider_receipts_count` es el nombre
explícito y `total_provider_calls:null` evita afirmar cero llamadas.

Una comparación exige pares, referencia documental y metadatos coincidentes:
host, modelo, esfuerzo, capabilities_sha256, generation_config_sha256,
sources_sha256, environment_sha256 y batch_policy_sha256. `sources_sha256` liga
el registro ordenado de fuentes y hashes. `environment_sha256` liga navegador,
dependencias, sistema, política y estado inicial de cachés. `batch_policy_sha256`
liga límites, complejidad y política de reintentos. Se registran sus documentos
originales junto a cada campaña; declarar un hash no autentica el anfitrión.
La revisión del runtime se registra por separado para permitir compararla.

Se publican fallidos e interrumpidos. Menos de tres repeticiones pareadas con
tiempos completos produce `inconclusive`. Aun con tres, la mediana es descriptiva
y exige adjudicación independiente de fidelidad antes de atribuir una mejora.
No se transforman caracteres en tokens ni subtotales conocidos en totales.

## Puertas de aceptación

La suite sintética comprueba contrato 0.2.0/paquete 0.1.0, cuatro flujos, crops,
inventarios, matemática, procedencia, recuperación, capturas y Gold documental.
La campaña real posterior debe comprobar las 65 preguntas/260 alternativas,
figura completa sin duplicación y desarrollo íntegro contra ensayo y pauta.
Esas propiedades de TESLA no se certifican ejecutando fixtures sintéticos.

No se ha ejecutado una campaña real de inferencia ni se afirma reducción de la
mediana hasta una entrega aceptable. Publicación y campañas reales posteriores
permanecen fuera de esta implementación.

## Resultado de verificación local

Runtime fijado: `c0d0b719e26a2f42133a038514989d62c74f7023`, candidato
`1.5.0-portable`. SHA-256 del manifiesto:
`91dc842758faf47d56119cda054d5458e942527764f650ec8ead5014d7e0456a`.

`scripts/check.py` completó 304 pruebas sin fallos; dos se omitieron por falta de
privilegios de enlaces simbólicos en Windows. Pasaron documentación, manifiesto,
contrato canónico y árbol físico, sin escrituras en el runtime durante la suite.
El informe se conserva en `results/optimization-complete-20261021.json`. La
verificación corresponde a los mismos bytes del manifiesto fijado posteriormente
en el commit local. Chrome real se habilitó mediante PAES_TEST_BROWSER; la
adopción sintética entre el runtime 1.4.1 real y el candidato se habilitó con
PAES_TEST_LEGACY_RUNTIME. No se ejecutó una matriz remota de sistemas operativos.

La prueba visual real por memoria conserva `question.png`, `probe.png` y hashes
en `results/visual-smoke-final-20261021/`. Se inspeccionaron texto, fórmula inline,
fórmula de bloque, tabla, figura y regiones/contexto. Es QA del renderer con
contenido ficticio; no certifica fidelidad de un ensayo real.

Tres repeticiones pareadas y alternadas del benchmark determinista se conservan
en `results/operations-final-20261021/report.json`:

| Operación / mediana | 1.4.1 | Candidato |
| --- | ---: | ---: |
| Preparar tres páginas ficticias | 118,89 ms | 120,76 ms |
| Diez consultas nativas | 15,81 ms | 38,08 ms |
| Segunda vista sin cambios | 116,44 ms | 92,43 ms |
| Bytes de imágenes materializadas inicialmente | 468 | 0 |
| Bytes de respuesta de diez consultas | 3.230 | 5.150 |

La nueva consulta verifica el índice y expone más trazabilidad; en esta muestra
pequeña cuesta más que reabrir un PDF mínimo. La vista vigente se reutiliza y las
imágenes quedan diferidas. Estos resultados mixtos no demuestran ahorro total,
de tokens ni del tiempo hasta una entrega aceptable. La conclusión para
importaciones reales permanece **inconclusa**.

Dos construcciones de `releases/paes-importer-1.5.0-candidate.zip` y su réplica
produjeron bytes idénticos: 133 entradas, 2.134.750 bytes, SHA-256
`d13694fa67f7246623dc9c2888e1c464cbf633da348b860c8e8b310068174a21`.
La distribución contiene solo el payload permitido y su manifiesto.

Las 65 preguntas/260 alternativas de TESLA, su figura equivalente al caso de
regresión y el desarrollo íntegro del solucionario requieren la campaña privada
documental posterior. TESLA RC3 y los resultados históricos se conservaron.
