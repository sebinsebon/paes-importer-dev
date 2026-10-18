# PAES Importer Skill

Skill portable para **PAES Matemática M1** desde PDF, con solucionario opcional, a .paessed 0.2.0 y ZIP idéntico. El agente anfitrión interpreta/resuelve; Python renderiza, recorta, valida, conserva trazabilidad y empaqueta. No requiere otra API de IA ni API key adicional.

Repositorio: https://github.com/sebinsebon/paes-importer-skill

**Para el agente:** comienza por [SKILL.md](SKILL.md), comprueba capacidades y cobertura del solucionario y lee únicamente el flujo seleccionado. Cada flujo enlaza los recursos comunes que necesita. Los informes y tests de mantenimiento no son parte del bundle.

Si el usuario no indicó Chat Web o CLI, la primera acción es preguntarlo y esperar su respuesta antes de abrir PDFs, referencias o flujos. Si ya lo indicó en la conversación, continúa sin repetir la pregunta.

## Prompts listos para usar

**Chat web**

> Usa la skill de https://github.com/sebinsebon/paes-importer-skill. Estoy en un chat web. Adjunto el ensayo y, si corresponde, su solucionario. Comprueba tus capacidades, selecciona el modo adecuado y entrégame el paquete .paessed final y su ZIP idéntico.

**CLI / agente de terminal**

> Usa la skill de https://github.com/sebinsebon/paes-importer-skill. Estoy en un agente de terminal. Los PDFs están adjuntos o en las rutas indicadas. Comprueba tus capacidades, selecciona el modo adecuado y genera el paquete .paessed final y su ZIP idéntico.

El anfitrión debe obtener el bundle completo y leer SKILL.md con sus referencias. Si no puede acceder a GitHub, adjunta el ZIP de la skill. Un enlace o SKILL.md aislado no instala dependencias ni añade herramientas. Para un repo privado usa acceso disponible o bundle, nunca credenciales en el prompt.

**Chat Web:** no pregunta dónde guardar archivos; genera el .paessed y el ZIP idéntico en la carpeta temporal disponible y los adjunta directamente a la conversación para descargar. **CLI:** pregunta solo si falta un destino explícito: Documentos (por defecto), Descargas o ruta personalizada. Nunca afirmes que un chat ha escrito archivos en el equipo del usuario.

## Modos

| Entorno | Solucionario | Flujo |
| --- | --- | --- |
| Chat web | Completo y correspondiente | [01 Chat con solucionario](flows/01-chat-con-solucionario/WORKFLOW.md): importación directa y .paessed/ZIP descargables. |
| CLI | Completo y correspondiente | [02 CLI con solucionario](flows/02-cli-con-solucionario/WORKFLOW.md): importación con lectura visual según las capacidades. |
| CLI | Ausente o parcial | [03 CLI sin solucionario completo](flows/03-cli-sin-solucionario/WORKFLOW.md): resolver solo pendientes y auditar cuando existan revisores independientes. |
| Chat web | Ausente o parcial | [04 Chat sin solucionario completo](flows/04-chat-sin-solucionario/WORKFLOW.md): comprobar viabilidad y solicitar consentimiento experimental. |

Pauta con letras: explicación breve generada por IA. Con justificación: reutilizar/resumir y registrar origen. Pauta parcial: resolver solo faltantes. Incompatible/ambigua: aclarar o continuar sin utilizarla. Validación estructural y autorrevisión no convierten respuestas en verified.

Las explicaciones se entregan como texto y matemática editables; las imágenes conservan diagramas necesarios. Las nuevas ejecuciones registran un inventario observado de figuras/tablas/matemática antes de transcribir y generan una vista fuente/resultado mediante `review --run RUN`. El agente debe abrirla y cotejar cada pregunta y recorte antes de registrar los controles. Los hashes invalidan revisiones de contenido o imágenes modificados. Con pauta completa, los cotejos pendientes bloquean la publicación; los otros flujos conservan entregas parciales explícitas. Consulta la [operación común](references/workflow.md).

## Instalación

Requisitos: **Python 3.12+ y Node.js 18+** (`node` disponible en PATH). Validadores JS y sus bibliotecas/licencias ya están incluidos; no necesita npm install. El instalador descarga las dependencias Python fijadas en requirements.txt; para instalación sin red, deben estar disponibles en el entorno o en un repositorio de paquetes configurado por el usuario.

~~~sh
git clone https://github.com/sebinsebon/paes-importer-skill.git
cd paes-importer-skill
python -B scripts/setup.py
~~~

Windows: .venv/Scripts/python.exe -B scripts/importer.py, o ./run.ps1. Linux/macOS: .venv/bin/python -B scripts/importer.py. También sirve un Python con requirements.txt instalado. setup crea .venv y tmp dentro de este checkout; no borra un entorno existente. Si falla pip, conserva el error y reintenta con el Python ya creado.

