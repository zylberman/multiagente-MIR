# Definimos la estructura (estado) que queremos manejar con dataclasses,
# en este caso tiene dos campos: 'query' (la consulta a realizar) y 'response' (la respuesta obtenida).
from dataclasses import dataclass
from http import client
from groq import Groq
import datetime
import textwrap
from http import client
import os
import re
from preguntas import obtener_preguntas_imagenes
from openai import OpenAI
from dotenv import load_dotenv

PDF_PATH = os.getenv("PDF_PATH")
ARCHIVO_PREGUNTAS = os.getenv("ARCHIVO_PREGUNTAS")
role = "system"

# Definir el contenido del sistema
content = textwrap.dedent("""
Eres un experto en la resolución de examenes MIR (España), médico con amplia experiencia. Recibirás una pregunta con varias opciones y deberás devolver la respuesta en formato JSON **estricto y válido**, siguiendo esta estructura:

{
  "pregunta": "Texto exacto de la pregunta.",
  "opciones": {
    "Opción 1": "Explicación detallada de por qué es correcta o incorrecta.",
    "Opción 2": "Explicación detallada de por qué es correcta o incorrecta.",
    "Opción 3": "Explicación detallada de por qué es correcta o incorrecta.",
    "Opción 4": "Explicación detallada de por qué es correcta o incorrecta.",
    ...
  },
  "respuesta_correcta": "Texto exacto de la opción correcta"
}

### **Instrucciones importantes**:
1. **Cada opción debe incluir una justificación** clara, precisa y fundamentada en evidencia médica.
2. **Solo una opción puede ser la respuesta correcta**, asegurando que `"respuesta_correcta"` coincida con una de las opciones listadas.
3. **El formato JSON debe ser válido y sin errores sintácticos**, asegurando que se pueda interpretar sin fallos.
4. **Debe respetar la terminología médica** y evitar respuestas ambiguas o incorrectas.
""")

# Configurar el cliente de Groq
load_dotenv()  # Esto carga las variables de entorno desde el .env
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def chat_with_groq(content, prompt):
    """
    Envía un prompt a Groq y obtiene la respuesta en formato JSON.
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": content
                },
                {
                    "role": "user",
                    "content": prompt,
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
def imprimir_preguntas(preguntas):
    """
    Imprime cada pregunta en pantalla.
    :param preguntas: Lista de preguntas en texto.
    """
    for i, pregunta in enumerate(preguntas): # Iterar sobre las preguntas
        print(f"\nProcesando pregunta {i}...")
        print(f"\n{pregunta}")
        print(f"\n{chat_with_groq(content, pregunta)}")
        print("-" * 50)  # Separador para mayor claridad

if __name__ == "__main__":
    #obtener_preguntas()
    # Uso de la función
    archivo_preguntas = ARCHIVO_PREGUNTAS  # Asegúrate de que el archivo existe y tiene contenido
    preguntas_seleccionadas = separar_preguntas(archivo_preguntas, 30, 35)

    # Imprimir las preguntas seleccionadas
    imprimir_preguntas(preguntas_seleccionadas)



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