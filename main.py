# Definimos la estructura (estado) que queremos manejar con dataclasses,
# en este caso tiene dos campos: 'query' (la consulta a realizar) y 'response' (la respuesta obtenida).
from dataclasses import dataclass
from http import client
from groq import Groq
from http import client
import os
import re
import json
from preguntas import obtener_preguntas_imagenes
from openai import OpenAI
from langgraph.graph import Graph
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph, START 
import time

PDF_PATH = os.getenv("PDF_PATH")
ARCHIVO_PREGUNTAS = os.getenv("ARCHIVO_PREGUNTAS")
role = "system"

# Cargar prompts desde un archivo JSON
def load_prompts(json_path="prompts.json"):
    with open(json_path, "r", encoding="utf-8") as file:
        return json.load(file)

# Cargar los prompts en una variable global
PROMPTS = load_prompts()

# Configurar el cliente de Groq
load_dotenv()  # Esto carga las variables de entorno desde el .env
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

@dataclass
class AgentState:
    query: str
    response: str = ""
    status: str = "pending"

# 🔹 Función para imprimir secciones con formato mejorado
def log_section(title):
    """Imprime un título en la consola con un formato claro."""
    print("\n\033[94m" + "=" * 70 + "\033[0m")  # Azul
    print(f"\033[1;36m🔹 {title.upper()} 🔹\033[0m")  # Cyan Negrita
    print("\033[94m" + "=" * 70 + "\033[0m")

# 🔹 Función para mostrar errores en rojo con más detalle
def log_error(msg):
    print(f"\033[91m🚨 ERROR: {msg}\033[0m")

# 🔹 Función para mostrar el resultado final de cada pregunta
def log_final_result(status, respuesta_correcta):
    print("\n\033[92m✅ RESULTADO FINAL 🔎\033[0m")  # Verde
    if status == "ok":
        print("\033[1;32m✔ Pregunta validada correctamente 🎯\033[0m")  # Verde Negrita
        print(f"\033[1;36m🔹 Respuesta correcta: {respuesta_correcta}\033[0m")
    else:
        print("\033[1;31m❌ Se requiere revisión ⚠\033[0m")  # Rojo Negrita
    print("=" * 70)

def chat_with_groq(prompt_system, prompt_user, max_retries=3, delay=10):
    """
    Envía un prompt a Groq y obtiene la respuesta en formato JSON.
    - Implementa reintento automático en caso de 'rate_limit_exceeded'.
    - Mejora el manejo de errores de JSON.
    """
    retries = 0

    while retries < max_retries:
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": prompt_system}, 
                    {"role": "user", "content": prompt_user}
                ],
                model="llama-3.3-70b-versatile",  
            )
            respuesta_texto = chat_completion.choices[0].message.content  

            # Eliminar posibles bloques de código Markdown (` ```json ... ``` `)
            respuesta_texto_clean = re.sub(r"```json|```", "", respuesta_texto).strip()

            # Intentar convertir la respuesta a JSON limpio
            try:
                respuesta_json = json.loads(respuesta_texto_clean)
                return json.dumps(respuesta_json, ensure_ascii=False, indent=4)
            except json.JSONDecodeError:
                log_error("❌ La respuesta del modelo no es JSON válido.")
                print(respuesta_texto_clean)
                return json.dumps({
                    "error": "La respuesta del modelo no es JSON válido.",
                    "raw_response": respuesta_texto_clean
                }, ensure_ascii=False, indent=4)

        except Exception as e:
            error_message = str(e)

            # Detectar si el error es por 'rate_limit_exceeded'
            if "rate_limit_exceeded" in error_message:
                log_error(f"🚨 Límite de tokens alcanzado. Reintentando en {delay} segundos... ({retries+1}/{max_retries})")
                print(f"error_message: {error_message}")
                time.sleep(delay)  # Esperar antes de reintentar
                retries += 1
                continue  # Intentar de nuevo

            # Cualquier otro error se muestra de inmediato
            log_error(f"❌ Error al comunicarse con Groq: {error_message}")
            return json.dumps({
                "error": f"Error al comunicarse con Groq: {error_message}"
            }, ensure_ascii=False, indent=4)

    # Si se alcanzó el máximo de reintentos
    log_error("🚨 Se alcanzó el límite de reintentos. No se pudo completar la consulta.")
    return json.dumps({"error": "Límite de reintentos alcanzado. Inténtalo más tarde."}, ensure_ascii=False, indent=4)


def obtener_preguntas():
    obtener_preguntas_imagenes(PDF_PATH)

def separar_preguntas(archivo_entrada, inicio=30, fin=31):
    """
    Extrae un rango específico de preguntas desde un archivo de texto.
    
    :param archivo_entrada: Ruta del archivo de texto que contiene las preguntas.
    :param inicio: Número de la primera pregunta a extraer.
    :param fin: Número de la última pregunta a extraer.
    :return: Lista de preguntas en formato de texto.
    """
    with open(archivo_entrada, "r", encoding="utf-8") as file:
        contenido = file.read()

    # Dividir las preguntas utilizando el separador
    bloques = contenido.split("----------------------------------------")

    # Filtrar preguntas dentro del rango deseado
    preguntas_filtradas = []
    
    for bloque in bloques:
        bloque = bloque.strip()  # Eliminar espacios en blanco innecesarios
        
        # Buscar el número de pregunta
        match = re.search(r"Pregunta (\d+):", bloque)
        
        if match:
            numero_pregunta = int(match.group(1))
            
            if inicio <= numero_pregunta <= fin:
                preguntas_filtradas.append(bloque)

    return preguntas_filtradas

