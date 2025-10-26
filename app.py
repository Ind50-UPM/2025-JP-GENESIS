import streamlit as st
from langchain_community.llms import Ollama
from langchain_core.messages import HumanMessage, SystemMessage

# --- Configuración de la interfaz ---
st.set_page_config(page_title="Asistente RAG con Llama 3")
st.title("🤖 Asistente RAG con Llama 3")

# --- Conexión al modelo (Se carga una sola vez) ---
@st.cache_resource
def load_llm():
    # Asegúrate de que el servidor Ollama esté corriendo en la VM
    return Ollama(model="llama3")

llm = load_llm()

# --- Lógica de la Sesión y Chat ---

if "messages" not in st.session_state:
    # Mensaje inicial del sistema para darle un rol al LLM
    st.session_state.messages = [
        {"role": "system", "content": "Eres un asistente de datos experto de la UPM. Responde de forma concisa."},
    ]

# Muestra el historial de mensajes
for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Lógica cuando el usuario envía un mensaje
if prompt := st.chat_input("Escribe tu pregunta para Llama 3..."):
    
    # Muestra el mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # Prepara el historial para el LLM (excluyendo la clave 'role' del sistema)
    history = [
        SystemMessage(content=st.session_state.messages[0]["content"])
    ]
    for msg in st.session_state.messages[1:]:
        if msg["role"] == "user":
            history.append(HumanMessage(content=msg["content"]))
        else:
            # En un chat real, también enviarías la respuesta del asistente
            pass 

    with st.chat_message("assistant"):
        with st.spinner("Llama 3 está pensando..."):
            # Aquí invocamos el modelo con la pregunta del usuario
            response = llm.invoke(prompt) 
            st.markdown(response)
    
    # Guarda la respuesta del asistente en el historial
    st.session_state.messages.append({"role": "assistant", "content": response})

