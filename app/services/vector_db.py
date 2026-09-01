"""
ChromaDB wrapper service for the AI Gateway Perimetral.

Responsibilities:
    - Initialize the persistent vector store on disk.
    - Load the initial seed attack signatures on first run.
    - Expose semantic similarity search for Layer 2.
    - Expose signature registration for the immunity feedback loop.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from app.core.config import Settings

logger = logging.getLogger(__name__)

# Path to the seed dataset, relative to the project root.
SEED_FILE_PATH = Path("./data/seed_attacks.json")

# ChromaDB collection name for confirmed attack signatures.
COLLECTION_NAME = "attack_signatures"


class VectorDBService:
    """
    Service layer for all ChromaDB interactions.

    Operates in persistent mode, storing vectors on disk so that
    learned attack signatures survive server restarts.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._embedding_model: SentenceTransformer | None = None
        self._client: chromadb.PersistentClient | None = None
        self._collection: Any = None

    def initialize(self) -> None:
        """
        Loads the embedding model and connects to the persistent ChromaDB store.
        Seeds the collection from the JSON file if it is empty.
        This method is called once during the application lifespan startup.
        """
        logger.info("Loading embedding model: %s", self._settings.embedding_model_name)
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        self._embedding_model = SentenceTransformer(
            self._settings.embedding_model_name,
            cache_folder=self._settings.hf_home,
        )

        logger.info("Connecting to ChromaDB at: %s", self._settings.vector_db_path)
        self._client = chromadb.PersistentClient(
            path=self._settings.vector_db_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        if self._collection.count() == 0:
            logger.info("Collection is empty. Loading seed attack signatures.")
            self._seed_collection()
        else:
            logger.info(
                "Collection loaded with %d existing signatures.",
                self._collection.count(),
            )

    def _seed_collection(self) -> None:
        """Loads the initial attack signatures from the seed JSON file."""
        if not SEED_FILE_PATH.exists():
            logger.warning("Seed file not found at %s. Skipping seed.", SEED_FILE_PATH)
            return

        with open(SEED_FILE_PATH, encoding="utf-8") as f:
            seed_data: list[dict] = json.load(f)

        texts = [item["text"] for item in seed_data]
        ids = [f"seed_{i}" for i in range(len(texts))]
        metadatas = [
            {
                "source": item.get("source", "seed"),
                "category": item.get("category", "unknown"),
            }
            for item in seed_data
        ]
        embeddings = self._embed(texts)

        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        logger.info("Seeded %d attack signatures into ChromaDB.", len(texts))

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Generates embedding vectors for a list of text strings."""
        if self._embedding_model is None:
            raise RuntimeError("VectorDBService has not been initialized.")
        return self._embedding_model.encode(texts, convert_to_numpy=True).tolist()

    def search_similar_attack(
        self, text: str
    ) -> tuple[bool, float, str | None]:
        """
        Checks if the given text is semantically similar to a known attack.

        Args:
            text: The user prompt to evaluate.

        Returns:
            A tuple of (is_attack, distance, matched_document).
            - is_attack: True if the closest match is within the threshold.
            - distance: The cosine distance to the closest vector (0 = identical).
            - matched_document: The closest matching document text, or None.
        """
        if self._collection is None:
            raise RuntimeError("VectorDBService has not been initialized.")

        if self._collection.count() == 0:
            return False, 1.0, None

        embedding = self._embed([text])
        results = self._collection.query(
            query_embeddings=embedding,
            n_results=1,
            include=["documents", "distances"],
        )

        distance: float = results["distances"][0][0]
        document: str = results["documents"][0][0]
        is_attack = distance <= self._settings.similarity_threshold

        return is_attack, distance, document

    def add_attack_signature(
        self, text: str, metadata: dict | None = None
    ) -> None:
        """
        Registers a newly detected attack prompt in the vector store.

        This method implements the immunity feedback loop: once an attack
        is identified by Layer 3 or Layer 5, it is vectorized and persisted
        so that Layer 2 can block identical or near-identical attempts
        in future requests without invoking the heavier AI classifier.

        Args:
            text: The attack prompt text to register.
            metadata: Optional dictionary with context such as layer, score, user_id.
        """
        if self._collection is None:
            raise RuntimeError("VectorDBService has not been initialized.")

        # Use a hash-based ID to prevent duplicate entries.
        import hashlib
        doc_id = f"learned_{hashlib.sha256(text.encode()).hexdigest()[:16]}"

        existing = self._collection.get(ids=[doc_id])
        if existing and existing.get("ids"):
            logger.debug("Signature already registered. Skipping duplicate: %s", doc_id)
            return

        embedding = self._embed([text])
        self._collection.add(
            ids=[doc_id],
            embeddings=embedding,
            documents=[text],
            metadatas=[metadata or {"source": "learned"}],
        )
        logger.info("New attack signature registered in ChromaDB: %s", doc_id)

    def get_signature_count(self) -> int:
        """Returns the total number of stored attack signatures."""
        if self._collection is None:
            return 0
        return self._collection.count()

    def reset(self) -> None:
        """
        Deletes all signatures and re-seeds from the base dataset.
        Invoked by the POST /v1/gateway/reset-vault endpoint.
        """
        if self._client is None:
            return
        self._client.delete_collection(COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._seed_collection()
        logger.info("Attack vault reset and reseeded.")
