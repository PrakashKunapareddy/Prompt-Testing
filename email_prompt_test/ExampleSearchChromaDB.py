from uuid import uuid4

import pandas as pd
from langchain.schema import embeddings
import chromadb

from EmbedingModelMapping import EMBEDDING_MODEL_MAPPING
from EmbedingParams import embeddings_params
from ModelFactory import ModelFactory

client = chromadb.HttpClient(host = 'localhost', port = 8000)
collection_name = "intent_classification_wisteria"
collection = client.get_collection(collection_name)
collection_length = collection.count()
documents = collection.get()

# for i, doc in enumerate(documents['documents'], start=1):
# print(f"Document {i}: {doc}")
# print(f"Number of documents in the collection '{collection_name}': {collection_length}")

embeddings_factory = ModelFactory(EMBEDDING_MODEL_MAPPING)
embeddings = embeddings_factory.create_model_instance(model_map_name="AzureOpenAIEmbeddings", **embeddings_params)


def fetch_similar_queries(input_query, top_k=10):
    # Embed the input query
    input_query_embedding = embeddings.embed_query(input_query)

    # Fetch similar queries from the collection
    results = collection.query(
        query_embeddings=[input_query_embedding],
        n_results=top_k
    )
    # Extract the similar queries and their intents from the results
    similar_queries = []
    for document, metadata in zip(results['documents'], results['metadatas']):
        # Ensure metadata is accessed correctly
        intents = [meta.get('intent', 'Unknown') for meta in metadata]  # Get intents for all metadata entries

        similar_queries.append({
            'query': document,
            'intents': intents  # Store all intents for the current document
        })

    return format_similar_queries(similar_queries)

def fetch_similar_queries_for_intent(input_query, main_intent, top_k=10):
    # Embed the input query
    input_query_embedding = embeddings.embed_query(input_query)
    # Fetch similar queries from the collection
    results = collection.query(
        query_embeddings=[input_query_embedding],
        n_results=top_k,
        where={"intent": main_intent}
    )

    # Extract the similar queries and their intents from the results
    similar_queries = []
    for document, metadata in zip(results['documents'], results['metadatas']):
        # Ensure metadata is accessed correctly
        sub_intent = [meta.get('sub_intent', 'Unknown') for meta in metadata]  # Get intents for all metadata entries

        similar_queries.append({
            'query': document,
            'sub_intent': sub_intent  # Store all intents for the current document
        })
    return format_similar_queries_sub_intent(similar_queries)


def format_similar_queries(similar_queries):
    formatted_queries = []
    for query, intent in zip(similar_queries[0]['query'], similar_queries[0]['intents']):
        formatted_queries.append(f"User message : {query} - Intent Identified : {intent}")
        # print(formatted_queries)
    return "\n".join(formatted_queries)

def format_similar_queries_sub_intent(similar_queries):
    formatted_queries = []
    for query, intent in zip(similar_queries[0]['query'], similar_queries[0]['sub_intent']):
        query= query.replace("\n", " ")
        formatted_queries.append(f"User message : {query} - Sub Intent Identified : {intent}")
        # print(formatted_queries)
    return "\n".join(formatted_queries)


# def handle_delete_collection(collection_name):
#     # Check if the collection exists, if not, create it
#     try:
#         client.delete_collection(name=collection_name)
#         print("Collection already exist deleting it")
#     except Exception as e:
#         print(f"Collection '{collection_name}' does not exist, creating it.")
#
#     return client.get_or_create_collection(name=collection_name)
#
# def insert_intent_classification_examples_data(file_path = "/home/saiprakesh/Downloads/nov17_examples_Intent_classification.xlsx", collection_name ="intent_classification_wisteria"):
#     # Load the Excel file
#     # file_path = os.path.join(BASE_DIR, "static/Examples for Intent Identification.xlsx")
#     print(f"File path :: {file_path}")
#     df = pd.read_excel(file_path)
#     df = df.fillna("")
#     df.columns = df.columns.str.strip()
#
#     # Extract the 'Query' and 'Intent' columns
#     queries = df['Query'].tolist()
#     intents = df['Intent'].tolist()
#     sub_intents = df['Sub Intents'].tolist()
#
#     collection = handle_delete_collection(collection_name)
#
#     # Loop through each query and intent, embed the query and add it to the collection
#     for query, intent, sub_intent in zip(queries, intents, sub_intents):
#         question_id = str(uuid4())
#         query_embedding = embeddings.embed_query(query)
#
#         # Prepare metadata with intent
#         metadata = {
#             "intent": intent,
#             "sub_intent": sub_intent,
#             "source": "intent_classification_examples"
#         }
#         # print("metadata ::", metadata)
#         # Add data to the collection
#         collection.add(
#             embeddings=[query_embedding],
#             documents=[query],
#             metadatas=[metadata],
#             ids=[question_id]
#         )
#
#     print(f"Successfully added {len(queries)} queries and intents to the collection.")
#
