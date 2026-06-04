import os
import glob
import logging
from dotenv import load_dotenv
load_dotenv(override=True)

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("brand-compliance")


def index_docs():
    
    data_folder = "/Users/shanthan/Documents/projects/Brand_Gaurdian/complianceqapipeline/backend/data"

    logger.info(f"Loading documents from {data_folder}")
    logger.info(f"AZURE_OPENAI_ENDPOINT: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
    logger.info(f"AZURE_OPENAI_API_VERSION: {'set' if os.getenv('AZURE_OPENAI_API_VERSION') else 'not set'}")
    logger.info(f"AZURE_OPENAI_EMBEDDING_DEPLOYMENT: {os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT')}")
    logger.info(f"AZURE_SEARCH_ENDPOINT: {'set' if os.getenv('AZURE_SEARCH_ENDPOINT') else 'not set'}")
    logger.info(f"AZURE_SEARCH_INDEX_NAME: {os.getenv('AZURE_SEARCH_INDEX_NAME')}")

    required_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_KEY",
        "AZURE_SEARCH_INDEX_NAME",
    ]
    for var in required_vars:
        if not os.getenv(var):
            logger.error(f"Missing required env var: {var}")
            return

    # ✅ Bug 1 fixed: correct params for embeddings
    try:
        logger.info("Initializing Azure OpenAI Embeddings...")
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        )
        logger.info("Embeddings initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing embeddings: {e}")
        return

    # ✅ Bug 2 fixed: consistent key name
    try:
        logger.info("Initializing Azure AI Search vector store...")
        index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")
        vector_store = AzureSearch(
            azure_search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            azure_search_key=os.getenv("AZURE_SEARCH_KEY"),
            index_name=index_name,
            embedding_function=embeddings.embed_query,
            semantic_configuration_name="brand-compliance-semantic-config" 
        )
        logger.info(f"Vector store initialized for index: {index_name}")
    except Exception as e:
        logger.error(f"Failed to initialize Azure Search: {e}")
        return

    pdf_files = glob.glob(os.path.join(data_folder, "*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDF files found in {data_folder}")
        return

    logger.info(f"Found {len(pdf_files)} PDF files: {[os.path.basename(f) for f in pdf_files]}")

    all_splits = []
    for pdf_file in pdf_files:
        try:
            loader = PyPDFLoader(pdf_file)
            documents = loader.load()
            logger.info(f"Loaded {len(documents)} pages from {os.path.basename(pdf_file)}")

            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            splits = splitter.split_documents(documents)
            for split in splits:
                split.metadata["source"] = os.path.basename(pdf_file)

            all_splits.extend(splits)
            logger.info(f"Split into {len(splits)} chunks")
        except Exception as e:
            logger.error(f"Error processing {pdf_file}: {e}")

    # ✅ Bug 3 fixed: outside the loop
    if all_splits:
        logger.info(f"Indexing {len(all_splits)} total chunks into Azure Search...")
        try:
            vector_store.add_documents(documents=all_splits)
            logger.info("✅ Documents indexed successfully")
        except Exception as e:
            logger.error(f"Failed to index documents: {e}")
    else:
        logger.warning("No chunks to index.")


# ✅ Bug 4 fixed: at module level
if __name__ == "__main__":
    index_docs()