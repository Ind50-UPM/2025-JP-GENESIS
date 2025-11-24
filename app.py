# Código provisional, no es ejecutado por el backend

import streamlit as st
from langchain_community.llms import Ollama
from langchain_core.messages import HumanMessage, SystemMessage

# --- Configuración de la interfaz ---
st.set_page_config(page_title="Asistente RAG con Llama 3")
st.title("🤖 Asistente RAG con Llama 3")

# --- Conexión al modelo ---
@st.cache_resource
def load_llm():
    # Verificación de Ollama en la VM
    return Ollama(model="llama3")

llm = load_llm()

# --- Chatbot ---

if "messages" not in st.session_state:
    # Asignación de rol al LLM
    st.session_state.messages = [
        {"role": "system", "content": "Eres un asistente de datos experto de la UPM. Responde de forma concisa."},
    ]

# Historial de mensajes
for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Interacción con el usuario
if prompt := st.chat_input("Escribe tu pregunta para Llama 3..."):
    
    # Mensaje de usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # Historial del LLM
    history = [
        SystemMessage(content=st.session_state.messages[0]["content"])
    ]
    for msg in st.session_state.messages[1:]:
        if msg["role"] == "user":
            history.append(HumanMessage(content=msg["content"]))
        else:
            # Envío de respuesta del asistente
            pass 

    with st.chat_message("assistant"):
        with st.spinner("Llama 3 está pensando..."):
            # Invocar al modelo luego del prompt
            response = llm.invoke(prompt) 
            st.markdown(response)
    
    # Guardar respuestas del historial
    st.session_state.messages.append({"role": "assistant", "content": response})

