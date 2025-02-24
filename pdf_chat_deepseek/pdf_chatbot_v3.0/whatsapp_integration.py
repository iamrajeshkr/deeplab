from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
import uuid

# Import your existing chatbot functions and modules
from langchain.chains import RetrievalQA
from langchain_ollama import ChatOllama
from utils import get_retriever
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate

app = Flask(__name__)

# Global QA chain – assumed to be reused across requests.
global_qa_chain = None

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
    global global_qa_chain
    if global_qa_chain is None:
        llm = ChatOllama(model="deepseek-r1:1.5b", temperature=0.3)
        retriever = get_retriever()  # Assumes vector store is already built and saved in ./chroma_db
        global_qa_chain = RetrievalQA.from_chain_type(
            llm,
            retriever=retriever,
            chain_type="stuff",
            chain_type_kwargs={"prompt": get_custom_prompt()}
        )
    return global_qa_chain

# Dictionary to maintain sessions per sender phone number.
# Each session is a dict: {"id": str, "name": str, "messages": list}
sessions = {}

def process_user_message(sender, message_text):
    """
    Processes an incoming message from a given sender.
    If this is a new session, create one with the default name "New Chat".
    Auto-renames the thread using the first three words of the first message.
    Then, passes the message to the QA chain and returns the assistant's response.
    """
    # Create session if needed.
    if sender not in sessions:
        sessions[sender] = {"id": str(uuid.uuid4()), "name": "New Chat", "messages": []}
    
    session = sessions[sender]
    
    # Auto-update the thread name if it is still the default.
    if session["name"] == "New Chat":
        words = message_text.split()
        new_name = " ".join(words[:3]) if words else "New Chat"
        session["name"] = new_name
    
    # Append the user's message to the session history.
    session["messages"].append({"role": "user", "content": message_text})
    
    # Process the message using the QA chain.
    qa_chain = initialize_qa_chain()
    try:
        response = qa_chain({"query": message_text})
        response_text = response.get("result", "I'm sorry, I couldn't generate a response.")
    except Exception as e:
        response_text = f"Error processing your request: {str(e)}"
    
    # Append the assistant's response to the session history.
    session["messages"].append({"role": "assistant", "content": response_text})
    
    return response_text

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    # Extract the incoming message details from Twilio's POST request.
    incoming_msg = request.values.get('Body', '').strip()
    sender = request.values.get('From', '').strip()
    
    # Process the incoming message.
    response_text = process_user_message(sender, incoming_msg)
    
    # Create a TwiML response to send back to WhatsApp.
    resp = MessagingResponse()
    resp.message(response_text)
    
    return Response(str(resp), mimetype="application/xml")

if __name__ == "__main__":
    app.run(debug=True)
