# Verificación de implementación

Comprobación local del bundle portable, 2026-10-10. Se utilizan únicamente fuentes ficticias generadas por examples/synthetic.py. No se ejecutan modelos ni se usan PDFs privados/outputs de V1 o V2 como fixtures.

La suite recorre las rutas con pauta completa/parcial/ausente; consentimiento web; autorrevisión; auditoría de todo el ensayo o solo faltantes; conservación exacta del baseline; evidencia ampliada; lectura completa; procedencia de respuestas/explicaciones; fórmulas/tablas/recortes y alternativas visuales; hashes/ZIP; destinos; reanudación y rechazo de cambios.

El lector real JavaScript y KaTeX se ejecutan en los recorridos de empaquetado. Las pruebas de vínculos dependen del sistema: Windows puede omitir symlink por privilegios, pero comprueba junction; Linux/macOS comprueban symlink y omiten junction Windows.

Entorno local: Windows, Python 3.14.0 en la .venv propia de este repositorio, dependencias directas/transitivas fijadas y Node 22.22.3. Una copia limpia fuera de la estructura Final/V1/V2 se comprueba sin artefactos históricos. El código no depende del lugar de ese intérprete; otros equipos deben instalar requirements.txt.

Validación de SKILL.md con quick_validate.py y release con hashes. GitHub Actions está preparado para Windows/Linux con Python 3.12/3.14 y Node 22; esa matriz remota no ha sido ejecutada todavía. No afirmar compatibilidad real con modelos/CLI/chats a partir de esta suite.

Resultado final: 43 pruebas ejecutadas, 42 aprobadas y 1 omitida (symlink Windows sin privilegios); junction comprobado y aprobado. La suite también pasó desde una copia limpia del bundle, con el entorno propio y sin fuentes/resultados históricos. SKILL.md pasó quick_validate.py. Release: 44 archivos verificados; bundle: esos archivos más release.json. Los logs completos permanecen en tmp/verification y no se distribuyen.
