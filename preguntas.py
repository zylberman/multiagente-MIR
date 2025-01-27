import os
import re
import pdfplumber
from dotenv import load_dotenv

# Cargar las variables desde el archivo .env
load_dotenv("config.env")

# Configuración desde el archivo .env
PDF_PATH = os.getenv("PDF_PATH")
OUTPUT_DIR = os.getenv("OUTPUT_DIR")
OUTPUT_FILE = os.getenv("OUTPUT_FILE")
START_PAGE_QUESTIONS = int(os.getenv("START_PAGE_QUESTIONS", 3))  # Valor por defecto 3
END_PAGE_QUESTIONS = int(os.getenv("END_PAGE_QUESTIONS", 14))  # Valor por defecto 14

def extraer_preguntas(pdf_path, start_page_questions, end_page_questions):
    """
    Extrae preguntas de las páginas del PDF en orden descendente y las organiza en dos columnas.
    """
    preguntas = []
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        last_question_page = total_pages - end_page_questions

        for i in range(start_page_questions - 1, last_question_page):
            pagina = pdf.pages[i]
            columnas = dividir_doble_columna(pagina)
            preguntas.extend(columnas)

    return preguntas


def dividir_doble_columna(pagina):
    """
    Divide el texto de una página en dos columnas y las organiza en orden descendente.
    """
    ancho_pagina = pagina.width
    mitad = ancho_pagina / 2

    columna_izquierda = pagina.within_bbox((0, 0, mitad, pagina.height)).extract_text() or ""
    columna_derecha = pagina.within_bbox((mitad, 0, pagina.width, pagina.height)).extract_text() or ""

    lineas_izquierda = columna_izquierda.split("\n")
    lineas_derecha = columna_derecha.split("\n")

    return lineas_izquierda + lineas_derecha


def eliminar_guiones(texto):
    """
    Corrige los guiones al final de las líneas y reconstruye palabras divididas.
    """
    texto = re.sub(r"(\w+)-\n(\w+)", r"\1\2", texto)
    texto = re.sub(r"-\n", "", texto)
    return texto


def procesar_preguntas_y_separar(preguntas, output_file):
    """
    Procesa y separa preguntas con opciones en un archivo final.
    """
    preguntas_completas = "\n".join(preguntas)
    preguntas_completas = eliminar_guiones(preguntas_completas)

    patron_pregunta = re.compile(
        r"(\d+)\.\s+(.+?)\n1\.\s+(.+?)\n2\.\s+(.+?)\n3\.\s+(.+?)\n4\.\s+(.+?)(?=\n\d+\.|$)",
        re.DOTALL
    )

    preguntas_separadas = patron_pregunta.findall(preguntas_completas)

    if not preguntas_separadas:
        print("No se encontraron preguntas válidas.")
        return

    with open(output_file, "w", encoding="utf-8") as file:
        for pregunta in preguntas_separadas:
            numero, texto, op1, op2, op3, op4 = pregunta
            file.write(f"Pregunta {numero}:\n")
            file.write(f"{texto.strip()}\n")
            file.write(f"1. {op1.strip()}\n")
            file.write(f"2. {op2.strip()}\n")
            file.write(f"3. {op3.strip()}\n")
            file.write(f"4. {op4.strip()}\n")
            file.write("\n" + "-" * 40 + "\n\n")

    print(f"Preguntas separadas correctamente. Archivo generado en: {output_file}")


def extraer_imagenes(pdf_path, output_dir, image_pages):
    """
    Extrae imágenes de las últimas páginas del PDF.
    """
    os.makedirs(output_dir, exist_ok=True)
    imagenes_extraidas = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        start_image_page = total_pages - image_pages

        for i in range(start_image_page, total_pages - 1):
            pagina = pdf.pages[i]
            imagenes_pagina = sorted(pagina.images, key=lambda x: x['top'])

            for j, imagen in enumerate(imagenes_pagina):
                bbox = (imagen['x0'], imagen['top'], imagen['x1'], imagen['bottom'])
                img = pagina.within_bbox(bbox).to_image()

                titulo = f"IMAGEN {2 * (i - start_image_page) + j + 1}"
                imagen_path = os.path.join(output_dir, f"{titulo.replace(' ', '_')}.png")
                img.save(imagen_path, format="PNG")
                imagenes_extraidas.append((titulo, imagen_path))

    print(f"Imágenes extraídas correctamente. Guardadas en: {output_dir}")


if __name__ == "__main__":
    # Verificar si el archivo PDF existe
    if not os.path.exists(PDF_PATH):
        print(f"Error: El archivo PDF no existe: {PDF_PATH}")
    else:
        print(f"Procesando el archivo PDF: {PDF_PATH}")
        # Extraer preguntas del PDF
        preguntas = extraer_preguntas(PDF_PATH, START_PAGE_QUESTIONS, END_PAGE_QUESTIONS)
        
        # Procesar y separar preguntas
        procesar_preguntas_y_separar(preguntas, OUTPUT_FILE)
        
        # Extraer imágenes
        extraer_imagenes(PDF_PATH, OUTPUT_DIR, END_PAGE_QUESTIONS)
