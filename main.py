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
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
# 🔹 Función para interactuar con Qwen con los mismos parámetros que chat_with_groq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, MessagesState, START
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

# Configuración de dos modelos de lenguaje que se ejecutan en local a través de LM Studio.
# openai_api_base indica la dirección base del servidor donde corre el modelo
# openai_api_key se usa para autenticar (aquí es un valor ficticio porque se está usando LM Studio local)
llm_qwen = ChatOpenAI(
    openai_api_base="http://localhost:1234/v1",  
    openai_api_key="lm-studio",  
    model_name="qwen2.5-7b-instruct-1m"
)

llm_dseek = ChatOpenAI(
    openai_api_base="http://localhost:1234/v1",  
    openai_api_key="lm-studio",  
    model_name="deepseek-r1-distill-llama-8b"
)

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

# 🔹 Función para elegir el modelo adecuado y realizar la consulta
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
            return json.dumps(clean_json_response(chat_completion.choices[0].message.content), ensure_ascii=False, indent=4)

        except Exception as e:
            error_message = str(e)
            if "rate_limit_exceeded" in error_message:
                print(f"🚨 Límite de tokens alcanzado. Reintentando en {delay} segundos... ({retries+1}/{max_retries})")
                time.sleep(delay)
                retries += 1
                continue  

            return json.dumps({"error": f"Error al comunicarse con Groq: {error_message}"}, ensure_ascii=False, indent=4)

def chat_with_qwen(prompt_system, prompt_user, max_retries=3, delay=10):
    """
    Envía un prompt a Qwen y obtiene la respuesta en formato JSON.
    - Implementa reintento automático en caso de error.
    - Maneja la limpieza de la respuesta JSON.
    """
    retries = 0
    messages = [
        SystemMessage(content=prompt_system),
        HumanMessage(content=prompt_user)
    ]

    while retries < max_retries:
        try:
            response = llm_qwen.invoke(messages)
            response_content = response.content
            return json.dumps(clean_json_response(response_content), ensure_ascii=False, indent=4)

        except Exception as e:
            error_message = str(e)
            print(f"❌ Error al comunicarse con Qwen: {error_message}")
            print(f"🚨 Reintentando en {delay} segundos... ({retries + 1}/{max_retries})")
            time.sleep(delay)
            retries += 1

    return json.dumps({"error": "Límite de reintentos alcanzado."}, ensure_ascii=False, indent=4)

def chat_with_dseek(prompt_system, prompt_user, max_retries=3, delay=10):
    """
    Envía un prompt a DeepSeek y obtiene la respuesta en formato JSON.
    - Implementa reintento automático en caso de error.
    - Asegura que la respuesta incluya 'respuesta_correcta'.
    """
    retries = 0
    messages = [
        SystemMessage(content=prompt_system),
        HumanMessage(content=prompt_user)
    ]

    while retries < max_retries:
        try:
            response = llm_dseek.invoke(messages)
            
            if not response or not response.content:
                raise ValueError("❌ Respuesta vacía del modelo.")

            response_content = response.content.strip()  # Elimina espacios innecesarios
            
            print(f"🔍 RESPUESTA CRUDA DE DEEPSEEK:\n{response_content}")  # Debug: Ver la respuesta real

            # Buscar si la respuesta contiene un JSON dentro de texto largo
            response_json = clean_json_response(response_content)

            # Intentar extraer 'respuesta_correcta' si no está presente
            if not response_json.get("respuesta_correcta"):
                print("⚠ El modelo no devolvió 'respuesta_correcta'. Intentando extraer de nuevo...")

                match = re.search(r'"respuesta_correcta"\s*:\s*"([^"]+)"', response_content)
                if match:
                    response_json["respuesta_correcta"] = match.group(1)
                else:
                    response_json["respuesta_correcta"] = "No disponible"

            return json.dumps(response_json, ensure_ascii=False, indent=4)

        except Exception as e:
            error_message = str(e)
            print(f"❌ Error al comunicarse con DeepSeek: {error_message}")
            print(f"🚨 Reintentando en {delay} segundos... ({retries + 1}/{max_retries})")
            time.sleep(delay)
            retries += 1

    return json.dumps({"error": "Límite de reintentos alcanzado o respuesta vacía."}, ensure_ascii=False, indent=4)


