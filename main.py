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
                {"role": "system", "content": prompt_system}, 
                {"role": "user", "content": prompt_user}
            ],
            model="llama-3.3-70b-versatile",  
        )

        respuesta_texto = chat_completion.choices[0].message.content  
        
        # Intentar convertir la respuesta a JSON
        try:
            respuesta_json = json.loads(respuesta_texto)
            return json.dumps(respuesta_json, ensure_ascii=False, indent=4)
        except json.JSONDecodeError:
            return json.dumps({
                "error": "La respuesta del modelo no es JSON válido.",
                "raw_response": respuesta_texto
            }, ensure_ascii=False, indent=4)

    except Exception as e:
        return json.dumps({
            "error": f"Error al comunicarse con Groq: {str(e)}"
        }, ensure_ascii=False, indent=4)




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
def expert_bot(state: AgentState):
    """El experto responde la pregunta y actualiza el estado."""
    print("\nConsultando al experto...\n")
    response_text = chat_with_groq(PROMPTS["expert"], state.query)   
    print(f"Respuesta del experto: {response_text}")
    try:
        response_json = json.loads(response_text)  # Convertimos a JSON
        status = response_json.get("status", "error")  # Si no hay status, asumimos error
    except json.JSONDecodeError:
        response_json = {"error": "Respuesta inválida del expert"}
        status = "error"

    return AgentState(query=state.query, response=json.dumps(response_json), status=status)

# Función para Revisor
def revisor_bot(state: AgentState):
    print("\n🔎 Consultando al REVISOR...\n")
    
    # El revisor responde la pregunta de forma independiente
    review_text = chat_with_groq(PROMPTS["revisor"], state.query)
    print(f"🔹 Respuesta del revisor (texto crudo): {review_text}")

    # Intentar convertir la respuesta del revisor en JSON
    try:
        review_json = json.loads(review_text)
        status = review_json.get("status", "ok")
    except json.JSONDecodeError:
        review_json = {
            "error": "❌ Respuesta del revisor no es JSON válido.",
            "raw_response": review_text
        }
        return AgentState(
            query=state.query,
            response=json.dumps(review_json, ensure_ascii=False, indent=4),
            status="fail"
        )

    # Verificar si el experto dio una respuesta válida antes de compararlas
    try:
        expert_response = json.loads(state.response)
    except json.JSONDecodeError:
        expert_response = {"error": "❌ Respuesta inválida del experto. No es JSON válido."}
        review_json["errores_detectados"] = ["⚠️ Error: La respuesta del experto no es válida para comparar."]
        return AgentState(
            query=state.query,
            response=json.dumps(review_json, ensure_ascii=False, indent=4),
            status="error"
        )

    errores = []

    # Comparar la respuesta del revisor con la del experto
    if (
        "respuesta_correcta" in expert_response
        and "respuesta_correcta" in review_json
        and expert_response["respuesta_correcta"] != review_json["respuesta_correcta"]
    ):
        errores.append("⚠️ Discrepancia: La respuesta del revisor NO coincide con la del experto.")

    # Si el revisor detectó errores en la pregunta, los agregamos a la lista de errores
    if review_json.get("errores_detectados"):
        errores.extend(review_json["errores_detectados"])

    # Si hay errores o discrepancias, se envía la respuesta al auditor
    if errores:
        review_json["errores_detectados"] = errores
        status = "error"  # Se requiere auditoría
    else:
        status = "ok"  # No se requiere auditoría

    return AgentState(
        query=state.query,
        response=json.dumps(review_json, ensure_ascii=False, indent=4),
        status=status
    )


# Función para Auditor
def auditor_bot(state: AgentState):
    print("\n🔎 Consultando al AUDITOR...\n")

    # Verificar si la respuesta del revisor es un JSON válido antes de enviarlo
    try:
        revisor_response = json.loads(state.response)
    except json.JSONDecodeError:
        return AgentState(
            query=state.query,
            response=json.dumps({"error": "❌ Respuesta inválida del revisor. No es JSON válido."}, ensure_ascii=False, indent=4),
            status="fail"
        )

    auditor_input = {
        "pregunta": state.query,
        "errores_reportados": revisor_response.get("errores_detectados", []),
        "respuesta_correcta_revisor": revisor_response.get("respuesta_correcta", ""),
        "respuesta_correcta_experto": json.loads(state.response).get("respuesta_correcta", ""),
        "evaluación_error": revisor_response.get("evaluación_error", "indeterminado"),
    }

    audit_text = chat_with_groq(PROMPTS["auditor"], json.dumps(auditor_input, ensure_ascii=False, indent=4))
    print(f"🔹 Respuesta del auditor: {audit_text}")

    try:
        audit_json = json.loads(audit_text)
        status = audit_json.get("status", "ok")  # ✅ Cambiado de "fail" a "ok" por defecto
    except json.JSONDecodeError:
        audit_json = {"error": "❌ Respuesta inválida en auditoría", "raw_response": audit_text}
        status = "fail"

    return AgentState(
        query=state.query,
        response=json.dumps(audit_json, ensure_ascii=False, indent=4),
        status=status
    )




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
        print(f"\nProcesando pregunta {i}...")
        print(f"\n{pregunta}")
        print("-" * 50)  # Separador para mayor claridad
        initial_state = AgentState(query=pregunta)
        result = graph.invoke(initial_state)
        print(result)
