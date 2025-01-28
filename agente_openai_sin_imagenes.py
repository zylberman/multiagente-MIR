import os
from dotenv import load_dotenv
from openai import OpenAI

# Cargar variables desde .env y config.env
load_dotenv(".env")  # Para la clave de API
load_dotenv("config.env")  # Para las rutas de archivos

# Configuración
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
archivo_preguntas = os.getenv("ARCHIVO_SALIDA_SIN_IMAGEN")
archivo_respuestas = os.getenv("ARCHIVO_RESPUESTAS", "salidas/respuestas_preguntas_sin_imagen.txt")
max_preguntas = int(os.getenv("MAX_PREGUNTAS", 3))  # Límite de preguntas para pruebas

# Validar configuraciones
if not client.api_key:
    raise ValueError("La clave de OpenAI no está definida en .env o es inválida.")
if not archivo_preguntas:
    raise ValueError("La variable ARCHIVO_PREGUNTAS no está definida en config.env o es inválida.")

# Crear directorio de salida si no existe
os.makedirs(os.path.dirname(archivo_respuestas), exist_ok=True)

def obtener_respuesta_openai(model, pregunta, modo="respuesta"):
    """
    Envía la pregunta al modelo de OpenAI y obtiene una respuesta.
    """
    try:
        print(f"Enviando pregunta al modelo {model}... ")
        if modo == "respuesta":
            messages = [
                {"role": "system", "content": "Eres un experto en medicina y responderás con la opción correcta (1, 2, 3 o 4) para la pregunta dada."},
                {"role": "user", "content": pregunta}
            ]
        elif modo == "probabilidades":
            messages = [
                {"role": "system", "content": "Eres un experto en medicina. Proporciona un porcentaje de certeza para cada opción de respuesta (1, 2, 3, 4) y señala cuál tiene la probabilidad más alta. Si varias opciones tienen alta probabilidad, inclúyelas."},
                {"role": "user", "content": pregunta}
            ]
        elif modo == "comparacion":
            messages = [
                {"role": "system", "content": "Eres un experto en medicina. Compara la respuesta seleccionada por gpt-4o y gpt-4o-mini. Genera una asociación inverosímil para memorizar si ambas respuestas coinciden. Si son diferentes, explica por qué."},
                {"role": "user", "content": pregunta}
            ]

        respuesta = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=500
        )
        contenido_respuesta = respuesta.choices[0].message.content.strip()
        print(f"Respuesta recibida del modelo {model}:\n{contenido_respuesta}")
        return contenido_respuesta
    except Exception as e:
        print(f"Error al obtener la respuesta de OpenAI con {model}: {e}")
        return "Error al generar la respuesta."

def procesar_preguntas(archivo_entrada, archivo_salida, limite_preguntas):
    """
    Procesa un número limitado de preguntas desde el archivo.
    """
    try:
        with open(archivo_entrada, "r", encoding="utf-8") as file:
            contenido = file.read()
            preguntas = contenido.split("----------------------------------------")

        with open(archivo_salida, "w", encoding="utf-8") as salida:
            for i, pregunta in enumerate(preguntas[:limite_preguntas], start=1):  # Procesar hasta el límite
                pregunta = pregunta.strip()
                if pregunta:
                    print(f"\nProcesando pregunta {i} de {limite_preguntas}...")
                    print(f"\nPregunta:\n{pregunta}")

                    # Paso 1: Obtener respuesta con gpt-4o
                    respuesta_gpt4o = obtener_respuesta_openai("gpt-4o", pregunta, modo="respuesta")

                    # Paso 2: Obtener probabilidades con gpt-4o-mini
                    respuesta_gpt4o_mini = obtener_respuesta_openai("gpt-4o-mini", pregunta, modo="probabilidades")

                    # Paso 3: Comparar y generar asociación con gpt-3.5-turbo
                    comparacion = obtener_respuesta_openai("gpt-3.5-turbo", f"Pregunta:\n{pregunta}\nRespuesta gpt-4o: {respuesta_gpt4o}\nProbabilidades gpt-4o-mini: {respuesta_gpt4o_mini}", modo="comparacion")

                    # Guardar resultados en el archivo
                    salida.write(f"Pregunta {i}:\n")
                    salida.write(pregunta + "\n")
                    salida.write("Respuesta gpt-4o:\n")
                    salida.write(respuesta_gpt4o + "\n")
                    salida.write("Probabilidades gpt-4o-mini:\n")
                    salida.write(respuesta_gpt4o_mini + "\n")
                    salida.write("Comparación gpt-3.5-turbo:\n")
                    salida.write(comparacion + "\n")
                    salida.write("\n" + "-" * 40 + "\n\n")
                    print(f"Resultados para la pregunta {i} guardados.")
        print(f"\nSe han procesado {min(limite_preguntas, len(preguntas))} preguntas. Respuestas guardadas en {archivo_salida}.")
    except FileNotFoundError:
        print(f"Error: El archivo {archivo_entrada} no existe.")
    except Exception as e:
        print(f"Error inesperado: {e}")

# Ejecutar el procesamiento con el límite de preguntas
procesar_preguntas(archivo_preguntas, archivo_respuestas, max_preguntas)
