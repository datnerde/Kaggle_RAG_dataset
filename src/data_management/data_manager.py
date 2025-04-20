from pymongo import MongoClient
from .competition_manager import CompetitionManager
from .user_profile_manager import UserProfileManager
from .notebook_manager import NotebookManager
from .dataset_manager import DatasetManager
from .competition_history_manager import CompetitionHistoryManager

class DataManager:
    """Main facade class that composes all managers"""
    def __init__(self, connection_string: str = 'mongodb://localhost:27017/', db_name: str = 'kaggle_platform'):
        """
        Initialize the data management system
        Args:
            connection_string: MongoDB connection string
            db_name: Database name
        """
        self.client = MongoClient(connection_string)
        self.db = self.client[db_name]
        
        # Initialize managers with proper dependencies
        self.competitions = CompetitionManager(self.db)
        self.users = UserProfileManager(self.db, self.competitions)
        self.notebooks = NotebookManager(self.db, self.competitions)
        self.datasets = DatasetManager(self.db, self.competitions)
        self.history = CompetitionHistoryManager(self.db, self.users)
        
    def close(self):
        """Close MongoDB connection"""
        self.client.close()
    
    def prepare_submission(self, user_id: str, submission_file: str, message: str = "") -> Dict:
        """
        Validate and submit a competition entry
        
        Args:
            user_id: User ID
            submission_file: Path to submission file
            message: Optional submission message
            
        Returns:
            Dict: Result with validation status and messages
        """
        # Get user's active competition
        user = self.users.get(user_id)
        if not user or not user.get('current_competition_id'):
            return {'status': 'error', 'message': 'No active competition found for user'}
            
        competition_id = user.get('current_competition_id')
        competition = self.competitions.get(competition_id)
        
        if not competition:
            return {'status': 'error', 'message': f'Competition {competition_id} not found'}
            
        # Get sample submission for this competition
        sample_submission_df = self.datasets.get_sample_submission(competition_id)
        if sample_submission_df is None:
            return {
                'status': 'error', 
                'message': f'No sample submission found for competition {competition_id}'
            }
        
        # Get max file size from competition settings or use default
        max_size_mb = competition.get('data_size', 5.0)
        
        # Run validation and submission
        return self.history.validate_and_submit(
            user_id, 
            submission_file, 
            message, 
            sample_submission_df=sample_submission_df,
            max_size_mb=max_size_mb
        )
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()