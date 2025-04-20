import uuid
import datetime
import logging
from typing import Dict, Optional

from .base_manager import BaseManager
from .competition_manager import CompetitionManager

logger = logging.getLogger(__name__)

class UserProfileManager(BaseManager):
    """Manages user profile documents"""
    def __init__(self, db, competition_manager: CompetitionManager):
        super().__init__(db['user_profiles'])
        self.competition_manager = competition_manager
        self._create_index('user_id')
        
    def create(self, username: str, email: str, **kwargs) -> Optional[str]:
        """
        Create a new user profile
        Args:
            username: User's display name
            email: User's email address
            **kwargs: Additional profile fields
        Returns:
            str: The created user_id if successful, None otherwise
        """
        user_id = str(uuid.uuid4())
        profile = {
            'user_id': user_id,
            'username': username,
            'email': email,
            'created_at': datetime.datetime.now(),
            'last_login': datetime.datetime.now(),
            'current_competition_id': None,
            **kwargs
        }
        
        try:
            result = self.collection.insert_one(profile)
            return user_id if result.inserted_id else None
        except Exception as e:
            logger.info(f"Error creating user profile: {str(e)}")
            return None
    
    def get(self, user_id: str) -> Optional[Dict]:
        """Get user profile by ID"""
        return self.collection.find_one(
            {'user_id': user_id},
            {'_id': 0}
        )
    
    def update(self, user_id: str, update_data: Dict) -> bool:
        """Update user profile data"""
        if 'user_id' in update_data:
            raise ValueError("Cannot modify user_id")
        return self._update({'user_id': user_id}, update_data)
    
    def set_active_competition(self, user_id: str, competition_id: str) -> bool:
        """
        Set user's active competition
        Args:
            user_id: User ID to update
            competition_id: Competition ID to set as active
        Returns:
            bool: True if successful
        Raises:
            ValueError: If competition doesn't exist
        """
        if not self.competition_manager.exists(competition_id):
            raise ValueError(f"Competition {competition_id} not found")
            
        return self._update(
            {'user_id': user_id},
            {
                'current_competition_id': competition_id,
                'competition_joined_at': datetime.datetime.now()
            }
        )
    
    def clear_active_competition(self, user_id: str) -> bool:
        """Clear user's active competition"""
        return self._update(
            {'user_id': user_id},
            {
                'current_competition_id': None,
                'competition_joined_at': None
            }
        )