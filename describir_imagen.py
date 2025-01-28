import os
import openai
import base64
from dotenv import load_dotenv
from openai import OpenAI

# Cargar las variables de entorno desde el archivo .env
load_dotenv(".env")

# Configurar la clave de API
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("La clave de OpenAI no está definida en .env o es inválida.")

# Inicializar el cliente de OpenAI
client = OpenAI(api_key=api_key)

# Función para codificar la imagen en base64
def codificar_imagen(ruta_imagen):
    with open(ruta_imagen, "rb") as imagen:
        return base64.b64encode(imagen.read()).decode("utf-8")

# Ruta de la imagen que deseas describir
ruta_imagen = 'imagen.png'

# Codificar la imagen
imagen_codificada = codificar_imagen(ruta_imagen)

# Realizar la solicitud a la API
respuesta = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "Eres un asistente que proporciona descripciones detalladas de imágenes."},
        {"role": "user", "content": "Describe la siguiente imagen:", "image": {"base64": imagen_codificada}}
    ]
)

# Imprimir la descripción proporcionada por la API
descripcion = respuesta.choices[0].message.content
print("Descripción de la imagen:", descripcion)
