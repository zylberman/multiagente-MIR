# Proyecto de Generación de Compendio MIR con Inteligencia Artificial

Este proyecto tiene como objetivo desarrollar un sistema basado en inteligencia artificial para resolver preguntas de exámenes MIR y simulacros, generando un **compendio con preguntas resueltas y explicaciones detalladas** que los estudiantes puedan usar para preparar el examen.

## **Visión del Proyecto**

El sistema final será capaz de:

1. **Resolver preguntas** usando:
   - Exámenes MIR anteriores.
   - Simulacros de preparación.
   - Inteligencia artificial.

2. **Generar explicaciones claras y detalladas**:
   - Respuestas correctas e incorrectas.
   - Explicaciones basadas en evidencia clínica, bibliografía médica y patrones previos.

3. **Clasificar preguntas por temas y subtemas**:
   - Organizar automáticamente las preguntas extraídas según categorías relevantes para el examen MIR.

4. **Futuro desarrollo**:
   - Crear preguntas nuevas dinámicamente basadas en las falencias académicas del estudiante.

## **Progreso Actual**

Al momento, el proyecto ha logrado:

1. **Extracción de preguntas**:
   - Procesamiento de los documentos PDF para identificar preguntas organizadas en doble columna.
   - Generación de un archivo de texto con todas las preguntas extraídas.

2. **Extracción de imágenes**:
   - Extracción de imágenes relacionadas desde las páginas finales de los PDFs.
   - Organización de las imágenes extraídas en un directorio específico.

3. **Eliminación de saltos de línea y guiones**:
   - Corrección automática de palabras cortadas por guiones (`-`) en el archivo de texto.
   - Reconstrucción del texto de las preguntas para mejorar su legibilidad.

4. **Separación y organización de preguntas**:
   - Identificación y separación de preguntas numeradas junto con sus respectivas cuatro opciones de respuesta.
   - Creación de un archivo de salida donde cada pregunta y opciones se presentan claramente delimitadas.

## **Estructura del Proyecto**

- **`pdfs/`**: Carpeta donde se almacenan los archivos PDF de entrada.
- **`salidas/`**: Carpeta donde se guardan las preguntas procesadas y las imágenes extraídas.
- **`extraccion_preguntas.py`**: Script principal para extraer preguntas e imágenes de los PDFs.
- **`corregir_guiones_txt.py`**: Script para eliminar guiones y reconstruir palabras divididas en las preguntas.
- **`separar_preguntas.py`**: Script para organizar las preguntas en bloques con su respectivo número y opciones.

## **Requisitos**

### **Requisitos Técnicos**
- Python 3.8 o superior.
- Librerías necesarias:
  - `pdfplumber` para extraer texto e imágenes de PDFs.
  - `os` y `re` para manipulación de archivos y procesamiento de texto.

### **Instalación de Dependencias**
Instala las librerías necesarias ejecutando:
```bash
pip install pdfplumber
