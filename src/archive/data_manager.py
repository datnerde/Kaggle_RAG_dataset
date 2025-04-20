import os
import json
import uuid
import datetime
import logging
from pymongo import MongoClient
import pandas as pd
from typing import Dict, List, Optional, Union
# Create competition-specific quality checks
from quality_checks import validate_submission

# Setup logger
logger = logging.getLogger(__name__)

class BaseManager:
    """Base class with common MongoDB operations"""
    def __init__(self, collection):
        self.collection = collection
        
    def _get_by_id(self, obj_id: str) -> Optional[Dict]:
        """Get document by its ID field"""
        return self.collection.find_one({'id': obj_id}, {'_id': 0})
    
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

class NotebookManager(BaseManager):
    """Manages notebook documents and file operations"""
    def __init__(self, db, competition_manager: CompetitionManager):
        super().__init__(db['notebooks'])
        self.competition_manager = competition_manager
        self._create_index([('notebook_id', 1), ('competition_id', 1)])
        
    def import_from_file(self, file_path: str, competition_id: str, metadata: Optional[Dict] = None) -> bool:
        """
        Import a Jupyter notebook from file
        Args:
            file_path: Path to .ipynb file
            competition_id: Associated competition ID
            metadata: Optional metadata dictionary
        Returns:
            bool: True if successful
        Raises:
            ValueError: If competition doesn't exist or file is invalid
        """
        if not self.competition_manager.exists(competition_id):
            raise ValueError(f"Competition {competition_id} doesn't exist")
            
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File {file_path} does not exist")
            
        if not file_path.endswith('.ipynb'):
            raise ValueError("Only Jupyter notebook (.ipynb) files are supported")

        notebook_id = os.path.splitext(os.path.basename(file_path))[0]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                notebook_content = json.load(f)
        except Exception as e:
            raise ValueError(f"Error reading notebook file: {str(e)}")

        notebook_doc = {
            'notebook_id': notebook_id,
            'competition_id': competition_id,
            'content': notebook_content,
            'last_updated': datetime.datetime.now(),
            'metadata': metadata or {}
        }
        
        return self._update(
            {'notebook_id': notebook_id, 'competition_id': competition_id},
            notebook_doc,
            upsert=True
        )
    
    def get(self, notebook_id: str, competition_id: str) -> Optional[Dict]:
        """Get notebook by ID and competition ID"""
        return self.collection.find_one(
            {'notebook_id': notebook_id, 'competition_id': competition_id},
            {'_id': 0}
        )
    
    def get_by_competition(self, competition_id: str, include_content: bool = False) -> List[Dict]:
        """Get all notebooks for a competition"""
        projection = {'_id': 0}
        if not include_content:
            projection['content'] = 0
            
        return list(self.collection.find(
            {'competition_id': competition_id},
            projection
        ))
    
    def export_to_file(self, notebook_id: str, competition_id: str, output_path: str) -> bool:
        """
        Export notebook to .ipynb file
        Args:
            notebook_id: ID of notebook to export
            competition_id: Associated competition ID
            output_path: Destination file path
        Returns:
            bool: True if successful
        """
        notebook = self.get(notebook_id, competition_id)
        if not notebook or 'content' not in notebook:
            return False
            
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(notebook['content'], f, indent=2)
            return True
        except Exception as e:
            logger.info(f"Error exporting notebook: {str(e)}")
            return False

