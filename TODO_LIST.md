
## Depreciated 
## Some BIG BUGS/ISSUES found to be fixed (Urgent)

1. Ensure that the name of ipynb files crawled/downloaded **EXACTLY** matches the one used in the metadata file. (Currently, let us just consider ipynb type of files, and do not consider R or pure python file.) Because we will calculate the score and retrieval the corresponding notebook based on the name provided in the metadata file. **Currently, it seems that there is a mismatch between the name present in the metadata file and the name of the downloaded ipynb files.**
2. Ensure the name of the ipynb files in the metadata is **unique**. Becasue I found that there is a case that different users have the same name of notebook file, for example, two user both created the file "titanic.ipynb". This will cause a problem when we try to retrieve the notebook based on the name provided in the metadata file.


## Urgent TODOs
1. Fix the copyed notebook issue. We need to ensure that all notebooks are unique and not copied.
2. Investigate the usage of kaggle official api for pulling the notebooks.
     Check this link: https://stackoverflow.com/questions/61130369/kaggle-directly-download-input-data-from-copied-kernel
3. Collect comments only after the two steps are done.


## April 12
Main goal: Interact with MongoDB and frontend.

## use logger.info() instead of print

### 1. We should have code for creating two databases: 1. Training_and_test_data and 2. Notebook and 3. User_profile, collection: user_id (uuid): . 4. Competition_history_tracker 

1. Training_and_test_data should contain the training and test csv files. Note 1: both file should be less tha 5MB. （Making the size prefebly to be an argument). Note 2: check how to save csv files in MongoDB. Note 3: collection should be competition ticker
2. Notebook: this should contain the notebooks collected. Should uniquely match the ticker used for data. 

### 2. We should check the reponse from user is valid or not. If yes, we call the kaggle's API to calculate the score.

1. We first check if user's response is valid or not. For instance, whether the length of the predictions matches the number of the test data. 2. Also, if the metrics are the same what we required (check numerical values).
 
**Note**: Adding more corner cases to check the validity of the response.

check [Link](https://www.kaggle.com/docs/api)

```bash
kaggle competitions submit -c [COMPETITION] -f [FILE] -m [MESSAGE]: make a competition submission
```

```python 

import autods 

autods.get_category ## kaggle and no kaggle
autods.get_competition(kaggle=True) ## ['titanic', 'house-prices-advanced-regression-techniques', 'digit-recognizer']

## separate the checking validation and the submission


def autods.evaluate(
     category='kaggle', ##
    competition ='titanic',
    submission_file='submission.csv',
    user_id = 'xx',
):

     if submission_file is valid:
          ## length and metrics obtain from a metadata file
          ## length and metrics obtain from MongoDB

     ## call bash
     kaggle competitions submit -c [COMPETITION] -f [FILE] -m [MESSAGE]: make a competition submission
```

## Task Manager(user_id)

1. Handling a complete series of queries. 
2. Markdown time for each sending and receiving.
3. **Most Important:** We only send next query if the previous one is successfully completed. Linked back to the 4th database.
