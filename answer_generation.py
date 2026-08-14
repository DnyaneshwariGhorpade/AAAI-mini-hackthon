from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_openai import ChatOpenAI
# from langchain_core.messages import SystemMessage, HumanMessage
from transformers import pipeline

persistent_directory = "db/chroma_db"
embedding_model = HuggingFaceEmbeddings(model_name = "sentence-transformers/all-MiniLM-L6-v2")

from langchain_chroma import Chroma
db = Chroma(persist_directory=persistent_directory, embedding_function=embedding_model, collection_metadata={"hnsw:space":"cosine"})

query = "What is the color of mango?"

retriever = db.as_retriever(
    search_type = "similarity_score_threshold",
    search_kwargs = {"k":2,"score_threshold":0.3}
)

relevant_docs = retriever.invoke(query)

print(f"User query: {query}")
print("context")
for i,doc in enumerate(relevant_docs,1):
    print(f"Document{i} : \n {doc.page_content}\n")

    
#CHATGPT
combined_input = f"""Based on the following documents please answer this question: {query}
Documents:
{chr(10).join([f"-{doc.page_content[:800]}"for doc in relevant_docs])} 
Please provide a clear helpful answer using only the information from these documents. If you can't find the answer in the document then just say "I don't have enough information to answer your query"
"""

# model = ChatOpenAI(model="gpt-4o")
# messages = [
#     SystemMessage(content = "You are a good assistant man"),
#     HumanMessage(content=combined_input),
# ]
# result = model.invoke(messages)

# print("\n Generated Response: ")
# print(result.content)

#LOCAL MODEL

print("\n Generating Response: ")
model = pipeline("text-generation",model = "distilgpt2")

result = model(
    combined_input,
    max_new_tokens = 50,
    do_sample = False
)
print("\nGenerated Output: ")
print(result[0]["generated_text"])