import streamlit as st
from langchain.chains import RetrievalQA
from langchain_ollama import ChatOllama
from utils import get_retriever
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.callbacks.base import BaseCallbackHandler
import uuid

class StreamlitCallbackHandler(BaseCallbackHandler):
    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.text = ""
    
    def on_llm_new_token(self, token: str, **kwargs):
        self.text += token
        self.placeholder.markdown(self.text)

def get_custom_prompt():
    return ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(
            "You are an AI chatbot that leverages a knowledge base built from uploaded documents to answer specific queries. "
            "If the user's query clearly asks for information from the documents, answer strictly using the provided context. "
            "However, if the user's message is simply a greeting or general conversation without referring to the documents, "
            "respond in a friendly and human-like manner without using the document context. "
            "For example, if the user says 'hi' or 'how are you?', reply as you would in a normal chat conversation."
        ),
        HumanMessagePromptTemplate.from_template(
            "Context:\n{context}\n\n"
            "Question: {question}\n\n"
            "Provide a precise and well-structured answer based on the context above when the query is document-related, "
            "or respond conversationally if the query is a general greeting or casual conversation."
        )
    ])


def initialize_qa_chain():
    if not st.session_state.qa_chain and st.session_state.vector_store:
        llm = ChatOllama(model="deepseek-r1:1.5b", temperature=0.3)
        retriever = get_retriever()
        st.session_state.qa_chain = RetrievalQA.from_chain_type(
            llm,
            retriever=retriever,
            chain_type="stuff",
            chain_type_kwargs={"prompt": get_custom_prompt()}
        )
    return st.session_state.qa_chain

def initialize_session_state():
    if "chat_threads" not in st.session_state:
        st.session_state.chat_threads = []  # each thread: {"id": str, "name": str, "messages": list}
    if "current_thread_id" not in st.session_state:
        st.session_state.current_thread_id = None
    if "vector_store" not in st.session_state:
        st.session_state.vector_store = None
    if "qa_chain" not in st.session_state:
        st.session_state.qa_chain = None
    if "renaming_thread_id" not in st.session_state:
        st.session_state.renaming_thread_id = None
    if "options_shown" not in st.session_state:
        st.session_state.options_shown = None

def create_new_chat_thread():
    thread_id = str(uuid.uuid4())
    new_thread = {"id": thread_id, "name": "New Chat", "messages": []}
    st.session_state.chat_threads.append(new_thread)
    st.session_state.current_thread_id = thread_id

def get_current_thread():
    current = None
    for thread in st.session_state.chat_threads:
        if thread["id"] == st.session_state.current_thread_id:
            current = thread
            break
    if current is None:
        create_new_chat_thread()
        current = st.session_state.chat_threads[-1]
    return current

def display_sidebar():
    with st.sidebar:
        st.header("Chat Threads")
        # New Chat button at the top (compact layout)
        if st.button("New Chat", key="new_chat"):
            create_new_chat_thread()
        
        # List chat threads with a burger button for options
        for thread in st.session_state.chat_threads:
            # Use columns to place thread name and burger button on the same line
            col_name, col_burger = st.columns([0.9, 0.1], gap="small")
            with col_name:
                # Clicking the thread name selects the thread
                if st.button(thread["name"], key=f"select_{thread['id']}"):
                    st.session_state.current_thread_id = thread["id"]
            with col_burger:
                # Burger button (using a Unicode character for a vertical ellipsis)
                if st.button("⋮", key=f"options_{thread['id']}"):
                    # Toggle options: if the same thread is already open, close it; otherwise open it.
                    if st.session_state.options_shown == thread["id"]:
                        st.session_state.options_shown = None
                    else:
                        st.session_state.options_shown = thread["id"]
            
            # Show options only if this thread's burger is activated
            if st.session_state.options_shown == thread["id"]:
                with st.expander("", expanded=True):
                    # If renaming is in progress, show input field; otherwise, show Rename button.
                    if st.session_state.get("renaming_thread_id") == thread["id"]:
                        new_name = st.text_input("New name:", value=thread["name"], key=f"input_{thread['id']}")
                        if st.button("Confirm Rename", key=f"confirm_{thread['id']}"):
                            thread["name"] = new_name
                            st.session_state.renaming_thread_id = None
                            st.session_state.options_shown = None
                    else:
                        if st.button("Rename", key=f"rename_{thread['id']}"):
                            st.session_state.renaming_thread_id = thread["id"]
                    # Delete button (with a confirmation, if needed, can be added later)
                    if st.button("Delete", key=f"delete_{thread['id']}"):
                        st.session_state.chat_threads = [t for t in st.session_state.chat_threads if t["id"] != thread["id"]]
                        # Reset current thread if it was deleted
                        if st.session_state.current_thread_id == thread["id"]:
                            st.session_state.current_thread_id = st.session_state.chat_threads[0]["id"] if st.session_state.chat_threads else None
                        st.session_state.options_shown = None

def chat_interface():
    st.title("PDF_CHATBOT.ai")
    st.markdown("Your personal textbook AI chatbot powered by Deepseek 1.5B")
    
    current_thread = get_current_thread()
    # Display messages for the current chat thread
    for message in current_thread["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    if prompt := st.chat_input("Ask about your documents"):
        # If this is the first message and thread name is still default, update it using first three words of the prompt
        if current_thread["name"] == "New Chat":
            words = prompt.split()
            new_name = " ".join(words[:6]) if words else "New Chat"
            current_thread["name"] = new_name

        current_thread["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            streamlit_callback = StreamlitCallbackHandler(message_placeholder)
            llm = ChatOllama(
                model="deepseek-r1:1.5b",
                temperature=0.3,
                streaming=True,
                callbacks=[streamlit_callback]
            )
            retriever = get_retriever()
            qa_chain = RetrievalQA.from_chain_type(
                llm,
                retriever=retriever,
                chain_type="stuff",
                chain_type_kwargs={"prompt": get_custom_prompt()}
            )
            with st.spinner("Fetching information..."):
                try:
                    response = qa_chain({"query": prompt})
                except Exception as e:
                    message_placeholder.markdown(f"Error: {str(e)}")
                    response = {"result": "Error occurred."}
            current_thread["messages"].append({"role": "assistant", "content": response["result"]})

def main():
    initialize_session_state()
    display_sidebar()
    chat_interface()

if __name__ == "__main__":
    main()
