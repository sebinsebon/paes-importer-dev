# Representación fiel: ejemplos ficticios

El [contrato de contenido](../shared/references/content-contract.md) define los bloques. Mantén separadas prosa y matemática sin perder espacios o puntuación.

## Variables y expresiones

«Si m y n son enteros, calcula m/n» se representa así:

~~~json
[
  {"type":"text","text":"Si "},
  {"type":"math","latex":"m","display":false},
  {"type":"text","text":" y "},
  {"type":"math","latex":"n","display":false},
  {"type":"text","text":" son enteros, calcula "},
  {"type":"math","latex":"\\frac{m}{n}","display":false}
]
~~~

En JSON, cada barra de LaTeX se escapa una vez. El valor decodificado lleva una barra ante frac. Usa display=true para desarrollos separados; false para símbolos dentro de una oración. Las letras de palabras y abreviaturas corrientes siguen siendo prosa. No pierdas índices, exponentes ni unidades.

## Tabla editable

~~~json
{"type":"table","rows":[
  [[{"type":"text","text":"Lado"}],[{"type":"text","text":"Área"}]],
  [[{"type":"math","latex":"a","display":false}],[{"type":"math","latex":"a^2","display":false}]]
]}
~~~

Conserva encabezados, filas, columnas y celdas. Una estructura que el contrato no expresa requiere imagen fiel y una incidencia; no se aplana a una oración.

## Opciones gráficas

~~~json
[
  {"label":"A","blocks":[{"type":"image","asset_id":"grafico-a","alt":"Parábola que abre hacia arriba."}]},
  {"label":"B","blocks":[{"type":"image","asset_id":"grafico-b","alt":"Parábola que abre hacia abajo."}]}
]
~~~

Cada recorte incluye su gráfico entero y sus rótulos, sin parte del siguiente. No pongas el mosaico en stem seguido de opciones genéricas.

## Desarrollo con solucionario

Transcribe la explicación y sus ecuaciones como bloques editables, conservando los pasos necesarios para entenderla. Una respuesta correcta por sí sola no demuestra que la transcripción sea fiel. Si el desarrollo necesita un diagrama, incorpora ese diagrama, con la fuente real del solucionario. La captura completa puede quedar como evidencia privada cuando ayude al cotejo.
