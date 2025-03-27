
# Data Collection Structure
```
kaggle-research-project/
│
├── datasets/
│   ├── competitions.json
│   └── {dataset_slug}/  # e.g., titanic/
│       ├── titanic_metadata.json                # Example: titanic_metadata.json
│       ├── leaderboard/
│       │   └── scores.csv               # Columns: rank, team_id, score, date
│       │
│       └── notebooks/
│           ├── notebooks_metadata.json             # Columns: notebook_id, title, author, votes, score, url
│           └── code/
│               └── {notebook_id}/       # e.g., 123456/
│                   ├── comments_metadata.json
│                   ├── code.ipynb
│                   └── comments.json    # Top-voted comments with metadata
│
└── metadata_templates/
    ├── competitions.json            # Empty template with all required fields
    ├── titanic_metadata.json            # Empty template with all required fields
    ├── notebooks_metadata.json            # Empty template with all required fields
    └── comments_metadata.json            # CSV header template
```