# Función para Expert
def expert_bot(state: AgentState) -> AgentState:
    """El experto responde la pregunta y actualiza el estado."""
    log_section("🧑‍🏫 CONSULTANDO AL EXPERTO")
    response_text = chat_with_groq(json.dumps(PROMPTS["expert"], ensure_ascii=False, indent=4), state.query)
    
    try:
        # Eliminar posibles backticks ``` que rodean el JSON
        response_text_clean = re.sub(r"```json|```", "", response_text).strip()
        response_json = json.loads(response_text_clean)  # Convertir a JSON
        status = response_json.get("status", "error")  # Si no hay status, asumimos error
    except json.JSONDecodeError:
        response_json = {"error": "Respuesta inválida del expert"}
        status = "error"

    return AgentState(query=state.query, response=json.dumps(response_json), status=status)


# Función para Revisor
def revisor_bot(state: AgentState) -> AgentState:
    """El revisor revisa la respuesta del experto y actualiza el estado."""
    log_section("🧐 CONSULTANDO AL REVISOR")

    # Asegurarse de que la respuesta del experto es un diccionario válido
    if isinstance(state.response, str):
        try:
            state.response = json.loads(state.response)
        except json.JSONDecodeError:
            state.response = {"error": "Respuesta inválida del experto"}

    revisor_input = {
        "pregunta": state.query,
        "respuesta_experto": state.response.get("respuesta_correcta", "No disponible"),
        "errores_detectados_experto": state.response.get("error_detectado", "Ninguno"),
    }
    # Pasar `revisor_input` como string JSON válido a `chat_with_groq()`
    response_text = chat_with_groq(json.dumps(PROMPTS["revisor"], ensure_ascii=False, indent=4), json.dumps(revisor_input, ensure_ascii=False))

    try:
        # LIMPIAR posibles bloque de código ```json ... ```
        response_text_clean = re.sub(r"```json|```", "", response_text).strip()
        response_json = json.loads(response_text_clean)  # Convertimos a JSON
        status = response_json.get("status", "error")  # Si no hay status, asumimos error
    except json.JSONDecodeError:
        response_json = {"error": "Respuesta inválida del revisor"}
        status = "error"

    return AgentState(query=state.query, response=json.dumps(response_json, ensure_ascii=False), status=status)


# Función para Auditor
def auditor_bot(state: AgentState) -> AgentState:
    """El auditor revisa la pregunta y valida la respuesta."""
    log_section("🔍 CONSULTANDO AL AUDITOR")
    # Asegurar que la respuesta del revisor es un diccionario válido
    if isinstance(state.response, str):
        try:
            state.response = json.loads(state.response)
        except json.JSONDecodeError:
            state.response = {"error": "Respuesta inválida del revisor"}

    auditor_input = {
        "pregunta": state.query,
        "respuesta_experto": state.response.get("respuesta_correcta", "No disponible"),
        "errores_detectados_experto": state.response.get("error_detectado", "Ninguno"),
        "respuesta_revisor": state.response.get("respuesta_correcta", "No disponible"),
        "errores_detectados_revisor": state.response.get("errores_detectados", []),
    }

    response_text = chat_with_groq(json.dumps(PROMPTS["auditor"], ensure_ascii=False, indent=4), json.dumps(auditor_input, ensure_ascii=False))

    try:
        # LIMPIAR posibles bloques de código ```json ... ```
        response_text_clean = re.sub(r"```json|```", "", response_text).strip()
        response_json = json.loads(response_text_clean)  # Convertimos a JSON
        status = response_json.get("status", "error")  # Si no hay status, asumimos error
    except json.JSONDecodeError:
        response_json = {"error": "Respuesta inválida del auditor"}
        status = "error"

    return AgentState(query=state.query, response=json.dumps(response_json, ensure_ascii=False), status=status)



# Definir el flujo de trabajo en LangGraph
workflow = StateGraph(AgentState)

# Definir nodos
workflow.add_node("expert", expert_bot)
workflow.add_node("revisor", revisor_bot)
workflow.add_node("auditor", auditor_bot)
workflow.add_node("end", lambda state: state)

# Definir punto de entrada
workflow.set_entry_point("expert")

# Transiciones condicionales
workflow.add_edge("expert", "revisor")
workflow.add_conditional_edges("revisor", lambda state: "auditor" if state.status == "error" else "end")
workflow.add_conditional_edges("auditor", lambda state: "end")

# Compilar el flujo
graph = workflow.compile()

if __name__ == "__main__":
    #obtener_preguntas()
    # Uso de la función
    archivo_preguntas = ARCHIVO_PREGUNTAS  # Asegúrate de que el archivo existe y tiene contenido
    preguntas_seleccionadas = separar_preguntas(archivo_preguntas, 30, 31)

    for i, pregunta in enumerate(preguntas_seleccionadas): # Iterar sobre las preguntas
        log_section(f"📌 Procesando pregunta {i+1}")
        print(f"\n{pregunta}\n" + "-" * 60)

        initial_state = AgentState(query=pregunta)
        result = graph.invoke(initial_state)

        # 🔹 CORRECCIÓN: Acceder a response correctamente
        try:
            final_status = json.loads(result["response"]).get("status", "error")
            respuesta_correcta = json.loads(result["response"]).get("respuesta_correcta", "No disponible")
        except json.JSONDecodeError:
            log_error("❌ Error al interpretar la respuesta JSON del flujo.")
            final_status = "error"
            respuesta_correcta = "No disponible"

        log_final_result(final_status, respuesta_correcta)


