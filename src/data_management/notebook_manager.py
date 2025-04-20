import os
import json
import datetime
import logging
from typing import Dict, List, Optional

from .base_manager import BaseManager
from .competition_manager import CompetitionManager

logger = logging.getLogger(__name__)

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