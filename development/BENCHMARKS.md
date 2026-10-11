# Estado de benchmarks

Las herramientas de inventario Gold, comparación por dimensiones y evaluación de ejecuciones existentes están implementadas con pruebas sintéticas. No se ejecutaron importaciones reales de IA como tests de implementación.

| Evidencia | Estado |
|---|---|
| Inventario TESLA y paquete derivado compatible | Preparado en tmp/gold/; originales intactos |
| Revisión matemática independiente de 65 preguntas | Pendiente |
| Adjudicación de ambigüedades del original | Pendiente |
| Certificación visual y web | Pendiente |
| Comparador sintético e integridad de inventario | Pruebas disponibles |
| Accounting de llamadas individuales | Pruebas disponibles; desconocidos permanecen null |
| Corpus independiente digital y escaneado | Por curar |
| Conjunto sellado | Por curar |
| Experimentos reales repetidos de los cuatro flujos | No ejecutados |
| Ahorro de tokens o tiempo | No demostrado |

No se informa una tasa de accuracy ni un ahorro de eficiencia. Para registrar una campaña, conservar manifiesto, hashes de fuentes/release, outputs, mediciones reales, informes comparativos y adjudicaciones bajo tmp/. Seguir benchmark-protocol.md. La CI usa exclusivamente fixtures ficticios; las herramientas de mantenimiento no incorporan contenido privado al release.
