Hola. Quiero que me ayudes a configurar Job Hunter, un programa que busca ofertas de empleo por mí en LinkedIn, Indeed y Glassdoor y les pone un puntaje de 0 a 100 según qué tanto encajan conmigo.

Tu tarea: hazme una entrevista corta para entender qué trabajo busco y, al final, dame un archivo de configuración en YAML.

CÓMO HACER LA ENTREVISTA
- Hazme UNA pregunta a la vez, en lenguaje sencillo, y espera mi respuesta antes de seguir.
- Si no sé algo o no tengo preferencia, propónme una opción razonable según lo que ya te conté.
- Pregúntame sobre:
  1. Mi nombre, y en qué ciudad y país vivo.
  2. Qué puesto o puestos busco y cuántos años de experiencia tengo.
  3. Mis principales habilidades, herramientas o conocimientos.
  4. Qué puestos NO quiero ver (por ejemplo, muy senior, de gerencia o de otra área).
  5. Cómo quiero trabajar (remoto, híbrido o presencial) y en qué ciudades o países.
  6. Qué jornada busco: tiempo completo, medio tiempo, prácticas o contrato.
  7. Qué idiomas hablo y a qué nivel.
  8. Qué cosas de una oferta me interesan más (suman puntos) y cuáles me alejan (restan puntos).
  9. Qué días y a qué hora quiero que busque solo.
- Al terminar, muéstrame un resumen corto y pregúntame si está bien antes de darme el archivo.

CÓMO FUNCIONA JOB HUNTER (tenlo en cuenta para que la configuración rinda)
- Por cada combinación de sitio × puesto × ubicación × jornada hace una búsqueda aparte, y cada una tarda unos 20 segundos. Muchas combinaciones = corridas de horas y bloqueos de los sitios. Apunta a 120 combinaciones o menos.
- LinkedIn es la fuente más confiable: inclúyelo siempre. Indeed también funciona bien. Glassdoor bloquea a menudo: agrégalo solo si lo pido.
- LinkedIn busca por título del puesto y acepta como ubicación una ciudad, un país, "Remote" o "worldwide".
- Indeed y Glassdoor buscan dentro de un solo país (la clave "pais"): ahí solo tienen sentido ubicaciones de ese país, "Remote" o "worldwide".
- Muchas ofertas de LinkedIn en Latinoamérica y España se publican en inglés, aunque la empresa sea local.
- Las palabras de filtros y puntaje se buscan como palabras completas, sin importar mayúsculas ni acentos.

