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


def limpiar_texto(texto):
    """
    Limpia el texto eliminando líneas no deseadas, respetando el formato de las preguntas y respuestas.
    """
    # Patrones que deben eliminarse
    patrones_a_eliminar = [
        r"^\s*-\d+\s*$",              # Líneas como -1, -2, etc.
        r"MIR\d+\.\d+\.\d+",          # Coincide con MIR12.2425.16 o similares
        r"^\s*-\s*$",                 # Líneas con solo un guion
        r"^\s*$"                      # Líneas vacías
    ]

    # Compilar los patrones en uno solo
    patron_compilado = re.compile("|".join(patrones_a_eliminar))

    # Filtrar líneas no deseadas
    lineas = texto.split("\n")
    lineas_filtradas = [linea for linea in lineas if not patron_compilado.match(linea.strip())]

    # Reconstruir el texto limpio
    texto_limpio = "\n".join(lineas_filtradas)

    # Corregir guiones y palabras separadas
    texto_limpio = re.sub(r"(\w+)-\n(\w+)", r"\1\2", texto_limpio)  # Une palabras separadas por guiones
    texto_limpio = re.sub(r"-\n", "", texto_limpio)                # Elimina guiones sueltos

    return texto_limpio


def determinar_pagina_final_preguntas(pdf_path, start_page_questions):
    """
    Determina la página inmediatamente después del final de la pregunta 210.
    """
    with pdfplumber.open(pdf_path) as pdf:
        for i in range(start_page_questions - 1, len(pdf.pages)):
            pagina = pdf.pages[i]
            texto = pagina.extract_text()
            if texto and re.search(r"210\.", texto):  # Busca la pregunta 210
                print(f"La pregunta 210 se encontró en la página {i + 1}.")
                return i + 1  # Página inmediatamente después de la pregunta 210
    raise ValueError("No se encontró la pregunta 210 en el PDF.")


def extraer_preguntas(pdf_path, start_page_questions, end_page_questions):
    """
    Extrae preguntas de las páginas del PDF en orden descendente y las organiza en dos columnas.
    """
    print(f"Iniciando extracción de preguntas desde la página {start_page_questions} hasta {end_page_questions - 1}.")
    preguntas = []
    with pdfplumber.open(pdf_path) as pdf:
        for i in range(start_page_questions - 1, end_page_questions - 1):
            pagina = pdf.pages[i]
            columnas = dividir_doble_columna(pagina)
            texto_limpio = limpiar_texto("\n".join(columnas))
            preguntas.extend(texto_limpio.split("\n"))

    return preguntas


def dividir_doble_columna(pagina):
    """
    Divide el texto de una página en dos columnas, las organiza y limpia.
    """
    ancho_pagina = pagina.width
    mitad = ancho_pagina / 2

    columna_izquierda = pagina.within_bbox((0, 0, mitad, pagina.height)).extract_text() or ""
    columna_derecha = pagina.within_bbox((mitad, 0, pagina.width, pagina.height)).extract_text() or ""

    # Une ambas columnas y aplica limpieza
    texto_completo = "\n".join(columna_izquierda.split("\n") + columna_derecha.split("\n"))
    texto_limpio = limpiar_texto(texto_completo)

    return texto_limpio.split("\n")


def procesar_preguntas_y_separar(preguntas, output_file):
    """
    Procesa y separa preguntas con opciones en un archivo final.
    """
    # Crear el directorio si no existe
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    preguntas_completas = "\n".join(preguntas)

    patron_pregunta = re.compile(
        r"(\d+)\.\s+(.+?)\n1\.\s+(.+?)\n2\.\s+(.+?)\n3\.\s+(.+?)\n4\.\s+(.+?)(?=\n\d+\.|$)",
        re.DOTALL
    )

    preguntas_separadas = patron_pregunta.findall(preguntas_completas)

    if not preguntas_separadas:
        print("No se encontraron preguntas válidas.")
        return []

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
    return preguntas_separadas


def extraer_imagenes(pdf_path, output_dir, start_page_images):
    """
    Extrae imágenes de las últimas páginas del PDF y las nombra secuencialmente desde "IMAGEN_1".
    """
    print(f"Iniciando extracción de imágenes desde la página {start_page_images}.")
    os.makedirs(output_dir, exist_ok=True)
    imagenes_extraidas = []
    contador_imagen = 1  # Contador global para numerar las imágenes

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

        for i in range(start_page_images - 1, total_pages):
            pagina = pdf.pages[i]
            imagenes_pagina = sorted(pagina.images, key=lambda x: x['top'])

            for j, imagen in enumerate(imagenes_pagina):
                bbox = (imagen['x0'], imagen['top'], imagen['x1'], imagen['bottom'])
                img = pagina.within_bbox(bbox).to_image()

                # Asignar nombre secuencial a la imagen
                titulo = f"IMAGEN_{contador_imagen}.png"
                imagen_path = os.path.join(output_dir, titulo)
                img.save(imagen_path, format="PNG")
                imagenes_extraidas.append((titulo, imagen_path))

                # Incrementar el contador de imágenes
                contador_imagen += 1

    print(f"Imágenes extraídas correctamente. Guardadas en: {output_dir}")
    return imagenes_extraidas

def obtener_preguntas_imagenes(pdf_path):
    # Verificar si el archivo PDF existe
    if not os.path.exists(pdf_path):
        print(f"Error: El archivo PDF no existe: {pdf_path}")
    else:
        print(f"Procesando el archivo PDF: {pdf_path}")
        try:
            # Determinar la página donde terminan las preguntas
            END_PAGE_QUESTIONS = determinar_pagina_final_preguntas(pdf_path, START_PAGE_QUESTIONS) + 1
            
            # Extraer preguntas del PDF
            preguntas = extraer_preguntas(pdf_path, START_PAGE_QUESTIONS, END_PAGE_QUESTIONS)
            
            # Procesar y separar preguntas
            procesar_preguntas_y_separar(preguntas, OUTPUT_FILE)
            
            # Extraer imágenes del PDF
            extraer_imagenes(pdf_path, OUTPUT_DIR, END_PAGE_QUESTIONS)

            print("Proceso completado correctamente. Todas las preguntas e imágenes fueron extraídas con éxito.")

        except ValueError as e:
            print(f"Error durante el procesamiento: {e}")

if __name__ == "__main__":
    obtener_preguntas_imagenes(PDF_PATH)
