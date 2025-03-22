# Building High-Quality Data Science Datasets for RAG, Fine-tuning, and Prompt Engineering

## Project Goal
Create comprehensive, well-structured datasets from Kaggle competitions that can be used for:
- Retrieval-Augmented Generation (RAG)
- Model fine-tuning and pre-training
- Prompt engineering experimentation
- Multi-agent Systems (MAS) 

## Data Collection Process

### Step 1: Identifying and Collecting High-Quality Solutions
1. Navigate to the target Kaggle competition (starting with Titanic dataset)
2. Go to the ["Code"](https://www.kaggle.com/competitions/titanic/code) section of the competition
3. Sort solutions by `Most Votes` 
4. Download notebooks meeting these criteria:
   - Reported `Score` > 0.75

*We aim to collect approximately 30 solutions per dataset*


### Step 2: Data Extraction and Structuring

*Download the previsouly identified solutions in original Jupyter notebook format (.ipynb)*
For each notebook, extract and organize content into the following structure:

```
dataset_name/
  ├── solution_id_1/
  │   ├── metadata.json  # Contains score, votes, author, etc.
  │   ├── text/          # All markdown and plain text content
  │   ├── code/          # All code cells' content
  │   └── output/
  │       ├── text/      # Text-based outputs
  │       ├── tables/    # Table outputs (CSV format where possible)
  │       └── images/    # Visualizations and other images
  ├── solution_id_2/
  │   └── ...
  └── ...
```

### Step 3: Data Storage
*To be implemented later: MongoDB integration*


## Quality Control Guidelines
- Ensure all code snippets are properly extracted with relevant comments
- Preserve the relationship between code cells and their outputs
- Maintain consistent formatting across all extracted content
- Document any data transformation steps applied during extraction
- Track metadata including original notebook URLs and performance metrics
