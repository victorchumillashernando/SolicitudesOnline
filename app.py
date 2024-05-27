import streamlit as st
import time
import openai
import numpy as np
import json
from heapq import nsmallest
import os
import psycopg2

conexion = psycopg2.connect(
            dbname=st.secrets["dbname"],
            user=st.secrets["user"],
            password=st.secrets["password"],
            host=st.secrets["host"],  # o la dirección de tu servidor PostgreSQL
            port="5432"       # el puerto por defecto de PostgreSQL es 5432
        )

cursor = conexion.cursor()


    
        

openai.api_type = "azure"
openai.api_key = st.secrets["key"]
openai.api_base = st.secrets["base"]
openai.api_version = "2023-05-15"

promptInicial = """
Eres un asistente amigable y útil para los usuarios que tienen preguntas sobre los sistemas Mediaset.
Si no recibes ningún dato para responder pero la pregunta no es sobre el sistema usuarios o cualquier cosa especifica, debes responder de la manera que consideres, siempre amigable.
Si no recibes datos y la pregunta es sobre sistemas de Mediaset o cualquier cosa especifica responde que no tienes datos.
"""

with open('campos.json', 'r') as archivo:
    nombres_datos = json.load(archivo)

with open("recursos_modificados.json", "r") as archivo:
    datos = json.load(archivo)

def obtener_nombre_por_id(id, nombres_datos):
    for elemento in nombres_datos:
        if elemento['id'] == id:
            return elemento['label']
    return None

def obtener_ayuda_por_id(id, nombres_datos):
    for elemento in nombres_datos:
        if elemento['id'] == id:
            return elemento['ayuda']
    return None

def guardar_lista(lista):
    nombre_archivo="lista.txt"
    with open(nombre_archivo, 'w') as archivo:
        for elemento in lista:
            archivo.write(elemento + '\n')

# Leer una lista desde un archivo .txt
def leer_lista():
    nombre_archivo="lista.txt"
    lista = []
    if os.path.isfile(nombre_archivo):
        with open(nombre_archivo, 'r') as archivo:
            for linea in archivo:
                lista.append(linea.strip())
    return lista
    
def borrar_archivo():
    if os.path.exists("lista.txt"):
        os.remove("lista.txt")

def embedded(text):
    response = openai.Embedding.create( 
            input=[text],engine="embedding"
            )
    embedding = response['data'][0]['embedding']
    return embedding

def recursosCercanos(texto):
    nuevo_embedding = embedded(texto)

    elementos_cercanos = []

    # Calcular la distancia euclidiana para cada elemento y mantener un seguimiento de los 3 más cercanos
    for elemento in datos:
        embedding = np.array(elemento["embeddingNombre"])
        distancia = np.linalg.norm(embedding - nuevo_embedding)
        elementos_cercanos.append((distancia, elemento["nombre"]))

    # Obtener los 3 elementos más cercanos
    n = 2
    elementos_mas_cercanos = nsmallest(n, elementos_cercanos, key=lambda x: x[0])

    # Imprimir los 3 elementos más cercanos
    return elementos_mas_cercanos

# Streamed response emulator
def response_generator(prompt):

    embedding = embedded(prompt)
    embedding_array = np.array(embedding)
    embedding_list = embedding_array.tolist()
    cursor.execute("""SELECT documentName,text, 1-(vector <=> %s::vector) as cosine_similarity
            FROM embeddings
            ORDER BY cosine_similarity DESC
            LIMIT 1""", (embedding_list,))
    resultados=cursor.fetchall()
    text2=resultados[0][1]
    #Similarity check
    if(resultados[0][2]<0.80):
        text2="No data"


    text = openai.ChatCompletion.create(
        engine="gpt-3-5",
        messages=[
            {"role": "system", "content": promptInicial},
            {"role": "user", "content":"QUESTION TO ANSWER:\n"+ prompt+"\nDATA TO ANSWER:\n"+text2},
        ],
        temperature=0.0,
    )
    response = text["choices"][0]["message"]["content"]
    return response

st.title("Mediaset Solicitudes Online")

elementos=leer_lista()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("¿En qué puedo ayudarte?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant response in chat message container
    with st.spinner("Espera un momento, estoy procesando tu solicitud..."):
        response = response_generator(prompt)
        
        elementos3=recursosCercanos(prompt)
        print(elementos3[0][0])

        if elementos3[0][0]<0.55:
            nombres_elementos= [nombre for _, nombre in elementos3]
            response=response+"\n\nSi no te he podido ayudar puedes probar con alguna de estas solicitudes"

        else:
            nombres_elementos=[]

        st.write(response)
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
        guardar_lista(nombres_elementos)
        elementos=leer_lista()

print(elementos)
if  st.session_state.messages != [] and elementos:
    print(f"dentro{elementos}")
    # Agregar un formulario desplegable al hacer clic en el botón
    string=elementos[0]
    nombres_elementos = elementos

    # Obtener los maestroCampoRecursoId del primer elemento
    maestroCampoRecursoIds = [campo['maestroCampoRecursoId'] for elemento in datos if elemento['nombre'] == nombres_elementos[0] for campo in elemento['maestroCamposRecursos']]

    # Obtener los nombres relativos a los IDs del primer elemento
    nombres_relativos = [obtener_nombre_por_id(id, nombres_datos) for id in maestroCampoRecursoIds]
    ayuda_relativos = [obtener_ayuda_por_id(id, nombres_datos) for id in maestroCampoRecursoIds]

    if st.button(string):
        st.write("Por favor, ingresa los siguientes datos:")
        with st.form("form"):
            for i,nombre in enumerate(nombres_relativos):
                nombre=st.text_input(nombre,help=ayuda_relativos[i])
            submit_button = st.form_submit_button(label="Enviar")

    # Obtener los maestroCampoRecursoId del primer elemento
    maestroCampoRecursoIds = [campo['maestroCampoRecursoId'] for elemento in datos if elemento['nombre'] == nombres_elementos[1] for campo in elemento['maestroCamposRecursos']]

    # Obtener los nombres relativos a los IDs del primer elemento
    nombres_relativos = [obtener_nombre_por_id(id, nombres_datos) for id in maestroCampoRecursoIds]
    ayuda_relativos = [obtener_ayuda_por_id(id, nombres_datos) for id in maestroCampoRecursoIds]
    print(nombres_relativos)
    string2=elementos[1]
    if st.button(string2):
        st.write("Por favor, ingresa los siguientes datos:")
        with st.form("form"):
            for i, nombre in enumerate (nombres_relativos):
                nombre=st.text_input(nombre,help=ayuda_relativos[i])
            submit_button = st.form_submit_button(label="Enviar")
    
