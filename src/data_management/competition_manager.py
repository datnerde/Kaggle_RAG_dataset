import datetime
import logging
from typing import Dict, List, Optional

from .base_manager import BaseManager

logger = logging.getLogger(__name__)

class CompetitionManager(BaseManager):
    """Manages competition documents"""
    def __init__(self, db):
        super().__init__(db['competitions'])
        self._create_index('competition_id')
        
    def create_or_update(self, competition_data: Dict) -> bool:
        """
        Create or update a competition record
        Args:
            competition_data: Dictionary containing competition details
        Returns:
            bool: True if successful, False otherwise
        """
        competition_id = competition_data.get('competition_id')
        if not competition_id:
            raise ValueError("Missing required field: competition_id")
            
        competition_data['last_updated'] = datetime.datetime.now()
        return self._update(
            {'competition_id': competition_id},
            competition_data,
            upsert=True
        )
        
    def get(self, competition_id: str) -> Optional[Dict]:
        """Get competition by ID"""
        return self.collection.find_one(
            {'competition_id': competition_id},
            {'_id': 0}
        )
    
    def list_all(self, projection: Optional[Dict] = None) -> List[Dict]:
        """List all competitions with optional projection"""
        projection = projection or {'_id': 0}
        return list(self.collection.find({}, projection))
    
    def exists(self, competition_id: str) -> bool:
        """Check if competition exists"""
        return self._validate_exists({'competition_id': competition_id})