REGLAS PARA EL ARCHIVO
- Usa exactamente el formato y las claves del ejemplo de abajo. No agregues secciones ni claves nuevas.
- Escribe palabras normales, nunca expresiones regulares, comillas de búsqueda ni operadores como OR o AND.
- "puestos": entre 4 y 10. Títulos cortos (de 2 a 4 palabras) tal como aparecen en las ofertas, mezclando español e inglés (por ejemplo "Contador" y "Accountant"). Sin ciudades, sin "remoto" y sin nivel, salvo una o dos variantes con "Junior" si mi nivel es junior.
- "ubicaciones": entre 2 y 4. Países con su nombre en inglés ("Mexico", "Spain", "United States"), mi ciudad si busco presencial o híbrido, y "Remote" si quiero remoto. No repitas lugares que ya cubre otro (si está "Colombia", no hace falta "Bogotá" para remoto).
- "jornada": déjala vacía ([]) salvo que de verdad solo quiera un tipo; como mucho 2, porque cada una multiplica las búsquedas.
- "sitios": [linkedin, indeed] salvo que pida otra cosa.
- "pais": el país de Indeed y Glassdoor, en inglés y minúsculas (por ejemplo mexico, colombia, spain, argentina, chile, peru, usa). Si mi país no tiene Indeed, pon worldwide.
- "ubicaciones_aceptadas": palabras que deben aparecer en la ubicación de una oferta para conservarla (las remotas pasan siempre). Incluye mi ciudad y mi país en español y en inglés, "remote", y "latam" o "latin america" si me sirven ofertas para toda la región.
- "excluir_en_titulo": entre 5 y 15 palabras que, si aparecen en el título, descartan la oferta: niveles que no me tocan (senior, lead, head, principal, director, gerente, manager…) y áreas que no son la mía. En español y en inglés. Nunca pongas una palabra que aparezca en mis "puestos".
- "anios_experiencia_maximos": mis años de experiencia más 1 o 2. Descarta ofertas que piden más.
- "habilidades_extra": entre 4 y 10 habilidades o herramientas mías. Cada una que aparezca en la oferta suma 5 puntos (máximo 20).
- "suman": entre 3 y 8 reglas. Escala: lo central de mi perfil +30; "junior" o "entry level" en el título +20 si soy junior; habilidades importantes +10; detalles deseables +5. Si la oferta puede venir en inglés, pon la palabra en ambos idiomas como reglas separadas.
- "restan": entre 2 y 6 reglas, de 10 a 20 puntos: requisitos que me alejan (otra especialidad, un idioma que no domino, más experiencia de la que tengo).
- "puntaje_minimo": entre 20 y 30 (25 es un buen punto de partida). "destacada": 70.
- "nivel": junior, semi-senior o senior. "donde" puede ser titulo, descripcion o ubicacion.
- Las horas, entre comillas y en formato de 24 horas ("09:00"). Los días: lun, mar, mie, jue, vie, sab, dom. Una búsqueda al día suele bastar.
- Entrégame el archivo completo en un solo bloque de código yaml y dime que lo guarde como jobhunter.yaml o que lo copie, para pegarlo en la página de ayuda de Job Hunter.

EJEMPLO DEL FORMATO (los valores son de otra persona; usa los míos)

```yaml
perfil:
  nombre: Ana López
  nivel: junior
  ubicacion: Bogotá, Colombia
  zona_horaria: UTC-5
  idiomas: [Español (nativo), Inglés (B1)]
  habilidades_principales: [Contabilidad, Excel, SAP]
  habilidades_secundarias: [Power BI, Facturación electrónica]

busqueda:
  puestos: [Contador, Auxiliar contable, Analista contable, Accountant, Accounting Assistant, Junior Accountant]
  ubicaciones: [Bogotá, Colombia, Remote]
  modalidad: [remoto, hibrido]        # remoto, hibrido, presencial
  jornada: [tiempo_completo]          # tiempo_completo, medio_tiempo, practicas, contrato ([] = cualquiera)
  sitios: [linkedin, indeed]          # linkedin, indeed, glassdoor
  pais: colombia
  habilidades_extra: [Excel, SAP, NIIF, IFRS, Power BI]

filtros:
  excluir_en_titulo: [senior, sr, lead, head, principal, director, gerente, manager, jefe, auditor, tax]
  ubicaciones_aceptadas: [bogota, colombia, remote, latam, latin america]
  anios_experiencia_maximos: 3
  puntaje_minimo: 25                  # de 0 a 100; las ofertas con menos no se guardan

puntaje:
  destacada: 70                       # desde este puntaje la oferta se marca como destacada
  suman:
    - palabra: contabilidad
      puntos: 30
      donde: descripcion
    - palabra: accounting
      puntos: 30
      donde: descripcion
    - palabra: junior
      puntos: 20
      donde: titulo
    - palabra: NIIF
      puntos: 10
      donde: descripcion
    - palabra: IFRS
      puntos: 10
      donde: descripcion
  restan:
    - palabra: inglés avanzado
      puntos: 15
      donde: descripcion
    - palabra: fluent english
      puntos: 15
      donde: descripcion

tecnologias_a_detectar: [Excel, SAP, Power BI, NIIF, IFRS]

horarios:
  - dias: [lun, mar, mie, jue, vie]
    hora: "09:00"
    busqueda: diaria

notificaciones:
  resumen_diario: true
  alertas_destacadas: true
```

Empieza ya con la primera pregunta.
