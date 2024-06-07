import streamlit as st
import time
import openai
import numpy as np
import json
from heapq import nsmallest
import os
import psycopg2
import hmac
import requests
from requests.auth import HTTPBasicAuth
import datetime

class Campo:
    def __init__(self, id, maestroId, valor):
        self.id = id
        self.maestroId = maestroId
        self.valor = valor

class Payload:
    def __init__(self, idRecursoCatalogo, campos, nivelesRecurso, baja):
        self.idRecursoCatalogo = idRecursoCatalogo
        self.campos = campos
        self.nivelesRecurso = nivelesRecurso
        self.baja = baja

conexion = psycopg2.connect(
            dbname="postgres",
            user="superuser",
            password="Root12345678",
            host="caupostgre.postgres.database.azure.com",  # o la dirección de tu servidor PostgreSQL
            port="5432"       # el puerto por defecto de PostgreSQL es 5432
        )

cursor = conexion.cursor()

values=[]
campos=[]

        

openai.api_type = "azure"
openai.api_key = "4fa9cd946ebc42d281ffbd9d1373e893"
openai.api_base = "https://msoais.openai.azure.com/"
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

def generarToken(usuario):
    # URL a la que deseas hacer el POST
    url = "https://apisolicitudesonlinepre.cinconet.local/api/Auth/login"

    # Credenciales para BasicAuth
    username = usuario
    password = "tu_contraseña"

    # Realizar el POST con autenticación básica
    response = requests.post(url, auth=HTTPBasicAuth(username, password),verify=False)

    #print(response.content)
    response_json = response.json()
    # Analizar el contenido HTML
    validtoken = response_json.get("validToken")
    refreshtoken = response_json.get("refreshToken")
    return validtoken

def callApi(payload,correo):
    validtoken=generarToken(correo)
    payload_dict = payload.__dict__
    payload_dict['campos'] = [campo.__dict__ for campo in payload_obj.campos]

    # Enviar la solicitud
    url = "https://apisolicitudesonlinepre.cinconet.local/api/Recurso/Carrito"
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'Authorization': f'Bearer {validtoken}'
    }

    response = requests.post(url, json=payload_dict, headers=headers, verify=False)
    return response.text

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
        elementos_cercanos.append((distancia, elemento["nombre"],elemento["id"]))

    # Obtener los 3 elementos más cercanos
    n = 2
    elementos_mas_cercanos = nsmallest(n, elementos_cercanos, key=lambda x: x[0])

    # Imprimir los 3 elementos más cercanos
    return elementos_mas_cercanos

def check_password():
    
    """Returns `True` if the user had the correct password."""
    def checkMail():
        try:
            generarToken(st.session_state.correo)
            return True  # Devuelve la respuesta JSON si todo va bien
        except requests.exceptions.RequestException as e:
            # Si ocurre un error de conexión o la API devuelve un error, muestra un mensaje al usuario
            return False
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], "contrasena123") and checkMail():
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    st.text_input(
        "Email:",key="correo"
    )
    # Show input for password.
    st.text_input(
        "Password", type="password", key="password"
    )
    submit_button = st.button(label='Enviar',on_click=password_entered)

    if "password_correct" in st.session_state:
        st.error("😕 Password or email incorrect")
    return False

def submitted():
    st.session_state.submitted = True

def submitted2():
    st.session_state.submitted2 = True

def reset():
    st.session_state.submitted = False

def reset2():
    st.session_state.submitted2= False

def getTipo(nombre,data):
    print(nombre)
    tipo="string"
    for elemento in data:
        if elemento["label"] == nombre:
            tipo= elemento["tipo"]
    print(tipo)
    return tipo
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

# Ruta del logo de la empresa
logo_url = "Mediaset_España.svg.png"

# Mostrar el logo de la empresa en la parte superior
st.image(logo_url, use_column_width=True)

if not check_password():
   st.stop() 

print(st.session_state.correo)
with st.sidebar:
    st.title("Datos Frecuentes")
    st.write("Ingrese la información:")
    
    # Agregar campos para que el usuario los llene
    campo1 = st.text_input("Campo 1")
    campo2 = st.number_input("Campo 2")
    campo3 = st.selectbox("Campo 3", ["Opción 1", "Opción 2", "Opción 3"])

    # Agregar botón de confirmación
    if st.button("Confirmar"):
        st.success("¡Información confirmada!")

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
        if 'id1' not in st.session_state:
            st.session_state.id1=elementos3[0][2]
        if 'id2' not in st.session_state:
            st.session_state.id2=elementos3[1][2]
        print(st.session_state.id1)
        print(st.session_state.id2)
        #print(elementos3[0][0])

        if elementos3[0][0]<0.55:
            nombres_elementos= [elementos3[0][1],elementos3[1][1]]
            response=response+"\n\nSi no te he podido ayudar puedes probar con alguna de estas solicitudes"

        else:
            nombres_elementos=[]

        st.write(response)
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
        guardar_lista(nombres_elementos)
        elementos=leer_lista()