# 🔹 Función para limpiar bloques de código Markdown (evita duplicación)
def clean_json_response(response_text):
    """Limpia el JSON eliminando bloques Markdown y asegurando que la respuesta sea válida."""
    
    # Eliminar bloques de código Markdown
    response_text_clean = re.sub(r"```json|```", "", response_text, flags=re.MULTILINE).strip()

    # Intentar convertir directamente el string a JSON
    try:
        response_json = json.loads(response_text_clean)
    except json.JSONDecodeError:
        print("⚠ Error: No se pudo decodificar JSON directamente. Intentando extraer JSON dentro del texto...")

        # Buscar cualquier bloque JSON dentro del texto usando expresiones regulares
        match = re.search(r'(\{.*?\})', response_text_clean, re.DOTALL)
        if match:
            try:
                response_json = json.loads(match.group(1))
            except json.JSONDecodeError:
                return {"error": "No se pudo extraer JSON válido.", "raw_response": response_text_clean}
        else:
            return {"error": "No se encontró JSON en la respuesta.", "raw_response": response_text_clean}

    # Asegurar que "respuesta_correcta" esté en formato string (puede venir como lista)
    if isinstance(response_json.get("respuesta_correcta"), list):
        response_json["respuesta_correcta"] = ", ".join(response_json["respuesta_correcta"])
    
    return response_json

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


# 🔹 Función para elegir el modelo adecuado y realizar la consulta
def chat_with_model(model, prompt_system, prompt_user, max_retries=3, delay=10):
    if model == "groq":
        return chat_with_groq(prompt_system, prompt_user, max_retries, delay)
    elif model == "qwen":
        return chat_with_qwen(prompt_system, prompt_user, max_retries, delay)
    elif model == "dseek":
        return chat_with_dseek(prompt_system, prompt_user, max_retries, delay)
    else:
        return json.dumps({"error": "Modelo no reconocido"}, ensure_ascii=False, indent=4)


# 🔹 Función genérica para cada agente
def expert_bot(state: AgentState, model="qwen") -> AgentState:
    """El experto responde la pregunta usando el modelo seleccionado y actualiza el estado."""
    log_section("🧑‍🏫 CONSULTANDO AL EXPERTO")

    prompt_system = json.dumps(PROMPTS["expert"], ensure_ascii=False, indent=4)
    response_text = chat_with_model(model, prompt_system, state.query)

    try:
        response_json = clean_json_response(response_text)
        print("\n\033[1;34m🔹 EXPERTO: \033[0m")  # Azul
        print(json.dumps(response_json.get("respuesta", {}), indent=4, ensure_ascii=False))
        status = response_json.get("status", "error")
    except Exception as e:
        response_json = {"error": f"Respuesta inválida del modelo: {str(e)}"}
        status = "error"

    return AgentState(query=state.query, response=json.dumps(response_json, ensure_ascii=False, indent=4), status=status)


def revisor_bot(state: AgentState, model="qwen") -> AgentState:
    """El revisor revisa la respuesta del experto y valida si el status es ok."""
    log_section("🧐 CONSULTANDO AL REVISOR")

    if isinstance(state.response, str):
        try:
            state.response = json.loads(state.response)
        except json.JSONDecodeError:
            state.response = {"error": "Respuesta inválida del experto"}

    status_experto = state.response.get("status", "error")
    if status_experto == 'error':
        print(f"Hubo un error en el nodo anterior")
    respuesta_experto = state.response.get("respuesta", [])
    errores_detectados = state.response.get("errores", "No especificado")

    revisor_input = {
        "pregunta": state.query,
        "respuesta_experto": respuesta_experto,
        "errores_detectados_experto": errores_detectados,
    }

    prompt_system = json.dumps(PROMPTS["revisor"], ensure_ascii=False, indent=4)
    prompt_user = json.dumps(revisor_input, ensure_ascii=False)

    response_text = chat_with_model(model, prompt_system, prompt_user)

    try:
        response_json = clean_json_response(response_text)
        print("\n\033[1;34m🔹 REVISOR: \033[0m")  # Azul
        print(json.dumps(response_json.get("respuesta", {}), indent=4, ensure_ascii=False))
        print(json.dumps(response_json.get("comparación", {}), indent=4, ensure_ascii=False))
        status = response_json.get("status", "error")
    except json.JSONDecodeError:
        response_json = {"error": "Respuesta inválida del revisor"}
        status = "error"

    return AgentState(query=state.query, response=json.dumps(response_json, ensure_ascii=False), status=status)


