import logging
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)

class BaseManager:
    """Base class with common MongoDB operations"""
    def __init__(self, collection):
        self.collection = collection
        
    def _get_by_id(self, obj_id: str) -> Optional[Dict]:
        """Get document by its ID field"""
        return self.collection.find_one({'_id': obj_id}, {'_id': 0})
    
    def _update(self, query: Dict, update_data: Dict, upsert: bool = False) -> bool:
        """Generic update operation"""
        result = self.collection.update_one(
            query,
            {'$set': update_data},
            upsert=upsert
        )
        return result.modified_count > 0 or (upsert and result.upserted_id is not None)
    
    def _update_with_operators(self, query: Dict, update_ops: Dict, upsert: bool = False) -> bool:
        """Generic update operation with MongoDB operators"""
        result = self.collection.update_one(
            query,
            update_ops,  # Directly pass operators like {'$push': ...}
            upsert=upsert
        )
        return result.modified_count > 0 or (upsert and result.upserted_id is not None)
    
    def _create_index(self, index_spec: Union[str, List], unique: bool = True) -> str:
        """Create index on collection"""
        return self.collection.create_index(index_spec, unique=unique)
    
    def _validate_exists(self, query: Dict) -> bool:
        """Check if document exists"""
        return self.collection.count_documents(query) > 0