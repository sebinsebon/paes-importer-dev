# Consolidación local de 1.5.0 en los repositorios originales

`optimization-runtime` y `optimization-dev` se crearon para aislar el trabajo
del checkout original. Son **worktrees enlazados**, no clones ni repositorios
independientes. Sus archivos `.git` apuntan a los metadatos `worktrees/` de los
dos repositorios originales. Comparten objetos, commits y referencias con ellos.
La preferencia del propietario es trabajar directamente en los dos originales.

## Ramas activas

Todas las rutas de esta sección son relativas a
`C:/Users/Administrator/Documents/Paessed.cl/`.

| Repositorio original | Rama activa | Commit de implementación conservado |
| --- | --- | --- |
| `paes-importer-skill` | `integration/1.5.0` | `c0d0b719e26a2f42133a038514989d62c74f7023` |
| `paes-importer-dev` | `integration/1.5.0` | `952f409e5eb2652d2aeedfa774d4aafa54181c2e` |

Las ramas nuevas parten de esos mismos objetos; no se reescribió historia ni se
aplicaron cherry-picks. Este documento y la actualización de rutas añaden un
commit de documentación en desarrollo, descendiente del commit indicado.
`runtime.lock.json` conserva la revisión del runtime y el hash del manifiesto.

El `main` del runtime sigue en
`f47bb4f16387434bbb8f7c96882c3f5cc28d24ee`. La rama de desarrollo anterior
`dev/repair-separation` sigue en
`aa559b9f686a4a72305c07facd4dc1d7a1f52152`.
No se realizó merge, push ni publicación de una release.

## Preservación de archivos e historia

El respaldo está en `paes-importer-dev/backups/worktree-consolidation-20261021/`:

- `inventory-before.json`: inventario físico inicial de ambos worktrees.
- `preservation.json`: correspondencia origen/destino y SHA-256 de cada archivo.
- `preservation-final.json`: auditoría posterior a las pruebas y al commit de
  documentación; conserva por separado los bytes históricos si cambió una copia
  activa y verifica de nuevo los orígenes, los destinos y las ramas base.
- `paes-importer-skill.bundle` y `paes-importer-dev.bundle`: historia y referencias
  Git alcanzables, verificadas con `git bundle verify`. Las copias adicionales
  `*-integration.bundle` incluyen también las ramas nuevas y este documento.
- `runtime-1.4.1-baseline.zip`: archivo de la revisión base para la prueba sintética
  de adopción; no es un segundo runtime mantenido ni una dependencia operativa.
- `original-checkout-eol/`: bytes previos de cuatro archivos del checkout original
  con CRLF, antes de igualarlos a los LF del worktree. Su contenido Git era igual.

Se preservaron **1.750 archivos y 34.945.596 bytes**, incluidos archivos ignorados:
pruebas, fixtures, resultados satisfactorios y fallidos, capturas, benchmarks,
distribuciones, respaldos normativos y archivos temporales de la implementación.
Cada destino coincide con el SHA-256 inicial de su origen. Los archivos de origen
permanecieron intactos durante la transferencia. Los archivos propios anteriores
de los repositorios originales se conservaron; una colisión distinta de archivos
ignorados se archiva separadamente bajo `conflicts/`, si existe.

Los informes históricos conservan sus bytes y sus rutas originales. Para
interpretarlos después de retirar los worktrees, aplicar esta correspondencia:

| Prefijo histórico | Ubicación actual |
| --- | --- |
| `.../optimization-runtime/` | `.../paes-importer-skill/` |
| `.../optimization-dev/` | `.../paes-importer-dev/` |

El manifiesto de preservación registra cualquier destino alternativo por colisión.
La copia canónica revisada del contrato en `contrato/` permanece en su ubicación;
su respaldo normativo y el lock se conservaron también en desarrollo.

## Verificación desde los originales

La verificación se registra en
`results/verification-original-repos-20261021.json` y su `.log`. Usa
`paes-importer-dev/scripts/check.py --runtime ../paes-importer-skill`, Chrome real
y la revisión 1.4.1 archivada para la prueba sintética de adopción. La extracción
de esa referencia vive temporalmente bajo `paes-importer-dev/tmp/` y se elimina
al terminar; no necesita ninguno de los dos worktrees.

Resultado: **304 pruebas, sin fallos, dos omitidas** por falta de privilegios de
enlaces simbólicos en Windows. Manifiesto, documentación, contrato y árbol físico
pasaron; no hubo cambios en el runtime. La suite tardó 245,87 segundos.

Se vuelve a comparar el contrato con `../contrato` y se reconstruye la distribución
en `releases/paes-importer-1.5.0-original-repos-check.zip`. Su SHA-256 debe ser
`d13694fa67f7246623dc9c2888e1c464cbf633da348b860c8e8b310068174a21`,
idéntico al candidato preservado; la reconstrucción lo confirmó. El informe de consolidación final registra
estos resultados y verifica de nuevo todas las copias y referencias Git.

## Carpetas que pueden retirarse tras la verificación

Las únicas carpetas redundantes identificadas son:

- `C:/Users/Administrator/Documents/Paessed.cl/optimization-runtime`
- `C:/Users/Administrator/Documents/Paessed.cl/optimization-dev`

Se conservan físicamente hasta que se decida retirarlas. Deben retirarse con
`git worktree remove` desde su repositorio original para que Git elimine también
el registro del worktree. El worktree de desarrollo contiene archivos ignorados;
su retirada puede exigir `--force`, que borraría esas copias locales ya respaldadas.
Antes de ejecutarlo hay que volver a comprobar que ningún origen cambió respecto
del manifiesto de preservación. Las ramas `optimization/documentary-quality`
pueden conservarse como referencias históricas después de retirar las carpetas.

No eliminar manualmente `.git/worktrees/`. No se señalan para eliminación los
repositorios originales, sus entornos, sus respaldos ni los resultados e informes
preservados. Esta consolidación no elimina ninguna de las dos carpetas redundantes.
