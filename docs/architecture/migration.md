# Migración local y reversión

## Árbol mantenido

```text
Paessed.cl/
  paes-importer-skill/         # repositorio oficial; único runtime mantenido
    SKILL.md
    flows/                    # cuatro WORKFLOW.md
    references/               # instrucciones de operación
    scripts/                  # entrada, instalación y verificación
    shared/                   # módulos, contratos, esquemas
    viewer/                   # renderer y bibliotecas locales con licencia
    requirements*.txt
    README.md, NOTICE.md, LICENSE, release.json
    .git/, .github/, .gitignore, .gitattributes
  paes-importer-dev/           # repositorio local de mantenimiento
    tests/, examples/, scripts/
    docs/history/, docs/architecture/
    distribution.json, contract.lock.json, runtime.lock.json
    .github/, .git/, requirements-dev.txt
    backups/, results/, releases/, experiments/, caches/, tmp/, .venv/
```

La última línea de desarrollo es privada e ignorada por Git. No se publica un ZIP
del directorio de desarrollo. `distribution.json` identifica cada archivo del ZIP
operativo, sin globs ni navegación por carpetas privadas. `release.json` conserva
hashes de esos mismos bytes. El runtime nunca importa módulos del desarrollo.

## Evidencia antes y después

`backups/pre-separation.bundle` conserva las seis referencias originales y su
historial completo. `backups/pre-separation/tracked-manifest.json` fija los 173
archivos originales, incluso cambios locales anteriores a esta migración. Las
carpetas tmp, entorno anterior y cachés residuales tienen manifiestos propios. La
junction archivada se conserva como enlace, sin copiar ni recorrer su destino.

La separación fue comprobada con las 159 pruebas originales antes de reparar
funciones. `scripts/verify_backups.py` vuelve a comprobar cada archivo respaldado,
la existencia de los métodos de prueba originales y los hashes de TESLA RC3.
Los informes del runner incluyen el árbol físico operativo antes y después.

El respaldo `backups/canonical-before` conserva el manifiesto, herramienta y 19
recursos originales del contrato. Los esquemas y catálogo permanecen idénticos.
Las copias de implementación se sincronizaron después de revisar los cambios de
directorios ZIP vacíos y workspaces externos; el nuevo módulo de entorno también
forma parte del manifiesto canónico. Una corrección documental enumera curriculum.

## Reversión sin destruir resultados

1. Detener nuevas ejecuciones y ejecutar el verificador de respaldos. Verificar
   además `git bundle verify` desde un repositorio confiable.
2. Conservar el árbol reparado y sus cambios locales renombrando la carpeta a una
   ubicación nueva; comprobar las rutas absolutas antes de moverla.
3. Clonar el bundle en una carpeta nueva para ensayar la restauración. Superponer
   **copias** de `backups/pre-separation/tracked/`, sin modificar el respaldo. Esto
   restaura también cambios que no pertenecían al commit base.
4. Comprobar los 173 hashes contra el manifiesto. El árbol reconstruido tiene el
   runtime, pruebas y herramientas originales. No ejecutar el runtime archivado
   como sustituto silencioso del candidato actual.
5. Para recuperar exactamente las rutas históricas, poner el árbol restaurado en
   la ubicación original después de preservar el reparado. Copiar tmp y, si se
   necesita para análisis, el entorno archivado, manteniendo su junction como
   enlace. Un entorno trasladado no se declara reutilizable: recrearlo para uso.
6. Si se revierte el contrato, preservar primero su estado actual. Restaurar
   copias de los 21 archivos de `canonical-before`, verificar sus hashes y apartar
   el módulo de entorno añadido. No tocar `referencias/TESLA-rc3` ni archivos de
   ensayos. La divergencia temporal del runtime reparado debe quedar explícita.
7. Ejecutar las pruebas originales sobre la restauración aislada antes de elegir
   qué árbol usar. Mantener ambos árboles y el desarrollo hasta aceptar el resultado.

No se han ejecutado estos movimientos de reversión sobre los directorios activos.
El backup original nunca se consume ni se sobrescribe.

## Publicación pendiente

La reparación es local y no tiene commits nuevos. Los SHAs actuales identifican
la base, no el candidato modificado. Antes de crear el repositorio público de
desarrollo: repetir la auditoría de todas las referencias y archivos publicables,
revisar los candidatos y metadatos, registrar una pareja de commits de runtime y
desarrollo, y ejecutar la matriz remota. Después se puede activar CI automática.
Los workflows manuales preparados exigen esa pareja explícita; no declaran una
ejecución remota que aún no ocurrió.
