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
        formatted_queries.append(f"User message : {query} - Sub_Intent Identified : {intent}")
        # print(formatted_queries)
    return "\n".join(formatted_queries)