#print(elementos)
if  st.session_state.messages != [] and elementos:
    #print(f"dentro{elementos}")
    # Agregar un formulario desplegable al hacer clic en el botón
    string=elementos[0]
    nombres_elementos = elementos

    # Obtener los maestroCampoRecursoId del primer elemento
    maestroCampoRecursoIds = [campo['maestroCampoRecursoId'] for elemento in datos if elemento['nombre'] == nombres_elementos[0] for campo in elemento['maestroCamposRecursos']]
    
    # Obtener los nombres relativos a los IDs del primer elemento
    nombres_relativos = [obtener_nombre_por_id(id, nombres_datos) for id in maestroCampoRecursoIds]
    print(maestroCampoRecursoIds)
    ayuda_relativos = [obtener_ayuda_por_id(id, nombres_datos) for id in maestroCampoRecursoIds]
    if 'submitted' not in st.session_state:
            st.session_state.submitted=False
    if 'submitted2' not in st.session_state:
            st.session_state.submitted2=False
    if st.button(string,on_click=reset):
        if 'valorCampos' not in st.session_state:
            st.session_state.valorCampos = {}
        st.write("Por favor, ingresa los siguientes datos:")
        form= st.form("form")
        for i,nombre in enumerate(nombres_relativos):
            if getTipo(nombre,nombres_datos)=="DateTime":
                st.session_state.valorCampos[i]=form.date_input(nombre,key=nombre, help=ayuda_relativos[i])
            else:
                st.session_state.valorCampos[i]=form.text_input(nombre,help=ayuda_relativos[i],key=nombre)    
        submit_button = form.form_submit_button(label="Enviar",on_click=submitted)
    if st.session_state.submitted == True:
        for nombre in nombres_relativos:
            if isinstance(st.session_state[nombre], datetime.date):
                fecha_str = str(st.session_state[nombre])
                fechacompleta=fecha_str+"T09:00:00.000Z"
                st.session_state[nombre]=fechacompleta
            print(f"{nombre}: {st.session_state[nombre]}")
            values.append(st.session_state[nombre])
        for i,id in enumerate(maestroCampoRecursoIds):
            campo = Campo(0, id, values[i])
            campos.append(campo)
        
        payload_obj = Payload(st.session_state.id1, campos, [], False)
        callApi(payload_obj,correo=st.session_state.correo)
        reset()

    # Obtener los maestroCampoRecursoId del primer elemento
    maestroCampoRecursoIds2 = [campo['maestroCampoRecursoId'] for elemento in datos if elemento['nombre'] == nombres_elementos[1] for campo in elemento['maestroCamposRecursos']]

    # Obtener los nombres relativos a los IDs del primer elemento
    nombres_relativos2 = [obtener_nombre_por_id(id, nombres_datos) for id in maestroCampoRecursoIds2]
    print(maestroCampoRecursoIds2)
    ayuda_relativos2 = [obtener_ayuda_por_id(id, nombres_datos) for id in maestroCampoRecursoIds2]
    #print(nombres_relativos)
    string2=elementos[1]
    if 'submitted' not in st.session_state:
            st.session_state.submitted=False
    if st.button(string2,on_click=reset):
        
        if 'valorCampos' not in st.session_state:
            st.session_state.valorCampos = {}
            
        st.write("Por favor, ingresa los siguientes datos:")
        form= st.form("form",clear_on_submit=True)
        for i, nombre in enumerate (nombres_relativos2):
                if getTipo(nombre,nombres_datos)=="DateTime":
                    st.session_state.valorCampos[i]=form.date_input(nombre,key=nombre, help=ayuda_relativos2[i])
                    
                else:
                    st.session_state.valorCampos[i]=form.text_input(nombre,help=ayuda_relativos2[i],key=nombre)

        submit_button = form.form_submit_button(label="Enviar",on_click=submitted2)
    if st.session_state.submitted2 == True:
        for nombre in nombres_relativos2:
            if isinstance(st.session_state[nombre], datetime.date):
                fecha_str = str(st.session_state[nombre])
                fechacompleta=fecha_str+"T09:00:00.000Z"
                st.session_state[nombre]=fechacompleta
            print(f"{nombre}: {st.session_state[nombre]}")
            values.append(st.session_state[nombre])
            
        for i,id in enumerate(maestroCampoRecursoIds2):
            campo = Campo(0, id, values[i])
            campos.append(campo)
        payload_obj = Payload(st.session_state.id2, campos, [], False)
        callApi(payload_obj,correo="vchumillas@megamedia.es")
        reset2()
            
         
        
