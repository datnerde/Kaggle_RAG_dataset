## Some BIG BUGS/ISSUES found to be fixed (Urgent)

1. Ensure that the name of ipynb files crawled/downloaded **EXACTLY** matches the one used in the metadata file. (Currently, let us just consider ipynb type of files, and do not consider R or pure python file.) Because we will calculate the score and retrieval the corresponding notebook based on the name provided in the metadata file. **Currently, it seems that there is a mismatch between the name present in the metadata file and the name of the downloaded ipynb files.**
2. Ensure the name of the ipynb files in the metadata is **unique**. Becasue I found that there is a case that different users have the same name of notebook file, for example, two user both created the file "titanic.ipynb". This will cause a problem when we try to retrieve the notebook based on the name provided in the metadata file. 



## Urgent TODOs
1. Fix the copyed notebook issue. We need to ensure that all notebooks are unique and not copied.
2. Investigate the usage of kaggle official api for pulling the notebooks.
     Check this link: https://stackoverflow.com/questions/61130369/kaggle-directly-download-input-data-from-copied-kernel
3. Collect comments only after the two steps are done.