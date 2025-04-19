import os
import pandas as pd
import numpy as np
from typing import Tuple, Dict, Optional
import logging

# Setup logger
logger = logging.getLogger(__name__)

def check_file_size(file_path: str, max_size_mb: float = 5.0) -> Tuple[bool, str]:
    """
    Check if file is within size limit
    
    Args:
        file_path: Path to submission file
        max_size_mb: Maximum allowed size in MB
    Returns:
        Tuple[bool, str]: (passed, message)
    """
    if not os.path.exists(file_path):
        logger.error(f"File {file_path} does not exist")
        return False, f"File {file_path} does not exist"
        
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    
    if file_size_mb > max_size_mb:
        logger.error(f"File size ({file_size_mb:.2f} MB) exceeds limit of {max_size_mb} MB")
        return False, f"File size ({file_size_mb:.2f} MB) exceeds limit of {max_size_mb} MB"
        
    logger.info(f"File size check passed: {file_size_mb:.2f} MB")
    return True, f"File size check passed: {file_size_mb:.2f} MB"

def compare_with_sample_submission(submission_file: str, sample_submission_df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Compare submission file with sample submission format
    
    Args:
        submission_file: Path to user's submission file
        sample_submission_df: DataFrame of the sample submission
    Returns:
        Tuple[bool, str]: (passed, message)
    """
    try:
        # Load user submission
        user_df = pd.read_csv(submission_file)
        
        # Check column names match
        sample_columns = set(sample_submission_df.columns)
        user_columns = set(user_df.columns)
        
        if sample_columns != user_columns:
            missing = sample_columns - user_columns
            extra = user_columns - sample_columns
            message = []
            if missing:
                message.append(f"Missing columns: {', '.join(missing)}")
            if extra:
                message.append(f"Extra columns: {', '.join(extra)}")
            error_msg = "; ".join(message)
            logger.error(f"Column mismatch: {error_msg}")
            return False, error_msg
        
        # Check row count
        if len(user_df) != len(sample_submission_df):
            error_msg = f"Row count mismatch: submission has {len(user_df)} rows, but sample has {len(sample_submission_df)} rows"
            logger.error(error_msg)
            return False, error_msg
        
        # Check column data types
        for col in sample_columns:
            sample_type = sample_submission_df[col].dtype
            user_type = user_df[col].dtype
            
            # Handle numeric types comparison (allow int vs float differences)
            if np.issubdtype(sample_type, np.number) and np.issubdtype(user_type, np.number):
                continue
                
            # For other types, they should match
            if sample_type != user_type:
                error_msg = f"Column '{col}' type mismatch: submission has {user_type}, but sample has {sample_type}"
                logger.error(error_msg)
                return False, error_msg
        
        # Check for null values if sample submission has none
        for col in sample_columns:
            if not sample_submission_df[col].isnull().any() and user_df[col].isnull().any():
                error_msg = f"Column '{col}' contains null values but should not"
                logger.error(error_msg)
                return False, error_msg
        
        # If ID column is present (usually first column), check values match
        if len(sample_columns) > 0:
            id_col = list(sample_columns)[0]  # Assume first column is ID
            if sample_submission_df[id_col].equals(user_df[id_col]):
                # If submission has same IDs as sample and in same order
                logger.info("Submission format matches sample submission exactly")
                return True, "Submission format matches sample submission exactly"
            elif set(sample_submission_df[id_col]) == set(user_df[id_col]):
                # If IDs match but possibly in different order
                logger.info("Submission has correct IDs but possibly in different order")
                return True, "Submission has correct IDs but possibly in different order"
            else:
                error_msg = f"ID column '{id_col}' values don't match sample submission"
                logger.error(error_msg)
                return False, error_msg
        
        logger.info("Submission format matches sample submission")
        return True, "Submission format matches sample submission"
    except Exception as e:
        logger.error(f"Error comparing with sample submission: {str(e)}")
        return False, f"Error comparing with sample submission: {str(e)}"

def validate_submission(submission_file: str, 
                      sample_submission_file: Optional[str] = None,
                      sample_submission_df: Optional[pd.DataFrame] = None,
                      max_size_mb: float = 5.0) -> Dict:
    """
    Validate submission against sample submission format
    
    Args:
        submission_file: Path to user's submission file
        sample_submission_file: Path to sample submission file (optional)
        sample_submission_df: Sample submission as DataFrame (optional)
        max_size_mb: Maximum allowed file size in MB
    Returns:
        Dict: Validation results with status and messages
    """
    results = {
        'status': 'failed',
        'messages': [],
        'passed_checks': 0,
        'total_checks': 2  # File size and format checks
    }
    
    logger.info(f"Starting validation for submission file: {submission_file}")
    
    # File size check
    size_passed, size_message = check_file_size(submission_file, max_size_mb)
    results['messages'].append(size_message)
    if size_passed:
        results['passed_checks'] += 1
    else:
        logger.error("File size check failed")
        return {**results, 'status': 'failed'}
    
    # Format check requires sample submission
    if sample_submission_df is None and sample_submission_file:
        try:
            logger.info(f"Loading sample submission from file: {sample_submission_file}")
            sample_submission_df = pd.read_csv(sample_submission_file)
        except Exception as e:
            error_msg = f"Error loading sample submission: {str(e)}"
            logger.error(error_msg)
            results['messages'].append(error_msg)
            return {**results, 'status': 'error'}
    
    if sample_submission_df is not None:
        format_passed, format_message = compare_with_sample_submission(submission_file, sample_submission_df)
        results['messages'].append(format_message)
        if format_passed:
            results['passed_checks'] += 1
        else:
            logger.error("Format check failed")
            return {**results, 'status': 'failed'}
    else:
        error_msg = "No sample submission provided for format check"
        logger.error(error_msg)
        results['messages'].append(error_msg)
        return {**results, 'status': 'incomplete'}
    
    # All checks passed
    if results['passed_checks'] == results['total_checks']:
        results['status'] = 'success'
        logger.info("All validation checks passed successfully")
    
    return results