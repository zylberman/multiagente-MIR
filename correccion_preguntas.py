import os
import re

# Variables externas
INPUT_TXT_PATH = "salidas/preguntas_extraidas.txt"  # Ruta del archivo de entrada
OUTPUT_TXT_PATH = "salidas/preguntas_corregidas.txt"  # Ruta del archivo corregido

def eliminar_guiones_txt(input_txt_path, output_txt_path):
    """
    Elimina los guiones medios al final de las líneas en un archivo .txt
    y genera un nuevo archivo corregido.
    """
    # Verificar si el archivo de entrada existe
    if not os.path.exists(input_txt_path):
        print(f"Error: El archivo de entrada no existe: {input_txt_path}")
        return

    # Leer el contenido del archivo
    with open(input_txt_path, "r", encoding="utf-8") as input_file:
        contenido = input_file.read()

    # Corregir los guiones al final de las líneas
    contenido_corregido = eliminar_guiones(contenido)

    # Comprobar si hubo cambios
    if contenido == contenido_corregido:
        print("No se encontraron guiones para corregir.")
    else:
        # Escribir el archivo corregido
        with open(output_txt_path, "w", encoding="utf-8") as output_file:
            output_file.write(contenido_corregido)
        print(f"Archivo corregido guardado en: {output_txt_path}")


def eliminar_guiones(texto):
    """
    Corrige los guiones medios al final de las líneas en un texto.
    Ejemplo: "palabra-\nsiguiente" -> "palabrasiguiente"
    """
    # Corregir palabras cortadas por guiones
    texto = re.sub(r"(\w+)-\n(\w+)", r"\1\2", texto)

    # Reemplazar cualquier "-\n" sobrante por nada
    texto = re.sub(r"-\n", "", texto)

    return texto


if __name__ == "__main__":
    # Ejecutar la corrección de guiones en el archivo de texto
    print(f"Procesando archivo: {INPUT_TXT_PATH}")
    eliminar_guiones_txt(INPUT_TXT_PATH, OUTPUT_TXT_PATH)
