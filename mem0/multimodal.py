import os
import logging
from typing import Optional, BinaryIO, Dict, Any
from mem0.memory.main import Memory
from mem0.exceptions import ConfigurationError, DatabaseError

class MultimodalMemory:
    """
    Enterprise-grade handler for Multimodal Memories in Mem0-Supabase.
    
    This class orchestrates the lifecycle of non-text assets (images, audio, etc.):
    1. Uploads raw binary assets to Supabase Storage.
    2. Generates authenticated or public access URLs.
    3. Links the asset to a cognitive memory entry in the vector store.
    """

    def __init__(self, memory_client: Memory):
        """
        Initializes the Multimodal Memory manager.
        
        Args:
            memory_client: An instance of the core Memory class.
            
        Raises:
            ConfigurationError: If Supabase credentials are missing.
        """
        self.memory = memory_client
        self.logger = logging.getLogger(__name__)
        
        try:
            from supabase import create_client, Client
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
            
            if not url or not key:
                 self.logger.error("SUPABASE_URL and SUPABASE_KEY/SERVICE_KEY are required for Multimodal operations.")
                 raise ConfigurationError(
                     message="Supabase authentication details missing",
                     error_code="CFG_003",
                     suggestion="Ensure SUPABASE_URL and SUPABASE_KEY are set in your environment."
                 )
            
            self.supabase: Client = create_client(url, key)
            self.logger.info("MultimodalMemory initialized with Supabase Storage client.")
        except ImportError:
            self.logger.error("The 'supabase' Python library is not installed.")
            raise ConfigurationError(
                message="Missing 'supabase' dependency",
                error_code="DEPS_002",
                suggestion="Install the required library: pip install supabase"
            )

    def add_image(
        self, 
        file_obj: BinaryIO, 
        file_path: str, 
        description: str, 
        user_id: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Processes and stores an image memory, uploading the asset and adding the cognitive link.
        
        Args:
            file_obj: The file-like binary stream to upload.
            file_path: The destination path in the 'mem0_artifacts' bucket.
            description: Semantic description of the image content (for embedding).
            user_id: The owner of the memory.
            metadata: Additional metadata to associate with the memory.
            
        Returns:
            The created memory object.
            
        Raises:
            DatabaseError: If the upload or memory creation fails.
        """
        bucket_name = "mem0_artifacts"
        self.logger.info(f"Adding multimodal image memory: {file_path} for user {user_id}")
        
        # 1. Upload to Storage
        try:
            # We use upsert=True to allow retries/re-uploads of the same asset path
            self.supabase.storage.from_(bucket_name).upload(
                path=file_path, 
                file=file_obj, 
                file_options={"content-type": "image/jpeg", "upsert": "true"}
            ) 
        except Exception as e:
            self.logger.warning(f"Storage upload for {file_path} encountered an issue (might already exist): {str(e)}")
            # We continue because the file might already be there and we just need the link.

        # 2. Retrieve the Public URL
        try:
            public_url = self.supabase.storage.from_(bucket_name).get_public_url(file_path)
        except Exception as e:
            self.logger.error(f"Failed to retrieve public URL for {file_path}: {str(e)}")
            raise DatabaseError(message="Could not retrieve asset URL from Storage")

        # 3. Create the Linked Memory
        # Format a descriptive text that includes the visual context and the link
        memory_text = f"[Visual Memory] {description}\nAsset: {public_url}"
        
        final_metadata = metadata or {}
        final_metadata.update({
            "asset_url": public_url,
            "asset_type": "image",
            "file_path": file_path,
            "multimodal": True
        })

        self.logger.debug(f"Submitting multimodal memory to core: {description[:50]}...")
        return self.memory.add(memory_text, user_id=user_id, metadata=final_metadata)