def auditor_bot(state: AgentState, model="qwen") -> AgentState:
    """El auditor revisa la pregunta y valida la respuesta."""
    log_section("🔍 CONSULTANDO AL AUDITOR")

    if isinstance(state.response, str):
        try:
            state.response = json.loads(state.response)
        except json.JSONDecodeError:
            state.response = {"error": "Respuesta inválida del revisor"}

    auditor_input = {
        "pregunta": state.query,
        "respuesta_revisor": state.response.get("respuesta", "No disponible"),
        "respuesta_experto": state.response.get("respuesta_expert", "No disponible"),
    }

    prompt_system = json.dumps(PROMPTS["auditor"], ensure_ascii=False, indent=4)
    prompt_user = json.dumps(auditor_input, ensure_ascii=False)

    response_text = chat_with_model(model, prompt_system, prompt_user)

    try:
        response_json = clean_json_response(response_text)
        
        # 🔹 Si la respuesta correcta es una lista, convertir a string
        if isinstance(response_json.get("respuesta_correcta"), list):
            response_json["respuesta_correcta"] = ", ".join(response_json["respuesta_correcta"])

        print("\n\033[1;32m🔹 AUDITOR: \033[0m")  # Verde
        print("📖 RESPUESTA:")
        print(response_json.get("respuesta_correcta", "No disponible"))
        print("🔖 COMENTARIO:")
        print(response_json.get("comentario", "No disponible"))
        status = response_json.get("status", "error")
    except json.JSONDecodeError:
        response_json = {"error": "Respuesta inválida del auditor"}
        status = "error"

    return AgentState(query=state.query, response=json.dumps(response_json, ensure_ascii=False), status=status)


def teacher_bot(state: AgentState, model="qwen") -> AgentState:
    """El profesor responde la pregunta usando el modelo seleccionado."""
    log_section("👨🏻‍🏫 CONSULTANDO AL PROFESOR")

    prompt_system = json.dumps(PROMPTS["teacher"], ensure_ascii=False, indent=4)

    try:
        response_dict = json.loads(state.response)  # Convierte el string JSON a diccionario
    except json.JSONDecodeError:
        return AgentState(query=state.query, response=json.dumps({"error": "Respuesta inválida del revisor"}, ensure_ascii=False), status="error")

    pregunta = response_dict.get("pregunta", "error")
    opciones = response_dict.get("opciones", {})
    respuesta = response_dict.get("respuesta", [])

    teacher_input = {
        "pregunta": pregunta,
        "opciones": opciones,
        "respuesta": respuesta
    }

    prompt_user = json.dumps(teacher_input, ensure_ascii=False)

    response_text = chat_with_model(model, prompt_system, prompt_user)
    
    try:
        response_json = clean_json_response(response_text)
        print("\n\033[1;35m🔹 RESPUESTA DEL PROFESOR: \033[0m")  # Morado
        print(json.dumps(response_json.get("pregunta_explicada", {}), indent=4, ensure_ascii=False))
        print(json.dumps(response_json.get("respuesta_correcta", {}), indent=4, ensure_ascii=False))
        print(json.dumps(response_json.get("respuesta_incorrecta", {}), indent=4, ensure_ascii=False))
        status = response_json.get("status", "error")
    except Exception as e:
        response_json = {"error": f"Respuesta inválida del modelo: {str(e)}"}
        status = "error"

    return AgentState(query=state.query, response=json.dumps(response_json, ensure_ascii=False, indent=4), status=status)


def memory_bot(state: AgentState, model="qwen") -> AgentState:
    """El memory responde la pregunta usando el modelo seleccionado."""
    log_section("🧠 CONSULTANDO AL MEMORY")

    prompt_system = json.dumps(PROMPTS["memory"], ensure_ascii=False, indent=4)

    try:
        response_dict = json.loads(state.response)  # Convierte el JSON string en diccionario
    except json.JSONDecodeError:
        return AgentState(query=state.query, response=json.dumps({"error": "Respuesta inválida del profesor"}, ensure_ascii=False), status="error")

    pregunta = response_dict.get("pregunta_explicada", "")
    respuesta_correcta = response_dict.get("respuesta_correcta", "")
    respuesta_incorrecta = response_dict.get("respuesta_incorrecta", "")

    memory_input = {
        "pregunta": pregunta,
        "respuesta_correcta": respuesta_correcta,
        "respuesta_incorrecta": respuesta_incorrecta
    }

    prompt_user = json.dumps(memory_input, ensure_ascii=False)

    response_text = chat_with_model(model, prompt_system, prompt_user)

    try:
        response_json = clean_json_response(response_text)
        print("\n\033[1;35m🔹 RESPUESTA DE MEMORY: \033[0m")  # Morado
        print(json.dumps(response_json.get("resumen", {}), indent=4, ensure_ascii=False))
        print(json.dumps(response_json.get("asociaciónes_inverosimiles", {}), indent=4, ensure_ascii=False))
        print(json.dumps(response_json.get("historia", {}), indent=4, ensure_ascii=False))
        status = response_json.get("status", "error")
    except Exception as e:
        response_json = {"error": f"Respuesta inválida del modelo: {str(e)}"}
        status = "error"

    return AgentState(query=state.query, response=json.dumps(response_json, ensure_ascii=False, indent=4), status=status)


