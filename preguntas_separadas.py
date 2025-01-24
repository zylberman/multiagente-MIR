import os
import re

# Variables externas
INPUT_FILE = "salidas/preguntas_corregidas.txt"  # Archivo de entrada
OUTPUT_FILE = "salidas/preguntas_separadas.txt"  # Archivo de salida


def separar_preguntas(input_file, output_file):
    """
    Lee el archivo de entrada, separa las preguntas y las guarda en el archivo de salida.
    Cada pregunta tiene su número, texto y cuatro opciones de respuesta.
    """
    if not os.path.exists(input_file):
        print(f"Error: El archivo de entrada no existe: {input_file}")
        return

    with open(input_file, "r", encoding="utf-8") as file:
        contenido = file.read()

    # Expresión regular para capturar preguntas con cuatro opciones
    patron_pregunta = re.compile(
        r"(\d+)\.\s+(.+?)\n1\.\s+(.+?)\n2\.\s+(.+?)\n3\.\s+(.+?)\n4\.\s+(.+?)(?=\n\d+\.|$)",
        re.DOTALL
    )

    preguntas = patron_pregunta.findall(contenido)

    if not preguntas:
        print("No se encontraron preguntas en el archivo.")
        return

    with open(output_file, "w", encoding="utf-8") as file:
        for pregunta in preguntas:
            numero, texto, op1, op2, op3, op4 = pregunta
            file.write(f"Pregunta {numero}:\n")
            file.write(f"{texto.strip()}\n")
            file.write(f"1. {op1.strip()}\n")
            file.write(f"2. {op2.strip()}\n")
            file.write(f"3. {op3.strip()}\n")
            file.write(f"4. {op4.strip()}\n")
            file.write("\n" + "-" * 40 + "\n\n")

    print(f"Preguntas separadas correctamente. Archivo generado en: {output_file}")


if __name__ == "__main__":
    # Ejecutar la separación de preguntas
    print(f"Procesando archivo: {INPUT_FILE}")
    separar_preguntas(INPUT_FILE, OUTPUT_FILE)
