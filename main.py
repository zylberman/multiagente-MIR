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

def chat_with_groq(prompt_system, prompt_user):
    """
    Envía un prompt a Groq y obtiene la respuesta en formato JSON.
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system", 
                    "content": prompt_system}, 
                {
                    "role": "user",
                    "content": prompt_user,
                }
            ],
            model="llama-3.3-70b-versatile",  # Asegúrate de que este modelo esté disponible
        )

        # ✅ Acceder al contenido de la respuesta correctamente
        respuesta_texto = chat_completion.choices[0].message.content  
        return respuesta_texto

    except Exception as e:
        return {"error": str(e)}

def obtener_preguntas():
    obtener_preguntas_imagenes(PDF_PATH)

def separar_preguntas(archivo_entrada, inicio=30, fin=35):
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

# Función para imprimir preguntas
def expert_bot(state: AgentState):
    """El experto responde la pregunta y actualiza el estado."""
    response = chat_with_groq(PROMPTS["expert"], state.query)
    return AgentState(query=state.query, response=json.dumps(response), status="pending")

def revisor_bot(state: AgentState):
    """El revisor evalúa la respuesta y actualiza el estado."""
    review = chat_with_groq(PROMPTS["revisor"], state.response)
    print(f"Este es el resultado de revisor_bot: {review}")

    try:
        review_json = json.loads(review)  # Convertir respuesta de string a JSON
    except json.JSONDecodeError:
        return AgentState(query=state.query, response=json.dumps({"error": "Respuesta inválida del revisor"}), status="fail")

    # Comparar la respuesta generada con la respuesta del experto
    expert_response = json.loads(state.response)  # La respuesta del experto
    errores = []

    if expert_response.get("respuesta_correcta") != review_json.get("respuesta_correcta"):
        errores.append("La respuesta correcta identificada por el revisor no coincide con la respuesta del experto.")

    if review_json.get("errores_detectados"):
        errores.extend(review_json.get("errores_detectados"))

    status = "error" if errores else "ok"
    review_json["errores_detectados"] = errores  # Agregar errores detectados

    # Si ya ha fallado más de 2 veces, marcar como fallo definitivo
    if state.status == "error":
        status = "fail"

    return AgentState(query=state.query, response=json.dumps(review_json), status=status)


def revisión_extra(state: AgentState):
    """Si hay errores, el experto vuelve a revisar la pregunta."""
    print(f"Este es el resultado de una nueva revisión: {state.response}")
    
    # Si ya se ha revisado más de una vez, detener el ciclo
    if "error" in state.status:
        return AgentState(query=state.query, response=json.dumps({"error": "Revisión fallida después de múltiples intentos"}), status="fail")
    
    new_review = chat_with_groq(PROMPTS["expert"], state.query)
    
    try:
        new_review_json = json.loads(new_review)  # Convertir la respuesta a JSON si es necesario
        status = "pending"  # Asumimos que necesita otra revisión
    except json.JSONDecodeError:
        new_review_json = {"error": "Respuesta inválida en revisión extra"}
        status = "fail"

    return AgentState(query=state.query, response=json.dumps(new_review_json), status=status)



# Definir el flujo de trabajo antes de agregar nodos
workflow = StateGraph(AgentState)

# Definir nodos
workflow.add_node("expert", expert_bot)
workflow.add_node("revisor", revisor_bot)
workflow.add_node("revisión_extra", revisión_extra)
workflow.add_node("end", lambda state: state)  # Nodo final

# Definir punto de entrada
workflow.set_entry_point("expert")

# Definir transiciones condicionales
workflow.add_edge("expert", "revisor")
workflow.add_conditional_edges("revisor", lambda state: "revisión_extra" if state.status == "error" else "end")
workflow.add_conditional_edges("revisión_extra", lambda state: "revisor" if state.status == "pending" else "end")

# Compilar el flujo
graph = workflow.compile()

if __name__ == "__main__":
    #obtener_preguntas()
    # Uso de la función
    archivo_preguntas = ARCHIVO_PREGUNTAS  # Asegúrate de que el archivo existe y tiene contenido
    preguntas_seleccionadas = separar_preguntas(archivo_preguntas, 30, 35)

    for i, pregunta in enumerate(preguntas_seleccionadas): # Iterar sobre las preguntas
        print(f"\nProcesando pregunta {i}...")
        print(f"\n{pregunta}")
        print("-" * 50)  # Separador para mayor claridad
        initial_state = AgentState(query=pregunta)
        result = graph.invoke(initial_state)
        print(result)

        





''''
@dataclass
class AgentState:
    query: str
    date: datetime 
    response: str

# Definir edges y flujo de control
workflow.add_edge(START, "validate")
workflow.add_edge("summary", END)

# Añadimos los nodos definidos al grafo de estados
workflow.add_node("validate", validar_activo)
workflow.add_node("search", buscar_noticias)
workflow.add_node("analyze", analizar_noticias)
workflow.add_node("summary", resumir_sentimiento)

workflow.add_edge("validate", "search")
# Reemplazar la arista que iba de "search" -> "evaluate" a "search" -> "analyze"
workflow.add_edge("search", "analyze")
# Conectar "analyze" -> "summary"
workflow.add_edge("analyze", "summary")


# Condición: si la validación es exitosa, pasa a "search", de lo contrario, se queda en "validate"
workflow.add_conditional_edges("validate", lambda state: "search" if state.response == "valid" else "END")

# Compilar el grafo
graph = workflow.compile()

# ----------
# Ejecución del flujo
# ----------
def obtener_sentimiento(query: str, date: str) -> dict:
    # Inicializar el estado del agente
    initial_state = AgentState(query=query, date=date, response="")

    # Ejecutar el flujo
    result = graph.invoke(initial_state)
'''