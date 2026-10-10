# PAES Importer Skill

Skill portable para **PAES Matemática M1** desde PDF, con solucionario opcional, a ZIP/.paessed. El agente anfitrión interpreta/resuelve; Python renderiza, recorta, valida, conserva trazabilidad y empaqueta. No requiere otra API de IA ni API key adicional.

Repositorio: https://github.com/sebinsebon/paes-importer-skill

## Prompts listos para usar

**Chat web**

> Usa la skill de https://github.com/sebinsebon/paes-importer-skill. Estoy en un chat web. Adjunto el ensayo y, si corresponde, su solucionario. Comprueba tus capacidades, selecciona el modo adecuado y entrégame el ZIP final.

**CLI / agente de terminal**

> Usa la skill de https://github.com/sebinsebon/paes-importer-skill. Estoy en un agente de terminal. Los PDFs están adjuntos o en las rutas indicadas. Comprueba tus capacidades, selecciona el modo adecuado y genera el ZIP final.

El anfitrión debe obtener el bundle completo y leer SKILL.md con sus referencias. Si no puede acceder a GitHub, adjunta el ZIP de la skill. Un enlace o SKILL.md aislado no instala dependencias ni añade herramientas. Para un repo privado usa acceso disponible o bundle, nunca credenciales en el prompt.

La skill pregunta destino: Documentos (por defecto), Descargas o ruta personalizada. En chat web sin acceso al equipo, entrega ZIP descargable y recomienda dónde guardarlo. Selección interactiva cuando exista; opciones numeradas en otras interfaces.

## Modos

| Entorno | Solucionario | Flujo |
| --- | --- | --- |
| Chat web / CLI | Completo y correspondiente | Importación con cotejo durante producción, sin resolver otra vez ni auditoría independiente completa. |
| Chat web | Ausente / parcial | Consentimiento experimental para resolver pendientes; si rechazas, conserva respuestas/explicaciones missing. |
| CLI | Ausente / parcial | Resuelve lo no cubierto; auditoría con subagentes si existen, o autorrevisión explícita. |

Pauta con letras: explicación breve generada por IA. Con justificación: reutilizar/resumir y registrar origen. Pauta parcial: resolver solo faltantes. Incompatible/ambigua: aclarar o continuar sin utilizarla. Validación estructural y autorrevisión no convierten respuestas en verified.

## Instalación

Requisitos: **Python 3.12+ y Node.js 18+**. Validadores JS y sus bibliotecas/licencias ya están incluidos; no necesita npm install.

~~~sh
git clone https://github.com/sebinsebon/paes-importer-skill.git
cd paes-importer-skill
python -B scripts/setup.py
~~~

Windows: .venv/Scripts/python.exe -B scripts/importer.py, o ./run.ps1. Linux/macOS: .venv/bin/python -B scripts/importer.py. También sirve un Python con requirements.txt instalado. setup crea .venv y tmp dentro de este checkout; no borra un entorno existente. Si falla pip, conserva el error y reintenta con el Python ya creado.

El agente puede leer [SKILL.md](SKILL.md) desde esta carpeta. Para descubrimiento en Codex/Claude Code, copia el bundle completo bajo .agents/skills/paes-importer o .claude/skills/paes-importer; prepara dependencias allí o usa otro Python instalado. No es necesario instalar globalmente. [Compatibilidad](docs/COMPATIBILITY.md).

## Operación y salida

El agente sigue [workflow](references/workflow.md), localiza preguntas, asocia pauta y produce contenido; prepare no resuelve automáticamente. [Interfaces](references/interfaces.md) de lote, pauta y cotejo. [Auditoría](references/audit.md) cuando corresponda.

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

Descargas usa igual estructura; ruta personalizada sustituye la raíz EnsayosPaessedOutput, sin agregarla otra vez. Windows respeta carpetas redirigidas y Linux XDG. No sobrescribir ejecuciones. ZIP lleva final.json, manifest.json y PNG usados; no PDF original ni .work.

## Pruebas y bundle para chat

Para preparar dependencias de desarrollo en un clon nuevo: python -B scripts/setup.py --dev. Si ya hay entorno, usar su Python con -m pip install -r requirements-dev.txt.

Con el Python preparado:

~~~sh
python -B -m unittest discover -s tests -v
python -B scripts/release.py
python -B scripts/make_bundle.py --output /ruta/absoluta/paes-importer.zip
~~~

Pruebas con PDFs ficticios: render, crops, modos, pauta, cotejo, auditoría, reanudación y paquete. No necesitan PDFs privados, outputs históricos ni modelos. [Verificación](docs/VERIFICATION.md).

Fuentes ficticias para demos: python -B examples/synthetic.py --output tmp/demo. No son ensayos reales ni resultados de IA. El release fija hashes; un cambio intencional exige regenerar con python -B scripts/release.py --write y preparar nuevas ejecuciones. No cambiar hashes para reanudar silenciosamente una corrida vieja.

## Límites y licencia

Solo M1. Formato histórico paessed-benchmark/0.1.0 compatible con el lector local; no integra PAESSED Web. Las declaraciones de lectura y revisión no autentican comprensión o independencia. Tokens/costo no disponibles son null; no derivar precisión de estados verified.

Pruebas sintéticas no acreditan funcionamiento real de todos los chats/modelos/CLI. [Compatibilidad y pruebas manuales](docs/COMPATIBILITY.md). [Decisiones y mejoras](docs/DECISIONS.md).

Código MIT. JSZip/KaTeX preservan licencias y atribuciones: [NOTICE](NOTICE.md). No agregar PDFs privados, resultados derivados, recortes de ensayos ni credenciales.
