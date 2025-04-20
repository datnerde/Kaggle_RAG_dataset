import os
import datetime
import logging
from typing import Dict, Optional

import pandas as pd
from .base_manager import BaseManager
from .competition_manager import CompetitionManager

logger = logging.getLogger(__name__)

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