class DatasetManager(BaseManager):
    """Manages dataset documents and CSV operations"""
    def __init__(self, db, competition_manager: CompetitionManager):
        super().__init__(db['datasets'])
        self.competition_manager = competition_manager
        self._create_index([('metadata.dataset_id', 1), ('metadata.competition_id', 1)])
        
    def import_csv(self, file_path: str, competition_id: str, dataset_type: str = 'train', 
               max_size_mb: float = 5.0) -> bool:
        """
        Import a CSV file as dataset
        Args:
            file_path: Path to CSV file
            competition_id: Associated competition ID
            dataset_type: Type of dataset (train/test/validation)
            max_size_mb: Maximum file size in MB (default: 5.0)
        Returns:
            bool: True if successful
        Raises:
            ValueError: If competition doesn't exist, file is invalid, or exceeds size limit
        """
        if not self.competition_manager.exists(competition_id):
            raise ValueError(f"Competition {competition_id} doesn't exist")
            
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File {file_path} does not exist")
            
        if not file_path.endswith('.csv'):
            raise ValueError("Only CSV files are supported")
        
        # Check file size
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        competition = self.competition_manager.get(competition_id)
        
        if file_size_mb > max_size_mb:
            max_allowed = competition.get('data_size', max_size_mb)
            if file_size_mb > max_allowed:
                raise ValueError(f"File size ({file_size_mb:.2f} MB) exceeds the maximum allowed size "
                                f"({max_allowed:.2f} MB)")
        
        dataset_id = os.path.splitext(os.path.basename(file_path))[0]
        
        try:
            df = pd.read_csv(file_path)
            records = df.to_dict('records')
        except Exception as e:
            raise ValueError(f"Error reading CSV file: {str(e)}")

        metadata = {
            'dataset_id': dataset_id,
            'competition_id': competition_id,
            'dataset_type': dataset_type,
            'original_filename': os.path.basename(file_path),
            'file_size_mb': file_size_mb,
            'row_count': len(records),
            'column_names': list(df.columns),
            'import_date': datetime.datetime.now()
        }
        
        result = self.collection._update_with_operators(
            {'metadata.dataset_id': dataset_id, 'metadata.competition_id': competition_id},
            {
                '$set': {
                    'metadata': metadata,
                    'records': records
                }
            }
        )
        
        return result.modified_count > 0 or result.upserted_id is not None
    
    def get(self, dataset_id: str, competition_id: str) -> Optional[Dict]:
        """Get dataset by ID and competition ID"""
        return self.collection.find_one(
            {'metadata.dataset_id': dataset_id, 'metadata.competition_id': competition_id},
            {'_id': 0}
        )
    
    def get_as_dataframe(self, dataset_id: str, competition_id: str) -> Optional[pd.DataFrame]:
        """Get dataset as pandas DataFrame"""
        dataset = self.get(dataset_id, competition_id)
        if not dataset or 'records' not in dataset:
            return None
        return pd.DataFrame(dataset['records'])
    
    def get_by_type(self, competition_id: str, dataset_type: str) -> Optional[Dict]:
        """Get dataset by competition ID and type"""
        return self.collection.find_one(
            {
                'metadata.competition_id': competition_id,
                'metadata.dataset_type': dataset_type
            },
            {'_id': 0}
        )
    
    def get_sample_submission(self, competition_id: str) -> Optional[pd.DataFrame]:
        """
        Get sample submission as DataFrame
        
        Args:
            competition_id: Competition ID
        Returns:
            Optional[pd.DataFrame]: Sample submission as DataFrame if found
        """
        dataset = self.get_by_type(competition_id, 'sample_submission')
        if dataset and 'records' in dataset:
            return pd.DataFrame(dataset['records'])
        return None
    
    def export_to_csv(self, dataset_id: str, competition_id: str, output_path: str) -> bool:
        """
        Export dataset to CSV file
        Args:
            dataset_id: ID of dataset to export
            competition_id: Associated competition ID
            output_path: Destination file path
        Returns:
            bool: True if successful
        """
        df = self.get_as_dataframe(dataset_id, competition_id)
        if df is None:
            return False
            
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            df.to_csv(output_path, index=False)
            return True
        except Exception as e:
            logger.info(f"Error exporting dataset: {str(e)}")
            return False
    
    # Add a method to get sample submission
    def get_sample_submission(self, competition_id: str) -> Optional[pd.DataFrame]:
        """
        Get sample submission as DataFrame
        
        Args:
            competition_id: Competition ID
        Returns:
            Optional[pd.DataFrame]: Sample submission as DataFrame if found
        """
        dataset = self.get_by_type(competition_id, 'sample_submission')
        if dataset and 'records' in dataset:
            return pd.DataFrame(dataset['records'])
        return None

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

