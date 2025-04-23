import datetime
import logging
from typing import Dict, List, Optional

from .base_manager import BaseManager

logger = logging.getLogger(__name__)

class CompetitionManager(BaseManager):
    """Manages competition documents"""
    def __init__(self, db):
        super().__init__(db['domains'])
        # self._create_index('_id')
        
    def create_or_update(self, competition_data: Dict) -> bool:
        """
        Create or update a competition record
        Args:
            competition_data: Dictionary containing competition details
        Returns:
            bool: True if successful, False otherwise
        """
        competition_id = competition_data.get('name')
        if not competition_id:
            raise ValueError("Missing required field: name")
            
        competition_data['last_updated'] = datetime.datetime.now()
        return self._update(
            {'name': competition_id},
            competition_data,
            upsert=True
        )
        
    def get(self, competition_name: str) -> Optional[Dict]:
        """Get competition by ID"""
        return self.collection.find_one(
            {'name': competition_name}
        )
    
    def list_all(self, projection: Optional[Dict] = None) -> List[Dict]:
        """List all competitions with optional projection"""
        projection = projection or {'_id': 0}
        return list(self.collection.find({}, projection))
    
    def exists(self, competition_id: str) -> bool:
        """Check if competition exists"""
        return self._validate_exists({'name': competition_id})