from dotenv import load_dotenv
import os
from openai import OpenAI

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Configuración de OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Verificar que la clave fue cargada correctamente
if not client.api_key:
    raise ValueError("La clave de API no se encontró. Verifica el archivo .env.")

# Archivos de entrada y salida
archivo_preguntas = "salidas/preguntas_separadas.txt"
archivo_salida = "salidas/preguntas_con_imagen.txt"

def es_pregunta_con_imagen(pregunta):
    """
    Usa un modelo de lenguaje para determinar si una pregunta está relacionada con una imagen.
    """
    messages = [
        {"role": "system", "content": "Eres un asistente que ayuda a clasificar preguntas relacionadas con imágenes."},
        {"role": "user", "content": f"""Determina si esta pregunta está relacionada con una imagen:
        
        Pregunta:
        {pregunta}
        
        Responde con 'Sí' si está relacionada con una imagen y menciona a qué imagen está vinculada. Si no lo está, responde 'No'."""}
    ]

    respuesta = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=50
    )
    
    contenido = respuesta.choices[0].message.content.strip().lower()
    if "sí" in contenido:
        return True, contenido  # Contiene imagen y vínculo
    return False, contenido  # No contiene imagen

def extraer_preguntas_con_imagen_ia(archivo_entrada, archivo_salida):
    """
    Procesa el archivo de preguntas y extrae aquellas relacionadas con imágenes usando IA.
    """
    preguntas_con_imagen = []
    total_preguntas_con_imagen = 0
    max_preguntas_con_imagen = 25  # Máximo de preguntas con imagen
    max_iteraciones = 10  # Límite para pruebas

    with open(archivo_entrada, "r", encoding="utf-8") as file:
        contenido = file.read()
        # Dividir el contenido en bloques de preguntas
        preguntas = contenido.split("----------------------------------------")
        
        for i, pregunta in enumerate(preguntas):
            if i >= max_iteraciones:  # Limitar a 10 iteraciones para pruebas
                print("Límite de iteraciones alcanzado para pruebas.")
                break
            
            contiene_imagen, resultado = es_pregunta_con_imagen(pregunta)
            
            if contiene_imagen:
                preguntas_con_imagen.append(pregunta.strip())
                total_preguntas_con_imagen += 1
                print(f"Pregunta {i + 1}: Contiene imagen. Detalles: {resultado}")
            else:
                print(f"Pregunta {i + 1}: No contiene imagen. Enunciado:\n{pregunta.strip()[:100]}...")  # Muestra el primer fragmento del enunciado
            
            if total_preguntas_con_imagen >= max_preguntas_con_imagen:
                print("Se alcanzó el límite de preguntas con imágenes.")
                break
    
    # Guardar las preguntas extraídas en el archivo de salida
    with open(archivo_salida, "w", encoding="utf-8") as salida:
        salida.write("\n----------------------------------------\n".join(preguntas_con_imagen))
    
    print(f"Se han extraído {total_preguntas_con_imagen} preguntas relacionadas con imágenes.")
    print(f"Archivo generado: {archivo_salida}")

# Ejecutar la extracción
extraer_preguntas_con_imagen_ia(archivo_preguntas, archivo_salida)