class CompetitionHistoryManager(BaseManager):
    """Manages competition participation history"""
    def __init__(self, db, user_manager: UserProfileManager):
        super().__init__(db['competition_history'])
        self.user_manager = user_manager
        self._create_index([('user_id', 1)])
        
    def initialize_history(self, user_id: str, competition_id: str) -> bool:
        """
        Initialize competition history for a user
        Args:
            user_id: User ID
            competition_id: Competition ID
        Returns:
            bool: True if successful
        """
        return self._update(
            {'user_id': user_id},
            {
                'user_id': user_id,
                'competition_id': competition_id,
                'start_time': datetime.datetime.now(),
                'last_activity': datetime.datetime.now(),
                'current_round': 1,
                'conversation_history': [],
                'submission_history': [],
                'round_history': {},  # Track each round's submissions and scores
                'status': 'active'
            },
            upsert=True
        )
    
    def log_interaction(self, user_id: str, message: str, is_user: bool = True) -> bool:
        """
        Log user/agent interaction
        Args:
            user_id: User ID
            message: The message content
            is_user: Whether the message is from the user (True) or agent (False)
        Returns:
            bool: True if successful
        Raises:
            ValueError: If user has no active competition
        """
        user = self.user_manager.get(user_id)
        if not user or not user.get('current_competition_id'):
            raise ValueError("User has no active competition")
            
        entry = {
            'timestamp': datetime.datetime.now(),
            'is_user': is_user,
            'content': message
        }
        
        return self._update_with_operators(
            {'user_id': user_id},
            {
                '$push': {'conversation_history': entry},
                '$set': {'last_activity': datetime.datetime.now()}
            }
        )
    
    def log_submission(self, user_id: str, submission_data: Dict) -> bool:
        """
        Log competition submission and handle round progression
        Args:
            user_id: User ID
            submission_data: Dictionary containing submission details
        Returns:
            bool: True if successful
        """
        submission_id = str(uuid.uuid4())
        submission = {
            'submission_id': submission_id,
            'timestamp': datetime.datetime.now(),
            **submission_data
        }
        
        # Get current history to determine round
        history = self.get_history(user_id)
        if not history:
            logger.error(f"No competition history found for user {user_id}")
            return False
        
        current_round = history.get('current_round', 1)
        
        # Update submission history and round tracking
        update_ops = {
            '$push': {'submission_history': submission},
            '$set': {'last_activity': datetime.datetime.now()}
        }
        
        # Initialize round history if needed
        if f'round_{current_round}' not in history.get('round_history', {}):
            update_ops['$set'][f'round_history.round_{current_round}'] = {
                'submissions': [],
                'best_score': None,
                'completed': False
            }
        
        # Add submission to current round
        update_ops['$push'][f'round_history.round_{current_round}.submissions'] = submission
        
        # Update best score if this submission is better
        if 'score' in submission_data:
            current_best = history.get('round_history', {}).get(f'round_{current_round}', {}).get('best_score')
            if current_best is None or submission_data['score'] > current_best:
                update_ops['$set'][f'round_history.round_{current_round}.best_score'] = submission_data['score']
        
        result = self._update_with_operators({'user_id': user_id}, update_ops)
        
        # Check if round is completed (successful submission)
        if submission_data.get('status') == 'success':
            return self._complete_round(user_id, current_round)
        
        return result.modified_count > 0
    
    def advance_round(self, user_id: str) -> bool:
        """Advance to next competition round"""
        return self._update_with_operators(
            {'user_id': user_id},
            {
                '$inc': {'current_round': 1},
                '$set': {'round_start_time': datetime.datetime.now()}
            }
        )
    
    def complete_competition(self, user_id: str, final_score: Optional[float] = None, notes: Optional[str] = None) -> bool:
        """Mark competition as completed"""
        return self._update_with_operators(
            {'user_id': user_id},
            {
                '$set': {
                    'end_time': datetime.datetime.now(),
                    'final_score': final_score,
                    'completion_notes': notes,
                    'status': 'completed'
                }
            }
        )
    
    def get_history(self, user_id: str) -> Optional[Dict]:
        """Get full competition history for user"""
        return self.collection.find_one(
            {'user_id': user_id},
            {'_id': 0}
        )
    def get_current_round(self, user_id: str) -> int:
        """Get user's current round number"""
        history = self.get_history(user_id)
        return history.get('current_round', 1) if history else 1
    
    def get_remaining_rounds(self, user_id: str) -> int:
        """Get number of rounds remaining"""
        history = self.get_history(user_id)
        if not history:
            return self.MAX_ROUNDS
        return self.MAX_ROUNDS - history.get('completed_rounds', 0)
    def _complete_round(self, user_id: str, round_number: int) -> bool:
        """
        Mark a round as completed and advance to next round if needed
        Args:
            user_id: User ID
            round_number: Round number being completed
        Returns:
            bool: True if successful
        """
        update_ops = {
            '$set': {
                f'round_history.round_{round_number}.completed': True,
                'last_activity': datetime.datetime.now(),
                'completed_rounds': round_number
            }
        }
        
        # If not the final round, advance to next round
        if round_number < self.MAX_ROUNDS:
            update_ops['$set']['current_round'] = round_number + 1
            update_ops['$set'][f'round_history.round_{round_number + 1}'] = {
                'submissions': [],
                'best_score': None,
                'completed': False
            }
        else:
            # Final round completed - mark competition as complete
            update_ops['$set']['status'] = 'completed'
            update_ops['$set']['end_time'] = datetime.datetime.now()
        
        result = self._update_with_operators({'user_id': user_id}, update_ops)
        
        if round_number == self.MAX_ROUNDS:
            logger.info(f"User {user_id} has completed all {self.MAX_ROUNDS} rounds")
            # Add to leaderboard
            self._add_to_leaderboard(user_id)
        
        return result.modified_count > 0
    def _add_to_leaderboard(self, user_id: str) -> bool:
        """
        Add user's final results to leaderboard collection
        Args:
            user_id: User ID
        Returns:
            bool: True if successful
        """
        history = self.get_history(user_id)
        if not history:
            return False
        
        user = self.user_manager.get(user_id)
        if not user:
            return False
        
        # Calculate final score (average of best round scores)
        round_scores = []
        for i in range(1, self.MAX_ROUNDS + 1):
            round_key = f'round_{i}'
            if round_key in history.get('round_history', {}):
                best_score = history['round_history'][round_key].get('best_score')
                if best_score is not None:
                    round_scores.append(best_score)
        
        final_score = sum(round_scores) / len(round_scores) if round_scores else 0
        
        leaderboard_entry = {
            'user_id': user_id,
            'username': user.get('username'),
            'competition_id': history['competition_id'],
            'final_score': final_score,
            'completion_date': datetime.datetime.now(),
            'round_scores': round_scores,
            'submission_count': len(history.get('submission_history', []))
        }
        
        # Insert into leaderboard collection
        leaderboard_collection = self.collection.database['leaderboard']
        try:
            result = leaderboard_collection.insert_one(leaderboard_entry)
            logger.info(f"Added user {user_id} to leaderboard with score {final_score}")
            return result.inserted_id is not None
        except Exception as e:
            logger.error(f"Error adding to leaderboard: {str(e)}")
            return False
    def get_round_history(self, user_id: str, round_number: int) -> Optional[Dict]:
        """Get detailed history for a specific round"""
        history = self.get_history(user_id)
        if not history:
            return None
        return history.get('round_history', {}).get(f'round_{round_number}')

    def get_all_rounds_status(self, user_id: str) -> Dict:
        """Get completion status for all rounds"""
        history = self.get_history(user_id)
        if not history:
            return {}
        
        status = {}
        for i in range(1, self.MAX_ROUNDS + 1):
            round_key = f'round_{i}'
            round_data = history.get('round_history', {}).get(round_key, {})
            status[round_key] = {
                'completed': round_data.get('completed', False),
                'best_score': round_data.get('best_score'),
                'submission_count': len(round_data.get('submissions', []))
            }
        
        return status

    
    # Update the validate_and_submit method
    def validate_and_submit(self, user_id: str, submission_file: str, message: str = "", 
                       sample_submission_df: Optional[pd.DataFrame] = None,
                       max_size_mb: float = 5.0) -> Dict:
        """
        Validate submission against sample and submit to Kaggle API if valid
        Handles round-based progression with up to 6 rounds
        
        Args:
            user_id: User ID
            submission_file: Path to submission file
            message: Optional submission message
            sample_submission_df: Sample submission DataFrame for validation
            max_size_mb: Maximum allowed file size in MB
            
        Returns:
            Dict: Result with status, message, and submission_id if successful
        """
        user = self.user_manager.get(user_id)
        if not user or not user.get('current_competition_id'):
            logger.error(f"User {user_id} has no active competition")
            return {
                'status': 'error',
                'message': "User has no active competition"
            }
        
        competition_id = user.get('current_competition_id')
        logger.info(f"Processing submission for user {user_id} in competition {competition_id}, round {self.get_current_round(user_id)}")
        
        # Validate the submission
        validation = validate_submission(
            submission_file, 
            sample_submission_df=sample_submission_df,
            max_size_mb=max_size_mb
        )
        
        # Prepare base submission data
        submission_data = {
            'file': os.path.basename(submission_file),
            'message': message,
            'validation': validation,
            'timestamp': datetime.datetime.now(),
            'status': 'success' if validation['status'] == 'success' else 'failed'
        }
        
        # If validation failed, just log the submission and return
        if validation['status'] != 'success':
            logger.error(f"Validation failed for {submission_file}: {validation['messages']}")
            self.log_submission(user_id, submission_data)
            return {
                'status': 'failed',
                'message': "Validation failed: " + "; ".join(validation['messages']),
                'validation': validation,
                'current_round': self.get_current_round(user_id),
                'remaining_rounds': self.get_remaining_rounds(user_id)
            }
        
        # All checks passed, submit to Kaggle
        try:
            logger.info(f"Submitting file {submission_file} to Kaggle API")
            import subprocess
            cmd = [
                'kaggle', 'competitions', 'submit',
                '-c', competition_id,
                '-f', submission_file,
                '-m', message or "Submission via platform"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if result.returncode == 0:
                # Simulate getting a score from Kaggle (in real implementation, you'd get this from API response)
                simulated_score = round(random.uniform(0.7, 0.95), 4)  # Replace with actual score retrieval
                
                # Update submission data with success details
                submission_data.update({
                    'kaggle_response': result.stdout,
                    'score': simulated_score,
                    'status': 'success'
                })
                
                # Log the successful submission (this will handle round progression)
                self.log_submission(user_id, submission_data)
                
                # Get updated round info
                current_round = self.get_current_round(user_id)
                remaining_rounds = self.get_remaining_rounds(user_id)
                
                response = {
                    'status': 'success',
                    'message': 'Submission successful',
                    'score': simulated_score,
                    'current_round': current_round,
                    'remaining_rounds': remaining_rounds,
                    'kaggle_response': result.stdout,
                    'validation': validation
                }
                
                if remaining_rounds == 0:
                    response['message'] = 'Congratulations! You completed all rounds!'
                    # Final score will be available in leaderboard
                    
                logger.info(f"Successfully submitted to Kaggle. Score: {simulated_score}, Round: {current_round}")
                return response
            else:
                submission_data.update({
                    'kaggle_response': result.stderr,
                    'status': 'failed'
                })
                self.log_submission(user_id, submission_data)
                
                logger.error(f"Kaggle API returned error: {result.stderr}")
                return {
                    'status': 'failed',
                    'message': f"Kaggle API error: {result.stderr}",
                    'current_round': self.get_current_round(user_id),
                    'remaining_rounds': self.get_remaining_rounds(user_id),
                    'validation': validation
                }
        
        except Exception as e:
            submission_data.update({
                'error': str(e),
                'status': 'error'
            })
            self.log_submission(user_id, submission_data)
            
            logger.error(f"Error submitting to Kaggle: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': f"Error submitting to Kaggle: {str(e)}",
                'current_round': self.get_current_round(user_id),
                'remaining_rounds': self.get_remaining_rounds(user_id),
                'validation': validation
            }
    

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

# Example Usage
if __name__ == "__main__":
    # Configure logger for the main script
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    with DataManager() as dm:
        # Create a competition
        dm.competitions.create_or_update({
            'competition_id': 'titanic',
            'title': 'Titanic Survival Prediction',
            'description': 'Predict survival on the Titanic',
            'evaluation': 'accuracy',
            'tags': ['classification', 'beginner']
        })
        
        # Import datasets
        dm.datasets.import_csv('data/train.csv', 'titanic', 'train')
        dm.datasets.import_csv('data/test.csv', 'titanic', 'test')
        
        # Create a user
        user_id = dm.users.create(
            username='data_scientist',
            email='ds@example.com',
            experience_level='intermediate'
        )
        
        # Set active competition
        dm.users.set_active_competition(user_id, 'titanic')
        dm.history.initialize_history(user_id, 'titanic')
        
        # Log some interactions
        dm.history.log_interaction(user_id, "Starting Titanic analysis", is_user=True)
        dm.history.log_interaction(user_id, "Here's some initial guidance", is_user=False)
        
        # Prepare and validate submission
        submission_result = dm.prepare_submission(
            user_id, 
            'submissions/titanic_predictions.csv',
            'Random forest model with feature engineering'
        )
        
        logger.info(f"Submission result: {submission_result['status']}")
        logger.info(f"Message: {submission_result['message']}")
        
        if submission_result['status'] == 'success':
            logger.info(f"Submission ID: {submission_result['submission_id']}")
            logger.info("Kaggle response:")
            logger.info(submission_result['kaggle_response'])
        else:
            logger.info("Submission failed validation or Kaggle API submission")
            for msg in submission_result.get('validation', {}).get('messages', []):
                logger.info(f"- {msg}")
                
        # Complete the competition
        dm.history.complete_competition(user_id, final_score=0.92, notes="Finished with good results")
        dm.users.clear_active_competition(user_id)
        
        # Retrieve data
        competition = dm.competitions.get('titanic')
        user_history = dm.history.get_history(user_id)
        datasets = dm.datasets.get_by_type('titanic', 'train')
        
        logger.info(f"Competition: {competition['title']}")
        logger.info(f"User completed with score: {user_history['final_score']}")