# Modificar el flujo de trabajo
graph = StateGraph(AgentState)

graph.add_node("expert", expert_bot)
graph.add_node("revisor", revisor_bot)
graph.add_node("auditor", auditor_bot)
graph.add_node("teacher", teacher_bot)
graph.add_node("memory", memory_bot)
graph.add_node("end", lambda state: state)

# Punto de entrada
graph.set_entry_point("expert")

# Expert siempre pasa a Revisor
graph.add_edge("expert", "revisor")

# Si Revisor encuentra errores, pasa a Auditor. Si no, pasa a Teacher
graph.add_conditional_edges("revisor", lambda state: "auditor" if json.loads(state.response).get("comparación") == "diferentes" else "teacher")

# Auditor siempre pasa a Teacher
graph.add_edge("auditor", "teacher")

# Teacher siempre pasa a Memory
graph.add_edge("teacher", "memory")

# Memory finaliza
graph.add_edge("memory", "end")

# Compilar el flujo
graph = graph.compile()

import sys

try:
    import msvcrt  # Windows
    def esperar_tecla():
        """Espera a que el usuario presione una tecla en Windows. Si es 's', finaliza el programa."""
        print("\n\033[93m🔹 Presiona cualquier tecla para continuar o 's' para salir... 🔹\033[0m", end="", flush=True)
        tecla = msvcrt.getch().decode("utf-8").lower()  # Captura la tecla presionada
        print("\n")  # Salto de línea después de presionar la tecla

        if tecla == 's':
            print("\033[92m✅ Finalizando la ejecución.\033[0m")
            sys.exit(0)  # Termina el programa inmediatamente

except ImportError:
    import termios, tty  # macOS / Linux
    def esperar_tecla():
        """Espera a que el usuario presione una tecla en macOS/Linux. Si es 's', finaliza el programa."""
        print("\n\033[93m🔹 Presiona cualquier tecla para continuar o 's' para salir... 🔹\033[0m", end="", flush=True)
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            tecla = sys.stdin.read(1).lower()  # Leer un solo carácter y convertirlo a minúscula
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        print("\n")  # Salto de línea después de la tecla

        if tecla == 's':
            print("\033[92m✅ Finalizando la ejecución.\033[0m")
            sys.exit(0)  # Termina el programa inmediatamente


if __name__ == "__main__":
    archivo_preguntas = ARCHIVO_PREGUNTAS  
    max_preguntas = 210  # Límite máximo de preguntas a procesar
    inicio = int(input("Ingrese el número de la primera pregunta a procesar: "))
    fin = inicio + 4  # Se procesan 5 preguntas por iteración

    while inicio <= max_preguntas:
        preguntas_seleccionadas = separar_preguntas(archivo_preguntas, inicio, fin)

        if not preguntas_seleccionadas:
            print("\033[91m🚨 No hay más preguntas disponibles en el rango seleccionado.\033[0m")
            break

        for i, pregunta in enumerate(preguntas_seleccionadas, start=inicio):  # Iterar sobre las preguntas
            log_section(f"📌 Procesando pregunta {i}")
            print(f"\n{pregunta}\n" + "-" * 60)

            initial_state = AgentState(query=pregunta)
            result = graph.invoke(initial_state)

            # 🔹 CORRECCIÓN: Acceder a response correctamente
            try:
                response_json = json.loads(result["response"])
                final_status = response_json.get("status", "error")
                respuesta_correcta = response_json.get("respuesta_correcta", "No disponible")
            except json.JSONDecodeError:
                log_error("❌ Error al interpretar la respuesta JSON del flujo.")
                final_status = "error"
                respuesta_correcta = "No disponible"

            log_final_result(final_status, respuesta_correcta)

            # ✅ Llamar a la función universal para esperar la tecla o salir con 's'
            esperar_tecla()

        # Preguntar al usuario si desea continuar con 5 preguntas más
        continuar = input("¿Desea continuar con 5 preguntas más? (s/n): ").strip().lower()
        if continuar == 's':
            print("\033[92m✅ Finalizando la ejecución.\033[0m")
            break

        # Incrementar el rango de preguntas
        inicio = fin + 1
        fin = min(inicio + 4, max_preguntas)  # Evitar sobrepasar el límite de 210 preguntas

    print("\033[92m✅ Se han procesado todas las preguntas dentro del límite establecido.\033[0m")

