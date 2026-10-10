# Compatibilidad

SKILL.md funciona como instrucciones cuando el anfitrión puede leer las referencias y ejecutar el bundle. Instalar una skill no garantiza lectura visual ni otras capacidades.

| Anfitrión | Estado de este bundle |
| --- | --- |
| AGY | V1 histórica tuvo uso real; corrida portable pendiente. |
| Codex CLI/app | Adaptación preparada; corrida real pendiente. |
| Claude Code | Adaptación preparada; corrida real pendiente. |
| Chat web con archivos/código | Ruta descargable y consentimiento preparados; prueba real pendiente. |
| Chat solo texto o sin visuales/ZIP | No puede completar este pipeline; debe informar lo faltante. |

No confundir pruebas sintéticas con pruebas reales de productos. Las herramientas dependen de cuenta/sesión; observarlas al comenzar. Leer texto de un PDF no implica comprender sus gráficos.

Codex: bundle completo bajo .agents/skills/paes-importer o lectura explícita por ruta. Para independencia, agentes sin historial heredado (fork_turns=none donde exista esa API), solo su lote e instrucciones mínimas. Fuentes oficiales: https://learn.chatgpt.com/docs/build-skills y https://learn.chatgpt.com/docs/agent-configuration/subagents.

Claude Code: bundle completo bajo .claude/skills/paes-importer o lectura explícita. Usar un subagente nuevo por lote; evitar forks que hereden historial productor. Fuentes oficiales: https://code.claude.com/docs/en/skills y https://code.claude.com/docs/en/sub-agents.

Chat web: obtener bundle, ejecutar Python/Node en workspace cuando estén disponibles, recortar y entregar enlace ZIP. Si no dispone de dependencias y no puede prepararlas, informar impedimento. Esperar consentimiento cuando falte pauta. Sin acceso al equipo, el destino local se elige al descargar.

## Prueba manual posterior

Usar M1/pautas autorizados y ejecuciones separadas por anfitrión. Comprobar pauta completa/parcial/ausente, procedencia, visuales, cobertura y paquete. Observar pregunta de destino, consentimiento, contexto y subagentes. Registrar herramientas/modelo/sesión reales, uso disponible y errores (medidas desconocidas null). Revisar contra fuentes con evaluador distinto; no usar informes internos como pauta externa. Actualizar tabla solo con evidencia. No ejecutar corridas reales durante implementación.
