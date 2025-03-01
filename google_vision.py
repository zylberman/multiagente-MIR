from google.cloud import vision
import io, os
from dotenv import load_dotenv

load_dotenv()

# Configurar credenciales en el código
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]=os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Crear un cliente de Vision AI
client = vision.ImageAnnotatorClient()

# Ruta de la imagen a analizar
image_path = "salidas/imagenes/IMAGEN_2.png"

# Cargar la imagen en formato bytes
with io.open(image_path, "rb") as image_file:
    content = image_file.read()

image = vision.Image(content=content)

# Realizar la detección de etiquetas en la imagen
response = client.label_detection(image=image)
labels = response.label_annotations

# Mostrar etiquetas detectadas
print("Etiquetas detectadas:")
for label in labels:
    print(f"{label.description} (Confianza: {label.score:.2f})")

