"""
Unified Storage Service
Handles both local filesystem and Google Cloud Storage
"""
from google.cloud import storage
from typing import Optional
import os
from pathlib import Path
from datetime import timedelta


class StorageService:
    """Unified storage service for local and cloud storage"""
    
    def __init__(self):
        self.use_cloud = os.getenv("USE_CLOUD_STORAGE", "false").lower() == "true"
        
        if self.use_cloud:
            self.client = storage.Client()
            self.bucket_images_name = os.getenv("GCS_BUCKET_IMAGES")
            self.bucket_uploads_name = os.getenv("GCS_BUCKET_UPLOADS")
            self.bucket_exports_name = os.getenv("GCS_BUCKET_EXPORTS")
            
            self.bucket_images = self.client.bucket(self.bucket_images_name) if self.bucket_images_name else None
            self.bucket_uploads = self.client.bucket(self.bucket_uploads_name) if self.bucket_uploads_name else None
            self.bucket_exports = self.client.bucket(self.bucket_exports_name) if self.bucket_exports_name else None
        else:
            # Local development
            self.local_images = Path("generated_images")
            self.local_images.mkdir(exist_ok=True)
            
            self.local_uploads = Path("uploads")
            self.local_uploads.mkdir(exist_ok=True)
            
            self.local_exports = Path("/tmp/anki_output") if os.path.exists("/tmp") else Path("anki_output")
            self.local_exports.mkdir(exist_ok=True)
    
    def save_generated_image(self, image_data: bytes, filename: str) -> str:
        """
        Save AI-generated course/chapter image
        Returns: URL to access the image
        """
        if self.use_cloud and self.bucket_images:
            blob = self.bucket_images.blob(filename)
            blob.upload_from_string(image_data, content_type='image/png')
            blob.make_public()
            return blob.public_url
        else:
            path = self.local_images / filename
            path.write_bytes(image_data)
            return f"/generated_images/{filename}"
    
    def save_anki_export(self, file_path: str, user_id: str, course_id: str) -> str:
        """
        Save Anki deck export
        Returns: Download URL (signed URL for cloud, local path for development)
        """
        filename = f"{user_id}/{course_id}/deck.apkg"
        
        if self.use_cloud and self.bucket_exports:
            blob = self.bucket_exports.blob(filename)
            blob.upload_from_filename(file_path)
            
            # Generate signed URL (valid for 1 hour)
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(hours=1),
                method="GET"
            )
            return url
        else:
            dest_path = self.local_exports / user_id / course_id
            dest_path.mkdir(parents=True, exist_ok=True)
            dest_file = dest_path / "deck.apkg"
            
            # Copy file
            import shutil
            shutil.copy(file_path, dest_file)
            
            return f"/output/{filename}"
    
    def save_user_upload(self, file_data: bytes, filename: str, user_id: str, content_type: str = "application/octet-stream") -> str:
        """
        Save user uploaded document
        Returns: Storage path (gs:// URL for cloud, local path for development)
        """
        path = f"{user_id}/{filename}"
        
        if self.use_cloud and self.bucket_uploads:
            blob = self.bucket_uploads.blob(path)
            blob.upload_from_string(file_data, content_type=content_type)
            return f"gs://{self.bucket_uploads_name}/{path}"
        else:
            local_path = self.local_uploads / user_id
            local_path.mkdir(parents=True, exist_ok=True)
            file_path = local_path / filename
            file_path.write_bytes(file_data)
            return str(file_path)
    
    def get_file_content(self, path: str) -> bytes:
        """
        Read file content from storage
        Supports both gs:// URLs and local paths
        """
        if path.startswith("gs://"):
            # Parse gs:// URL
            parts = path[5:].split("/", 1)
            bucket_name = parts[0]
            blob_path = parts[1]
            
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            return blob.download_as_bytes()
        else:
            return Path(path).read_bytes()
    
    def delete_file(self, path: str):
        """Delete a file from storage"""
        if path.startswith("gs://"):
            parts = path[5:].split("/", 1)
            bucket_name = parts[0]
            blob_path = parts[1]
            
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            blob.delete()
        else:
            Path(path).unlink(missing_ok=True)
    
    def list_user_files(self, user_id: str) -> list:
        """List all files for a user"""
        if self.use_cloud and self.bucket_uploads:
            blobs = self.bucket_uploads.list_blobs(prefix=f"{user_id}/")
            return [blob.name for blob in blobs]
        else:
            user_path = self.local_uploads / user_id
            if user_path.exists():
                return [str(f.relative_to(user_path)) for f in user_path.rglob("*") if f.is_file()]
            return []
    
    def get_image_url(self, filename: str) -> str:
        """Get URL for a generated image"""
        if self.use_cloud and self.bucket_images:
            blob = self.bucket_images.blob(filename)
            return blob.public_url
        else:
            return f"/generated_images/{filename}"
