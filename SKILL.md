---
name: paes-importer
description: Importa ensayos PAES Matemática M1 PDF, con solucionario opcional, a ZIP/.paessed; selecciona un flujo para chat web o agente CLI según la cobertura de la pauta y las capacidades observadas.
license: MIT
metadata:
  requires: Comprobar lectura visual, bundle completo, Python 3.12+, Node.js 18+ y capacidad de entregar ZIP.
---

# Importador PAESSED M1

## Primero: confirmar el entorno

Antes de abrir referencias, flujos o PDFs, comprueba si el usuario ya indicó **Chat Web** o **CLI / agente de terminal** en esta conversación. Si lo indicó, usa esa respuesta sin volver a preguntar. Si no lo indicó o es ambiguo, pregunta: **«¿Dónde estás usando la skill: Chat Web o CLI / agente de terminal?»** Ofrece esas dos opciones y espera su respuesta antes de continuar. Mientras esperas, lee únicamente este SKILL.md; no cargues otros archivos ni ejecutes preparación o pruebas de capacidades. No deduzcas el entorno solo porque existan Python o herramientas de terminal.

PAESSED necesita una transcripción fiel de cada pregunta, con matemática, tablas, imágenes, alternativas, respuesta y explicación. Esta skill produce un ZIP y un .paessed idéntico conforme al [contrato del paquete](shared/references/package-contract.md). El agente interpreta el PDF; los scripts incluidos preparan, validan y empaquetan. Esta versión cubre Matemática M1 y el lector local, sin acreditar integración con PAESSED Web. **Regla de entrega:** en Chat Web genera el ZIP en el espacio temporal disponible y adjúntalo directamente a la conversación como archivo descargable. Nunca preguntes dónde guardar archivos ni solicites rutas/carpetas al usuario web. En CLI sí puedes solicitar Documentos, Descargas o una ruta personalizada. Esta regla prevalece sobre instrucciones generales de destino.

## Elegir un solo flujo

1. Localiza esta carpeta y el bundle completo. Identifica el ensayo M1, sus páginas y cualquier pauta separada o integrada. Si solo hay respuestas sin enunciados completos, solicita el ensayo. Ante varios ensayos, identifica la asociación antes de continuar.
2. Comprueba con observaciones concretas las herramientas disponibles para leer páginas y visuales, recortar, ejecutar Python/Node, validar, crear y entregar un ZIP. El nombre «chat web» o «CLI» no demuestra ni descarta capacidades. Si falta una capacidad indispensable, explica cuál y conserva el trabajo realizado; no sustituyas el formato PAESSED.
3. Comprueba la correspondencia de la pauta con identidad, numeración, alternativas y evidencia visible. Haz un mapa de todas las preguntas para conocer su cobertura. Una pauta ambigua o incompatible no cuenta como válida; registra la discrepancia y pide la asociación correcta cuando sea necesaria. La pauta parcial cubre solo sus preguntas documentadas.
4. Selecciona la fila correspondiente y lee **solo** su WORKFLOW.md. No cargues los otros tres flujos. Dentro del flujo, consulta únicamente las referencias comunes que indique.

| Entorno de trabajo | Cobertura válida de la pauta | Leer |
| --- | --- | --- |
| Chat web | Todas las preguntas | [01 Chat con solucionario](flows/01-chat-con-solucionario/WORKFLOW.md) |
| CLI | Todas las preguntas | [02 CLI con solucionario](flows/02-cli-con-solucionario/WORKFLOW.md) |
| CLI | Ausente o parcial | [03 CLI sin solucionario completo](flows/03-cli-sin-solucionario/WORKFLOW.md) |
| Chat web | Ausente o parcial | [04 Chat sin solucionario completo](flows/04-chat-sin-solucionario/WORKFLOW.md) |

Una pauta válida y parcial conserva sus respuestas y explicaciones cubiertas; el flujo 03 o 04 trata únicamente las preguntas pendientes. Si la asociación es ambigua, no inventes cobertura para elegir un flujo rápido. Elige el anfitrión por el lugar donde se realiza el trabajo: un chat web con ejecución de código sigue el flujo web.

El [contrato de contenido](shared/references/content-contract.md) y el cotejo con el PDF rigen los cuatro flujos. Conserva las verificaciones de enunciados, alternativas, matemática, tablas, imágenes, respuestas y explicaciones. No promociones una autorrevisión o una pauta copiada a verified.
