import os
import io
import glob
from utils import process_documents  # Ensure process_documents is defined in utils.py

def process_pdf_directory(pdf_dir=r"C:\Users\20368750\OneDrive - Larsen & Toubro\Documents\Digital Initiative\DeepLab\pdf_chat_deepseek\PDF_Knowledge base"):
    pdf_files = glob.glob(os.path.join(pdf_dir, "*.pdf"))
    if not pdf_files:
        print("No PDF files found in the designated directory.")
        return
    file_objects = []
    for pdf_file in pdf_files:
        with open(pdf_file, "rb") as f:
            data = f.read()
        # Create a BytesIO object and set its name attribute
        bio = io.BytesIO(data)
        bio.name = os.path.basename(pdf_file)
        file_objects.append(bio)
    # Process the PDFs and update the vector database (Chroma DB)
    vector_store = process_documents(file_objects)
    print("Knowledge base has been updated with the PDFs from the directory.")
    return vector_store

if __name__ == "__main__":
    process_pdf_directory()
