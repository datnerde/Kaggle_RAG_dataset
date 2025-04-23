import os
import json
import datetime
import logging
import numpy as np
from typing import Dict, List, Optional, Any, Union
from .base_manager import BaseManager
from .competition_manager import CompetitionManager

logger = logging.getLogger(__name__)

class NotebookManager(BaseManager):
    """Manages Jupyter notebooks with advanced querying and scoring capabilities"""

    SCORE_CONFIGS = {
        'quality': {
            'weights': {'score': 0.25, 'votes': 0.5, 'comments': 0.25},
            'requires_normalization': True,
            'description': 'Overall quality score'
        }
    }

    def __init__(self, db, competition_manager: CompetitionManager):
        """
        Initialize the NotebookManager
        Args:
            db: MongoDB database connection
            competition_manager: CompetitionManager instance
        """
        super().__init__(db['notebooks'])
        self.competition_manager = competition_manager
        self.max_values = {'score': 1.0, 'votes': 1.0, 'comments': 1.0}
        self.min_values = {'score': 0.0, 'votes': 0.0, 'comments': 0.0}
        self._initialize()

    def _initialize(self):
        """Setup indexes and load initial max values"""
        # Create indexes for all queryable fields
        self._create_core_indexes()
        self._load_max_values()

    def _create_core_indexes(self):
        """Create all necessary indexes"""
        # Core document indexes
        self._create_index([('notebook_name', 1), ('domain_name', 1)], unique=True)
        # Score indexes
        for score_type in self.SCORE_CONFIGS:
            self._create_index([(f'scores.{score_type}', -1)],unique=False)
        
        # Raw metric indexes
        for metric in ['score', 'votes', 'comments']:
            self._create_index([(f'metrics.{metric}', -1)],unique=False)
        
        # Metadata indexes
        self._create_index([('last_updated', -1)],unique=False)

    def _load_max_values(self):
        """Load maximum and minimum values for normalization from database"""
        try:
            result = list(self.collection.aggregate([
                {'$group': {
                    '_id': None,
                    'max_score': {'$max': '$metrics.score'},
                    'max_votes': {'$max': '$metrics.votes'},
                    'max_comments': {'$max': '$metrics.comments'},
                    'min_score': {'$min': '$metrics.score'},
                    'min_votes': {'$min': '$metrics.votes'},
                    'min_comments': {'$min': '$metrics.comments'}
                }}
            ]))
            
            if result:
                self.max_values = {
                    'score': max(result[0].get('max_score', 1), 1),
                    'votes': max(result[0].get('max_votes', 1), 1),
                    'comments': max(result[0].get('max_comments', 1), 1)
                }
                self.min_values = {
                    'score': result[0].get('min_score', 0),
                    'votes': result[0].get('min_votes', 0),
                    'comments': result[0].get('min_comments', 0)
                }
        except Exception as e:
            logger.error(f"Error loading max/min values: {str(e)}")
            self.max_values = {'score': 1.0, 'votes': 1.0, 'comments': 1.0}
            self.min_values = {'score': 0.0, 'votes': 0.0, 'comments': 0.0}

    def _update_max_values(self, metrics: Dict):
        """Update in-memory max and min values with new metrics"""
        for metric in ['score', 'votes', 'comments']:
            if metric in metrics:
                if metrics[metric] > self.max_values[metric]:
                    self.max_values[metric] = metrics[metric]
                if metrics[metric] < self.min_values[metric]:
                    self.min_values[metric] = metrics[metric]

    def register_score_type(self, score_type: str, config: Dict):
        """
        Register a new score type dynamically
        Args:
            score_type: Name of the score type
            config: Dictionary containing:
                   - weights: Dict of metric:weight pairs
                   - requires_normalization: bool
                   - description: Optional description
        """
        required_keys = ['weights', 'requires_normalization']
        if not all(k in config for k in required_keys):
            raise ValueError(f"Config must contain: {required_keys}")
            
        self.SCORE_CONFIGS[score_type] = config
        self._create_index([(f'scores.{score_type}', -1)])
        logger.info(f"Registered new score type: {score_type}")

    def calculate_scores(self, metrics: Dict) -> Dict[str, float]:
        """
        Calculate all scores for given metrics
        Args:
            metrics: Dictionary of raw metrics
        Returns:
            Dictionary of {score_type: calculated_score}
        """
        scores = {}
        for score_type, config in self.SCORE_CONFIGS.items():
            total = 0.0
            for metric, weight in config['weights'].items():
                value = metrics.get(metric, 0)
                
                if config['requires_normalization'] and metric in self.max_values:
                    value = (np.log1p(value) - np.log1p(self.min_values[metric])) / (np.log1p(self.max_values[metric])-np.log1p(self.min_values[metric]))
                
                total += weight * value
            
            scores[score_type] = max(0.0, min(total, 1.0))  # Clamp to 0-1 range
        
        return scores

    def import_from_file(self, file_path: str, competition_name: str, 
                       metrics: Optional[Dict] = None) -> bool:
        """
        Import a Jupyter notebook with automatic score calculation
        Args:
            file_path: Path to .ipynb file
            competition_id: Associated competition ID
            metrics: Dictionary of scoring metrics
        Returns:
            bool: True if import was successful
        Raises:
            ValueError: If file or competition is invalid
        """
        # Validate inputs
        # if not self.competition_manager.exists(competition_id):
        #     raise ValueError(f"Competition {competition_id} doesn't exist")
            
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File {file_path} does not exist")
            
        if not file_path.endswith('.ipynb'):
            raise ValueError("Only Jupyter notebook (.ipynb) files are supported")

        # Read notebook content
        notebook_name = os.path.splitext(os.path.basename(file_path))[0]
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                notebook_content = json.load(f)
        except Exception as e:
            raise ValueError(f"Error reading notebook file: {str(e)}")

        # Process metrics and calculate scores
        metrics = metrics or {}
        if metrics:
            self._update_max_values(metrics)
            scores = self.calculate_scores(metrics)
        else:
            scores = {}
        # get the object id of the competition from domains collection
        domain_id = self.competition_manager.get(competition_name)
        # Create notebook document
        notebook_doc = {
            'domain_id':domain_id['_id'],
            'notebook_name': notebook_name,
            'domain_name': competition_name,
            'content': notebook_content,
            'metrics': metrics,
            'scores': scores,
            'last_updated': datetime.datetime.now()
        }

        # Use BaseManager's update operation
        result = self._update(
            {'notebook_name': notebook_name, 'domain_name': competition_name},
            notebook_doc,
            upsert=True
        )

        # Periodically refresh max values (every 100 imports)
        if self.collection.count_documents({}) % 100 == 0:
            self._load_max_values()

        return result

    def query_notebooks(self, competition_id: str = None,
                      filters: Dict[str, Any] = None,
                      sort_by: str = None,
                      descending: bool = True,
                      limit: int = 10,
                      include_content: bool = False) -> List[Dict]:
        """
        Flexible notebook querying with direct metric and score filtering
        Args:
            competition_id: Optional competition filter
            filters: Dictionary of field:value filters
                    e.g. {'metrics.votes': {'$gte': 50}, 'scores.quality': {'$gt': 0.7}}
            sort_by: Field to sort by (supports both metrics and scores)
            descending: Sort direction
            limit: Maximum results to return
            include_content: Whether to include notebook content
        Returns:
            List of matching notebooks
        """
        # Build base query
        query = {}
        if competition_id:
            query['competition_id'] = competition_id
        
        # Apply filters
        if filters:
            for field, condition in filters.items():
                # Validate field prefix
                if not field.startswith(('metrics.', 'scores.', 'metadata.')):
                    raise ValueError(f"Invalid filter field: {field}. Must start with metrics., scores., or metadata.")
                query[field] = condition

        # Configure projection
        projection = {'_id': 0}
        if not include_content:
            projection['content'] = 0

        # Build sort specification
        sort = [(sort_by, -1 if descending else 1)] if sort_by else None

        # Execute query
        cursor = self.collection.find(query, projection)
        if sort:
            cursor.sort(sort)
        if limit:
            cursor.limit(limit)

        return list(cursor)

    def get_by_metrics(self, competition_id: str = None,
                     min_score: float = None,
                     min_votes: int = None,
                     min_comments: int = None,
                     limit: int = 10) -> List[Dict]:
        """
        Convenience method for querying by raw metrics
        Args:
            competition_id: Optional competition filter
            min_score: Minimum raw score
            min_votes: Minimum vote count
            min_comments: Minimum comment count
            limit: Maximum results
        Returns:
            List of matching notebooks
        """
        filters = {}
        if min_score is not None:
            filters['metrics.score'] = {'$gte': min_score}
        if min_votes is not None:
            filters['metrics.votes'] = {'$gte': min_votes}
        if min_comments is not None:
            filters['metrics.comments'] = {'$gte': min_comments}

        return self.query_notebooks(
            competition_id=competition_id,
            filters=filters,
            sort_by='metrics.score',
            limit=limit
        )

    def get_by_score(self, competition_id: str, score_type: str, 
                   min_score: float = 0.0, limit: int = 10,
                   include_content: bool = False) -> List[Dict]:
        """
        Get notebooks filtered and sorted by a specific score
        Args:
            competition_id: Competition ID to filter by
            score_type: Which score to sort by
            min_score: Minimum score threshold (0-1)
            limit: Maximum number of results
            include_content: Whether to include notebook content
        Returns:
            List of notebook documents
        """
        if score_type not in self.SCORE_CONFIGS:
            raise ValueError(f"Unknown score type: {score_type}")

        return self.query_notebooks(
            competition_id=competition_id,
            filters={f'scores.{score_type}': {'$gte': min_score}},
            sort_by=f'scores.{score_type}',
            limit=limit,
            include_content=include_content
        )

    def get_top_by_metric(self, competition_id: str,
                        metric: str,
                        min_value: float = None,
                        limit: int = 10) -> List[Dict]:
        """
        Get top notebooks by specific raw metric
        Args:
            competition_id: Competition ID filter
            metric: Metric name (score, votes, comments)
            min_value: Optional minimum value threshold
            limit: Maximum results
        Returns:
            List of notebooks sorted by metric
        """
        filters = {}
        if min_value is not None:
            filters[f'metrics.{metric}'] = {'$gte': min_value}

        return self.query_notebooks(
            competition_id=competition_id,
            filters=filters,
            sort_by=f'metrics.{metric}',
            limit=limit
        )

    def recalculate_scores(self, competition_name: str = None,
                         update_max_values: bool = True) -> int:
        """
        Recalculate scores for notebooks
        Args:
            competition_id: Optional competition ID to filter by
            update_max_values: Whether to refresh max values first
        Returns:
            int: Number of notebooks updated
        """
        if update_max_values:
            self._load_max_values()

        query = {}
        if competition_name:
            query['domain_name'] = competition_name

        updated_count = 0
        for notebook in self.collection.find(query):
            new_scores = self.calculate_scores(notebook.get('metrics', {}))
            if new_scores != notebook.get('scores', {}):
                result = self._update_with_operators(
                    {'_id': notebook['_id']},
                    {'$set': {'scores': new_scores}}
                )
                if result:
                    updated_count += 1

        logger.info(f"Recalculated scores for {updated_count} notebooks")
        return updated_count

    def export_to_file(self, notebook_id: str, competition_id: str,
                     output_path: str) -> bool:
        """
        Export notebook to .ipynb file
        Args:
            notebook_id: Notebook ID
            competition_id: Competition ID
            output_path: Destination file path
        Returns:
            bool: True if successful
        """
        notebook = self._get_by_id({'notebook_id': notebook_id, 'competition_id': competition_id})
        if not notebook or 'content' not in notebook:
            return False
            
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(notebook['content'], f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error exporting notebook: {str(e)}")
            return False

    def get_notebook(self, notebook_id: str, competition_id: str) -> Optional[Dict]:
        """
        Get single notebook by ID
        Args:
            notebook_id: Notebook ID
            competition_id: Competition ID
        Returns:
            Notebook document or None if not found
        """
        return self._get_by_id({'notebook_id': notebook_id, 'competition_id': competition_id})

    def notebook_exists(self, notebook_id: str, competition_id: str) -> bool:
        """
        Check if notebook exists
        Args:
            notebook_id: Notebook ID
            competition_id: Competition ID
        Returns:
            bool: True if notebook exists
        """
        return self._validate_exists({'notebook_id': notebook_id, 'competition_id': competition_id})

    def get_by_competition(self, competition_id: str,
                         include_content: bool = False) -> List[Dict]:
        """
        Get all notebooks for a competition
        Args:
            competition_id: Competition ID
            include_content: Whether to include notebook content
        Returns:
            List of notebooks
        """
        return self.query_notebooks(
            competition_id=competition_id,
            include_content=include_content
        )