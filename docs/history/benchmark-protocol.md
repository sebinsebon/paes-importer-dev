# Protocolo reproducible de evaluación

## Corpus y condiciones

Gold documental exige cotejo visual vigente del ensayo y solucionario disponible; no exige segunda resolución ni estados matemáticos `verified`. La declaración de Gold de una ejecución no certifica por sí sola la referencia. TESLA RC3 permanece de solo lectura; adjudicar cualquier referencia propuesta antes de compararla. Curar dos ensayos M1 adicionales: uno digital y otro escaneado/con mayor complejidad visual. Incluir pauta completa, parcial, integrada y ausente; guardar al menos un conjunto sellado que no se use para ajustar prompts. Las anotaciones se adjudican documentalmente. Datos reales permanecen fuera de Git y bundle, bajo tmp/ o en sus ubicaciones de solo lectura.

Congelar Skill/release, modelo, esfuerzo, anfitrión, capacidades, fuentes y configuración. Ejecutar primero la línea base, después las correcciones de fidelidad y después cada optimización por separado. Comparar producción con lotes 1, 3 y 5; revisión con 1, 5 y 10. Tres repeticiones por condición finalista. Una estrategia puede reducir llamadas y aumentar errores: ambos resultados deben publicarse. No comparar capacidades distintas como si fueran la misma condición.

Preparar recursos, índices y cachés solo por hash de fuente + región + escala/configuración. Un índice o resumen compacto debe permitir volver al PDF, sin sustituir evidencia obligatoria. Medir el contexto enviado y las relecturas. Ante fallo de lote, medir preguntas aceptadas/rechazadas y reintentos; no contabilizar una ejecución interrumpida como éxito.

## Evaluador de ejecuciones existentes

La instrumentación vigente, hashes adicionales de condiciones, tiempo desde la
solicitud y límites de atribución se describen en
[el protocolo de optimización](../optimization-20261021.md#medición-reproducible).

scripts/benchmark.py no hace llamadas a modelos ni importa ensayos. Consume un manifiesto JSON de importaciones ya producidas y uso real de proveedores:

~~~json
{
  "runs": [
    {
      "id": "baseline-repeat-1",
      "status": "completed",
      "gold": "reference.paessed",
      "candidate": "candidate.paessed",
      "gold_taxonomy": "annotations.json",
      "id_map": "identity-map.json",
      "metadata": {
        "pair_id": "exam-a-repeat-1",
        "host": "cli",
        "model": "declared-model",
        "effort": "declared-effort",
        "capabilities_sha256": "hash-of-observed-host-capabilities",
        "generation_config_sha256": "hash-of-provider-generation-settings",
        "release_sha256": "recorded-release-hash",
        "strategy": "baseline",
        "production_batch_size": 3,
        "review_batch_size": 5
      },
      "usage": [
        {
          "event_id": "unique-provider-call-id",
          "input_tokens": null,
          "output_tokens": null,
          "cost": null,
          "currency": "USD",
          "duration_seconds": null
        }
      ]
    }
  ]
}
~~~

Los nombres son ficticios. Omitir gold_taxonomy e id_map cuando no correspondan. Rutas relativas se resuelven contra el manifiesto. Un certificado opcional se suministra mediante certification, con reference_sha256 igual al hash de gold y status explícito. El evaluador comprueba la vinculación y declara que no realiza esa revisión. Sin certificado no supone que la referencia esté certificada.

status admite completed, failed e interrupted. Las últimas dos conservan failure_reason y uso medido, sin comparación ni éxito ficticio. Cada evento representa una llamada individual: no mezclar sumas de coordinador/worker con sus llamadas. event_id debe ser único en todo el informe. Falta de exposición de tokens/costo se mantiene null. Los subtotales conocidos aparecen separados y un total solo existe si todos los eventos tienen la medida. No inferir tokens desde caracteres. Cada costo medido exige currency en su evento; el evaluador rechaza monedas diferentes en el mismo manifiesto.

~~~powershell
.venv/Scripts/python.exe -B scripts/benchmark.py --manifest tmp/experiment/manifest.json --output tmp/experiment/report.json
.venv/Scripts/python.exe -B scripts/benchmark.py --manifest tmp/experiment/optimized.json --baseline-report tmp/experiment/report.json --output tmp/experiment/optimized-report.json
~~~

Las salidas requieren una ruta nueva dentro de tmp/, sin enlaces ni sobrescritura. Los ahorros son descriptivos y solo se calculan cuando están presentes mediciones completas y coinciden referencia, pares de repetición, anfitrión, modelo, esfuerzo, capacidades y ajustes de generación del proveedor. Faltar cualquiera de esos hashes impide calcular ahorros comparables. El conjunto sellado, las decisiones de anotación y el trabajo humano siguen siendo requisitos del experimento, no inferencias del script.

## Métricas y puertas

Publicar denominadores, diferencias por dimensión, preguntas sustituidas/omitidas, signos/índices/exponentes/denominadores, opciones/orden/claves, tablas, cobertura/legibilidad visual, corrección de explicación y acuerdo curricular. Separar las abstenciones de los aciertos. Reportar tiempos, llamadas, tokens medidos, relecturas, reintentos y minutos de revisión humana por ensayo/flujo/condición con dispersión.

El comparador es una herramienta de triage: diferencias literales no equivalen necesariamente a errores y coincidencia no prueba semántica. El informe no asigna accuracy ni promoción automática. La aceptación final exige adjudicación de diferencias y cero sustituciones/corrupciones críticas aceptadas en el corpus observado, conservación contractual y sin regresión crítica. Meta de ahorro: 15 % en tokens medidos o tiempo, sujeta a esas puertas. Si la muestra no permite concluir, declarar el límite.

## OCR matemático y CAS (O5)

La experimentación es opcional tras observar errores residuales que la justifiquen. Prototipos aislados, sin dependencias en runtime: OCR propone lectura y señala diferencias; CAS contrasta cálculos con dominio explícito. Evaluar falsos positivos, casos fuera de dominio, costo y beneficio en el corpus. Ninguno puede corregir automáticamente operaciones intencionalmente erróneas del enunciado ni promocionar fidelidad. Promover una dependencia requiere resultados reproducibles y una decisión explícita posterior.