Los ejemplos con rutas relativas parten de la carpeta que contiene SKILL.md. `python` debe ser el intérprete con las dependencias instaladas: sustituye ese comando por `.venv/Scripts/python.exe` en Windows o `.venv/bin/python` en Linux/macOS si no activaste el entorno. Desde otra carpeta usa las rutas absolutas del intérprete y del script; en PowerShell invoca rutas entre comillas con `&`. Los scripts encuentran sus recursos desde su ubicación, aunque la ruta contenga espacios o acentos.

Para trasladar o compartir la skill, utiliza el clon o el bundle completo. `.venv` pertenece a cada instalación: sus ejecutables y scripts de activación pueden guardar rutas absolutas y debe recrearse en la nueva ubicación con setup.py, conservando primero el entorno anterior fuera de `.venv` si existe. No copies entornos virtuales entre equipos. Los PDFs y las salidas se eligen explícitamente; las ejecuciones guardan sus rutas originales para reanudación y auditoría, por lo que trasladar el código no migra ejecuciones existentes.

El agente puede leer [SKILL.md](SKILL.md) desde esta carpeta. Para descubrimiento en Codex/Claude Code, copia el bundle completo bajo .agents/skills/paes-importer o .claude/skills/paes-importer; prepara dependencias allí o usa otro Python instalado. No es necesario instalar globalmente. [Compatibilidad](references/hosts.md).

## Operación y salida

El agente sigue el flujo seleccionado por SKILL.md. Los cuatro reutilizan la [operación común](references/workflow.md), las [interfaces](references/interfaces.md) y los contratos; prepare no resuelve automáticamente. El flujo 03 usa [auditoría](references/audit.md) cuando corresponde.

~~~text
Documentos/EnsayosPaessedOutput/
  m1-<nombre-observado>/
    <fecha-hora>-<id>/
      m1-<nombre-observado>.zip
      m1-<nombre-observado>.paessed
      final.json
      candidate.json
      assets/
      run.json
      .work/
~~~

Descargas usa igual estructura; ruta personalizada sustituye la raíz EnsayosPaessedOutput, sin agregarla otra vez. Windows respeta carpetas redirigidas y Linux XDG. No sobrescribir ejecuciones. .paessed y ZIP llevan final.json 0.2.0, manifest.json 0.1.0 y PNG usados; no PDF original ni .work.

## Crear el ZIP de la skill para compartir

Con Python y Node.js preparados en esta instalación:

~~~sh
python -B scripts/release.py
python -B scripts/make_bundle.py --output /ruta/absoluta/paes-importer.zip
~~~

El bundle contiene las instrucciones, herramientas y recursos operativos de la skill. No incluye tests, ejemplos sintéticos, informes de desarrollo, configuraciones de CI ni entornos virtuales. Cada anfitrión necesita Python/Node y dependencias disponibles; el ZIP no instala herramientas ni garantiza lectura visual.

## Límites y licencia

Solo M1. Salida oficial paessed-benchmark/0.2.0; lectura histórica 0.1.0. El consumidor local paesseduiux admite el contrato, con estados y reservas visibles; esto no acredita importaciones reales en todos los hosts ni certificación Gold. Las declaraciones de lectura y revisión no autentican comprensión o independencia. Tokens/costo no disponibles son null; no derivar precisión de estados verified.

Pruebas sintéticas no acreditan funcionamiento real de todos los chats/modelos/CLI. [Compatibilidad por entorno](references/hosts.md).

Código MIT. JSZip/KaTeX preservan licencias y atribuciones: [NOTICE](NOTICE.md). No agregar PDFs privados, resultados derivados, recortes de ensayos ni credenciales.


## Contrato curricular 0.2.0

Toda nueva importación M1 incorpora questions[].curriculum = {eje, subeje, en_temario}. Clasificar automáticamente cada pregunta por su contenido usando los cuatro ejes y 16 subejes de shared/references/curriculum-m1.json; consultar shared/references/curriculum-contract.md para pertenencia, evidencia y pendientes. No copiar la taxonomía de TESLA ni inferir desde numeración. Cada lote añade curriculum_provenance[id] con reason y evidence [{source_id,page,observation}]. Clasificar también preguntas sin pauta o cuya resolución experimental se rechazó. Conservar la incertidumbre como dudoso; un par null requiere CURRICULUM_PENDING y entrega curricular parcial. Los lectores admiten finales históricos 0.1.0 sin inventar clasificación; el manifiesto del paquete sigue en 0.1.0.

El contrato canónico se mantiene en `contrato/0.2.0` del espacio PAESSED; la skill distribuye copias verificadas por hash y funciona de forma independiente. `draft.json` v1 sigue siendo un artefacto interno del extractor previo; no es un paquete final. Para incorporarlo a una ejecución preparada y mapeada, consulta `adapt-draft` en [interfaces](references/interfaces.md#draftjson-v1-del-extractor-previo).
