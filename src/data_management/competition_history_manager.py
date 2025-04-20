import uuid
import random
import datetime
import logging
import subprocess
import os
from typing import Dict, Optional

import pandas as pd
from .base_manager import BaseManager
from .user_profile_manager import UserProfileManager
from quality_checks import validate_submission

logger = logging.getLogger(__name__)

class CompetitionHistoryManager(BaseManager):
    """Manages competition participation history with round-based progression"""
    MAX_ROUNDS = 6  # Constant for maximum rounds
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