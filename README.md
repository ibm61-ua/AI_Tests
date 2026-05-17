# Gestor de Preguntas Tipo Test con IA

Una aplicación de escritorio desarrollada en Python con **CustomTkinter**. Te permite estudiar mediante la resolución de exámenes tipo test, calcular tu porcentaje de acierto en tiempo real y recibir explicaciones detalladas y contextuales de cada respuesta gracias a la integración de la inteligencia artificial de **Groq (Llama 3.3)**.

---

## Requisitos Previos

Para ejecutar esta aplicación, necesitas tener instalado:
1. Conexión a internet.
2. Una clave API válida de [Groq](https://console.groq.com/keys).

---

## Formato de los Archivos de Preguntas

La aplicación lee todas las preguntas desde archivos `.txt`. Para que las lea correctamente, cada pregunta debe seguir **exactamente** la siguiente estructura de líneas y estar separada por una **línea en blanco**:

```text
¿Cuál es la capital de Francia?
2
Madrid
París
Roma
Berlín

¿En qué año llegó el hombre a la Luna?
1
1969
1958
1972
```

**Explicación de la estructura:**
- **Línea 1:** El enunciado de la pregunta.
- **Línea 2:** El **número** de la respuesta correcta (empezando por 1).
- **Líneas 3 en adelante:** Las posibles opciones de respuesta.

> ⚠️ **Importante:** Deja siempre **una línea en blanco** para separar una pregunta de la siguiente. Puedes agrupar las preguntas en varios archivos `.txt` dentro de una misma carpeta.

---

## Cómo usar la aplicación

1. **Ejecutar el programa:** Haz doble clic en AI_Test.exe.
2. **Autenticación:** En la ventana principal, introduce tu clave de API de Groq en la caja de texto. Puedes usar el botón del ojo (👁) para ver si la has escrito correctamente.
3. **Importar Carpeta:** Haz clic en "Importar carpeta de preguntas" y selecciona el directorio de tu ordenador que contenga tus archivos `.txt`.
4. **Selección de Archivos:** Aparecerá una lista con todos los archivos encontrados. Marca la casilla de los temas/archivos que quieras estudiar hoy y pulsa en "Continuar".
5. **Realizar el Test:** 
   - Haz clic en las opciones para responder.
   - Observa cómo la ventana se anima dinámicamente para dejarle espacio a la IA.
   - Lee el análisis generado en el panel derecho para entender el concepto.
   - Revisa tu **Acierto (%)** en la parte superior y ajusta el **selector de penalización** si lo deseas.
   - Pulsa "Siguiente" para continuar o "Salir" para volver a la selección de archivos.

---

## Cierre del programa
- Usa los botones internos (`Volver` o `✕ Salir`) para retroceder a la pantalla anterior sin perder tu configuración.
- Usa la **cruz roja del sistema operativo** (arriba a la derecha de la ventana) para cerrar y terminar completamente la aplicación.
