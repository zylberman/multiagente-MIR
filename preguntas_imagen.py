import re
from dotenv import load_dotenv
import os

# Cargar las variables desde el archivo de configuración
load_dotenv("config.env")

# Archivos de entrada y salida
archivo_preguntas = os.getenv("ARCHIVO_PREGUNTAS")
archivo_salida_con_imagen = os.getenv("ARCHIVO_SALIDA_CON_IMAGEN")
archivo_salida_sin_imagen = os.getenv("ARCHIVO_SALIDA_SIN_IMAGEN")
archivo_log_errores = os.getenv("ARCHIVO_LOG_ERRORES")

# Validar las variables cargadas
if not archivo_preguntas:
    raise ValueError("La variable ARCHIVO_PREGUNTAS no está definida en config.env o es inválida.")
if not archivo_salida_con_imagen:
    raise ValueError("La variable ARCHIVO_SALIDA_CON_IMAGEN no está definida en config.env o es inválida.")
if not archivo_salida_sin_imagen:
    raise ValueError("La variable ARCHIVO_SALIDA_SIN_IMAGEN no está definida en config.env o es inválida.")
if not archivo_log_errores:
    raise ValueError("La variable ARCHIVO_LOG_ERRORES no está definida en config.env o es inválida.")

# Crear directorios si no existen
os.makedirs(os.path.dirname(archivo_salida_con_imagen), exist_ok=True)
os.makedirs(os.path.dirname(archivo_salida_sin_imagen), exist_ok=True)
os.makedirs(os.path.dirname(archivo_log_errores), exist_ok=True)

secuencia_imagen = 1  # Número esperado de la primera imagen

def es_pregunta_con_imagen(pregunta):
    patron = r"Pregunta vinculada a la imagen nº (\d+)"
    match = re.search(patron, pregunta)
    if match:
        return True, int(match.group(1))
    return False, None

def extraer_preguntas_con_imagen_ia(archivo_entrada, archivo_salida_con_imagen, archivo_salida_sin_imagen, archivo_log):
    global secuencia_imagen
    preguntas_con_imagen = []
    preguntas_sin_imagen = []
    total_preguntas_con_imagen = 0
    total_preguntas_sin_imagen = 0

    try:
        with open(archivo_entrada, "r", encoding="utf-8") as file:
            contenido = file.read()
            preguntas = contenido.split("----------------------------------------")

            for i, pregunta in enumerate(preguntas, start=1):
                contiene_imagen, numero_imagen = es_pregunta_con_imagen(pregunta)
                
                if contiene_imagen:
                    if numero_imagen == secuencia_imagen:
                        preguntas_con_imagen.append(pregunta.strip())
                        total_preguntas_con_imagen += 1
                        print(f"Pregunta {i}: Contiene imagen {numero_imagen}. Secuencia correcta.")
                        secuencia_imagen += 1
                    else:
                        error_msg = (f"Error: Secuencia de imágenes interrumpida en la pregunta {i}. "
                                     f"Se esperaba imagen {secuencia_imagen}, pero se detectó imagen {numero_imagen}.")
                        print(error_msg)
                        with open(archivo_log, "a", encoding="utf-8") as log:
                            log.write(error_msg + "\n")
                else:
                    preguntas_sin_imagen.append(pregunta.strip())
                    total_preguntas_sin_imagen += 1
                    print(f"Pregunta {i}: No contiene imagen. Enunciado:\n{pregunta.strip()[:100]}...")
    except FileNotFoundError:
        print(f"Error: El archivo {archivo_entrada} no existe.")
        return
    except Exception as e:
        print(f"Error inesperado al procesar las preguntas: {e}")
        return

    # Guardar preguntas con imagen
    with open(archivo_salida_con_imagen, "w", encoding="utf-8") as salida_con_imagen:
        salida_con_imagen.write("\n----------------------------------------\n".join(preguntas_con_imagen))
    print(f"Se han extraído {total_preguntas_con_imagen} preguntas relacionadas con imágenes.")
    print(f"Archivo generado: {archivo_salida_con_imagen}")

    # Guardar preguntas sin imagen
    with open(archivo_salida_sin_imagen, "w", encoding="utf-8") as salida_sin_imagen:
        salida_sin_imagen.write("\n----------------------------------------\n".join(preguntas_sin_imagen))
    print(f"Se han extraído {total_preguntas_sin_imagen} preguntas sin imágenes.")
    print(f"Archivo generado: {archivo_salida_sin_imagen}")

# Ejecutar la extracción
extraer_preguntas_con_imagen_ia(archivo_preguntas, archivo_salida_con_imagen, archivo_salida_sin_imagen, archivo_log_errores)
