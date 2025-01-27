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

def obtener_respuesta_openai(pregunta):
    """
    Envía la pregunta al modelo de OpenAI para obtener una respuesta.
    """
    try:
        print(f"Enviando pregunta a OpenAI ... ")
        respuesta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un experto en medicina y responderás preguntas de opción múltiple con explicaciones breves."},
                {"role": "user", "content": pregunta}
            ],
            max_tokens=500
        )
        contenido_respuesta = respuesta.choices[0].message.content.strip()
        print(f"Respuesta recibida:\n{contenido_respuesta}")
        return contenido_respuesta
    except Exception as e:
        print(f"Error al obtener la respuesta de OpenAI: {e}")
        return "Error al generar la respuesta."

def procesar_preguntas(archivo_entrada, archivo_salida, limite_preguntas):
    """
    Procesa un número limitado de preguntas desde el archivo, las envía a OpenAI y guarda las respuestas.
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
                    print(f"\n{pregunta}")
                    respuesta = obtener_respuesta_openai(pregunta)
                    salida.write(f"Pregunta {i}:\n")
                    salida.write(pregunta + "\n")
                    salida.write("Respuesta:\n")
                    salida.write(respuesta + "\n")
                    salida.write("\n" + "-" * 40 + "\n\n")
                    print(f"Respuesta para la pregunta {i} guardada.")
        print(f"\nSe han procesado {min(limite_preguntas, len(preguntas))} preguntas. Respuestas guardadas en {archivo_salida}.")
    except FileNotFoundError:
        print(f"Error: El archivo {archivo_entrada} no existe.")
    except Exception as e:
        print(f"Error inesperado: {e}")

# Ejecutar el procesamiento con el límite de preguntas
procesar_preguntas(archivo_preguntas, archivo_respuestas, max_preguntas)
