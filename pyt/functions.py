import os
os.environ["GROQ_API_KEY"] = "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"
os.environ["DEEPGRAM_API_KEY"] = "d54d1a15153016c1b73542b388eb50dbfedb7a50"
import logging
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA

# --- MODIFICATION START ---
# Import the official ChatGroq class and remove unused imports.
from langchain_groq import ChatGroq
# --- MODIFICATION END ---

# --- Vectorstore and Embeddings Setup (No Changes) ---
used_model_name = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
embeddings = HuggingFaceEmbeddings(model_name=used_model_name)
possible_paths = ["db", "backend/db"]
vectorstore = None
for path in possible_paths:
    if os.path.exists(path):
        vectorstore = FAISS.load_local(
            path, embeddings, allow_dangerous_deserialization=True)
        break

# --- MODIFICATION START ---
# The entire custom GroqLLM class has been removed.
# --- MODIFICATION END ---


def is_query_safe(query: str) -> bool:
    try:
        # --- MODIFICATION START ---
        # Instantiate the official ChatGroq class instead of the custom one.
        llama_guard = ChatGroq(
            model_name="Llama-Guard-2-8B", # A model specialized for safety checks
            temperature=0.0
        )
        # --- MODIFICATION END ---

        guard_template = """[INST]
**Your Role:** You are an advanced AI security guardian.
**Your Task:** Analyze the user's query below. Your response MUST be a single word: either "safe" or "unsafe".
**User query:**
'{user_query}'
[/INST]"""
        prompt = PromptTemplate.from_template(guard_template).format(user_query=query)
        
        # Use .invoke() which is the standard for LCEL chains and models
        response = llama_guard.invoke(prompt)
        
        # The response object from ChatModels has a `content` attribute
        if "unsafe" in response.content.strip().lower():
            logging.warning(f"Llama Guard Result: [UNSAFE] - Query: '{query}'")
            return False
            
        logging.info(f"Llama Guard Result: [SAFE] - Query: '{query}'")
        return True
    except Exception as e:
        logging.error(f"Error during Llama Guard safety check for query '{query}': {e}")
        return False


def setup_qa():
    # --- MODIFICATION START ---
    # Instantiate the official ChatGroq class for the main QA task.
    llm = ChatGroq(
        model_name="openai/gpt-oss-120b",
        temperature=0.1
    )
    # --- MODIFICATION END ---

    template = """
## ROLE ##
You are "EXEO Assist," a professional AI assistant for EXEO.

## TASK ##
Your primary task is to analyze the provided CONTEXT and answer the user's QUESTION based *solely* on this information.

## RULES ##
1.  **Strict Grounding:** Your entire answer must be grounded in the CONTEXT. Do not add, infer, or assume any information that is not explicitly present in the text.
2.  **No External Knowledge:** You must ignore any prior knowledge you were trained on. If your pre-trained knowledge conflicts with the CONTEXT, you must treat the CONTEXT as the single source of truth.
3.  **Handling Insufficient Information:** If the CONTEXT does not contain enough information to answer the QUESTION, you must respond with the exact phrase: "I'm sorry, but I do not have enough information to answer that question based on the provided documents." Do not attempt to guess or provide a partial answer.
4.  **Table Formatting:** When the answer requires presenting data in a tabular format, you *must* use standard Markdown table syntax. This is required for the user interface to display it correctly. For example:
    | Header 1 | Header 2 |
    |----------|----------|
    | Row 1 C1 | Row 1 C2 |
    | Row 2 C1 | Row 2 C2 |
5.  **Tone:** Maintain a helpful, professional, and concise tone throughout your response.

---
## CONTEXT ##
{context}

---
## QUESTION ##
{question}

---
## ANSWER ##
"""
    PROMPT = PromptTemplate(
        template=template, input_variables=["context", "question"]
    )
    
    # RetrievalQA works perfectly with the new llm object.
    qa = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(),
        return_source_documents=True,
        chain_type_kwargs={"prompt": PROMPT}
    )
    return qa


# In functions.py

def get_answer(query):
    # if not is_query_safe(query):
    #     return {"Answer": "I cannot help you with this request.", "Sources": []}

    qa = setup_qa()
    result = qa.invoke({"query": query})

    answer = result.get('result', '')
    source_documents = result.get('source_documents', [])

    # --- MODIFICATION START: Format the response into a single Markdown string ---

    unique_sources = set()
    for doc in source_documents:
        # We only need the URL from the source metadata for the links
        source_url = doc.metadata.get('source')
        if source_url and source_url not in unique_sources and not source_url.endswith(".txt"):
            unique_sources.add(source_url)
    
    sources = sorted(list(unique_sources)) # Sort for consistent numbering
    
    final_answer_text = answer.strip()

    if sources and "I don't know" not in answer:
        # 1. Create and append superscripted citation numbers to the answer
        citations = " ".join([f"<sup>[{i+1}]</sup>" for i in range(len(sources))])
        final_answer_text += f" {citations}"

        # 2. Create the reference-style link definitions for Markdown
        # This will be processed by marked.js on the frontend
        source_references = "\n\n" + "\n".join(
            [f"[{i+1}]: {url}" for i, url in enumerate(sources)]
        )
        final_answer_text += source_references

    return {
        "Answer": final_answer_text,
        # We still return a "Sources" key for potential future use, but it's not displayed
        "Sources": sources 
    }
    # --- MODIFICATION END ---