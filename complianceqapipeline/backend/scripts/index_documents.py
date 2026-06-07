"""
Indexes Dodd-Frank / SEC / FINRA compliance documents into Azure AI Search.

Drop PDFs into the data/ folder:
  - SEC Rule 10b-5 guidance
  - Dodd-Frank relevant sections (Title VII, Title IX)
  - FINRA Rules 2010, 2020, 4511
  - Firm-specific restricted securities lists and prohibited phrases
  - MNPI policy documentation

Then run:
  python -m backend.scripts.index_documents            # add new docs
  python -m backend.scripts.index_documents --reindex  # wipe index and re-upload everything
"""

import os
import sys
import glob
import logging
from dotenv import load_dotenv

load_dotenv(override=True)

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SimpleField,
    SearchFieldDataType,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField,
)
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("trade-surveillance.indexer")

# Legal-aware separators: try to break on section/rule boundaries before falling
# back to paragraph breaks and whitespace.
LEGAL_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1800,
    chunk_overlap=400,
    separators=[
        "\n§",          # CFR / Dodd-Frank section symbol
        "\nSection ",   # spelled-out section headers
        "\nRule ",      # FINRA Rule 2010, 4511 etc.
        "\n\n",         # paragraph breaks
        "\n",
        " ",
    ],
)

DOC_TYPE_MAP = {
    "dodd": "dodd_frank",
    "frank": "dodd_frank",
    "sec": "sec",
    "10b": "sec",
    "finra": "finra",
    "mnpi": "mnpi",
    "restricted": "restricted_list",
}


def _infer_doc_type(filename: str) -> str:
    lower = filename.lower()
    for keyword, doc_type in DOC_TYPE_MAP.items():
        if keyword in lower:
            return doc_type
    return "compliance"


def _check_env(required_vars: list[str]) -> bool:
    missing = [v for v in required_vars if not os.getenv(v)]
    for v in missing:
        logger.error(f"Missing required environment variable: {v}")
    return len(missing) == 0


SEMANTIC_CONFIG_NAME = "dodd-frank-compliance-semantic-config"


def patch_index(endpoint: str, key: str, index_name: str) -> bool:
    """
    Add missing fields and semantic configuration to an existing index without deleting data.
    Azure AI Search allows adding fields and semantic config to a live index.

    Adds:
    - 'metadata' string field (required by LangChain for doc metadata storage)
    - 'doc_type' string field (filterable/facetable for per-regulation queries)
    - Semantic configuration 'dodd-frank-compliance-semantic-config' (required for
      semantic_hybrid_search — uses 'content' as the primary content field and
      'source' as keyword context)
    """
    required_fields = {
        "metadata": SimpleField(name="metadata", type=SearchFieldDataType.String, filterable=True),
        "doc_type": SimpleField(name="doc_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
    }
    try:
        index_client = SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(key))
        index = index_client.get_index(index_name)
        changed = False

        # Add missing fields
        existing_fields = {f.name for f in index.fields}
        to_add = [field for name, field in required_fields.items() if name not in existing_fields]
        if to_add:
            index.fields.extend(to_add)
            changed = True
            for f in to_add:
                logger.info(f"Patched index: added field '{f.name}'.")

        # Add semantic configuration if missing
        existing_semantic_names = set()
        if index.semantic_search and index.semantic_search.configurations:
            existing_semantic_names = {c.name for c in index.semantic_search.configurations}

        if SEMANTIC_CONFIG_NAME not in existing_semantic_names:
            semantic_config = SemanticConfiguration(
                name=SEMANTIC_CONFIG_NAME,
                prioritized_fields=SemanticPrioritizedFields(
                    content_fields=[SemanticField(field_name="content")],
                    keywords_fields=[SemanticField(field_name="source")],
                ),
            )
            existing_configs = (
                index.semantic_search.configurations
                if index.semantic_search and index.semantic_search.configurations
                else []
            )
            index.semantic_search = SemanticSearch(configurations=[*existing_configs, semantic_config])
            changed = True
            logger.info(f"Patched index: added semantic configuration '{SEMANTIC_CONFIG_NAME}'.")

        if not changed:
            logger.info("Index schema already has all required fields and semantic config — no patch needed.")
            return True

        index_client.create_or_update_index(index)
        logger.info("Index patch applied successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to patch index '{index_name}': {e}")
        return False


def clear_index(endpoint: str, key: str, index_name: str) -> bool:
    """Delete the Azure AI Search index entirely so it can be recreated clean."""
    try:
        index_client = SearchIndexClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key),
        )
        existing = [idx.name for idx in index_client.list_indexes()]
        if index_name not in existing:
            logger.info(f"Index '{index_name}' does not exist — nothing to clear.")
            return True
        index_client.delete_index(index_name)
        logger.info(f"Index '{index_name}' deleted successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to delete index '{index_name}': {e}")
        return False


def index_docs(reindex: bool = False):
    data_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    logger.info(f"Loading compliance documents from {data_folder}")

    required_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_KEY",
        "AZURE_SEARCH_INDEX_NAME",
    ]
    if not _check_env(required_vars):
        return

    search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    search_key = os.getenv("AZURE_SEARCH_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")

    if reindex:
        logger.info("--reindex flag set: clearing existing index before re-uploading.")
        if not clear_index(search_endpoint, search_key, index_name):
            logger.error("Aborting — could not clear index.")
            return
    else:
        # Always ensure required fields exist before uploading — safe to run on every invocation.
        if not patch_index(search_endpoint, search_key, index_name):
            logger.error("Aborting — could not patch index schema.")
            return

    try:
        logger.info("Initializing Azure OpenAI Embeddings...")
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        )
    except Exception as e:
        logger.error(f"Failed to initialize embeddings: {e}")
        return

    try:
        logger.info("Initializing Azure AI Search vector store...")
        vector_store = AzureSearch(
            azure_search_endpoint=search_endpoint,
            azure_search_key=search_key,
            index_name=index_name,
            embedding_function=embeddings.embed_query,
            semantic_configuration_name="dodd-frank-compliance-semantic-config",
        )
        logger.info(f"Vector store initialized — index: {index_name}")
    except Exception as e:
        logger.error(f"Failed to initialize Azure Search: {e}")
        return

    pdf_files = glob.glob(os.path.join(data_folder, "*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDF files found in {data_folder}")
        return

    logger.info(f"Found {len(pdf_files)} compliance documents: {[os.path.basename(f) for f in pdf_files]}")

    all_splits = []
    for pdf_file in pdf_files:
        try:
            loader = PyPDFLoader(pdf_file)
            documents = loader.load()
            logger.info(f"Loaded {len(documents)} pages from {os.path.basename(pdf_file)}")

            splits = LEGAL_SPLITTER.split_documents(documents)
            doc_type = _infer_doc_type(os.path.basename(pdf_file))
            for split in splits:
                split.metadata["source"] = os.path.basename(pdf_file)
                split.metadata["doc_type"] = doc_type
                split.metadata["char_count"] = len(split.page_content)
            all_splits.extend(splits)
            logger.info(f"  → {len(splits)} chunks (doc_type={doc_type})")
        except Exception as e:
            logger.error(f"Error processing {pdf_file}: {e}")

    if not all_splits:
        logger.warning("No document chunks to index.")
        return

    logger.info(f"Indexing {len(all_splits)} chunks into Azure AI Search...")
    try:
        vector_store.add_documents(documents=all_splits)
        logger.info("Documents indexed successfully.")
    except Exception as e:
        logger.error(f"Failed to index documents: {e}")


if __name__ == "__main__":
    reindex = "--reindex" in sys.argv
    index_docs(reindex=reindex)
