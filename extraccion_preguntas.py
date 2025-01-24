import pdfplumber
import os

# Variables externas para configuración
PDF_PATH = "pdfs/MIR.12.2425.01.pdf"  # Ruta del PDF
OUTPUT_DIR = "salidas/imagenes"  # Directorio donde se guardarán las imágenes

START_PAGE_QUESTIONS = 3  # Página inicial de las preguntas
END_PAGE_QUESTIONS = 14  # Número de páginas finales reservadas para imágenes


def extraer_preguntas(pdf_path, start_page_questions, end_page_questions):
    """
    Extrae preguntas de las páginas del PDF en orden descendente
    organizadas en dos columnas.
    """
    preguntas = []
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        last_question_page = total_pages - end_page_questions

        for i in range(start_page_questions - 1, last_question_page):
            pagina = pdf.pages[i]
            columnas = dividir_doble_columna(pagina)
            preguntas.extend(columnas)

    # Procesar preguntas para asegurarse de que se identifiquen las opciones y se separen con saltos de línea
    preguntas_procesadas = procesar_preguntas_con_opciones(preguntas)
    return preguntas_procesadas


def dividir_doble_columna(pagina):
    """
    Divide el texto de una página en dos columnas y las organiza
    en orden descendente (primero izquierda, luego derecha).
    """
    # Obtener las dimensiones de la página
    ancho_pagina = pagina.width
    mitad = ancho_pagina / 2

    # Extraer texto de cada columna basado en coordenadas
    columna_izquierda = pagina.within_bbox((0, 0, mitad, pagina.height)).extract_text() or ""
    columna_derecha = pagina.within_bbox((mitad, 0, pagina.width, pagina.height)).extract_text() or ""

    # Convertir cada columna en una lista de líneas
    lineas_izquierda = columna_izquierda.split("\n")
    lineas_derecha = columna_derecha.split("\n")

    # Combinar en orden descendente: primero columna izquierda, luego derecha
    return lineas_izquierda + lineas_derecha


def procesar_preguntas_con_opciones(preguntas):
    """
    Procesa cada pregunta para asegurarse de que se identifiquen las opciones (1, 2, 3, 4),
    elimina líneas irrelevantes, y agrega un doble salto de línea antes de cada pregunta.
    """
    preguntas_procesadas = []
    buffer_pregunta = []

    for linea in preguntas:
        linea = linea.strip()

        # Ignorar líneas irrelevantes
        if not linea or linea.startswith("-") or "MIR" in linea:
            continue

        # Identificar inicio de pregunta (si está numerada)
        if linea[0].isdigit() and "." in linea[:3]:  # Ejemplo: "1. Pregunta"
            # Si hay una pregunta previa en el buffer, procesarla y agregarla
            if buffer_pregunta:
                preguntas_procesadas.append("\n".join(buffer_pregunta) + "\n")
                buffer_pregunta = []
            # Agregar doble salto de línea antes de la nueva pregunta
            preguntas_procesadas.append("")  # Doble salto de línea antes de la pregunta actual
        
        # Agregar línea al buffer de la pregunta actual
        buffer_pregunta.append(linea)

    # Agregar la última pregunta procesada si hay contenido en el buffer
    if buffer_pregunta:
        preguntas_procesadas.append("\n".join(buffer_pregunta) + "\n")

    return preguntas_procesadas


def extraer_imagenes(pdf_path, output_dir, image_pages):
    """
    Extrae imágenes de las últimas páginas del PDF en el orden correcto.
    """
    imagenes_extraidas = []
    os.makedirs(output_dir, exist_ok=True)
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        start_image_page = total_pages - image_pages

        for i in range(start_image_page, total_pages - 1):  # Última página no tiene imágenes
            pagina = pdf.pages[i]
            imagenes_pagina = sorted(pagina.images, key=lambda x: x['top'])  # Ordenar imágenes por posición 'top'

            for j, imagen in enumerate(imagenes_pagina):
                bbox = (imagen['x0'], imagen['top'], imagen['x1'], imagen['bottom'])
                img = pagina.within_bbox(bbox).to_image()

                # Crear el título dinámico basado en el orden
                titulo = f"IMAGEN {2 * (i - start_image_page) + j + 1}"
                
                # Guardar imagen
                imagen_path = os.path.join(output_dir, f"{titulo.replace(' ', '_')}.png")
                img.save(imagen_path, format="PNG")
                imagenes_extraidas.append((titulo, imagen_path))
    return imagenes_extraidas


if __name__ == "__main__":
    # Extraer preguntas
    preguntas = extraer_preguntas(PDF_PATH, START_PAGE_QUESTIONS, END_PAGE_QUESTIONS)

    # Extraer imágenes
    imagenes = extraer_imagenes(PDF_PATH, OUTPUT_DIR, END_PAGE_QUESTIONS)

    # Guardar resultados de preguntas
    os.makedirs("salidas", exist_ok=True)
    with open("salidas/preguntas_extraidas.txt", "w", encoding="utf-8") as file:
        for pregunta in preguntas:
            file.write(f"{pregunta}\n")

    print("Extracción completada.")
    print(f"Preguntas guardadas en: salidas/preguntas_extraidas.txt")
    print(f"Imágenes guardadas en: {OUTPUT_DIR}")
