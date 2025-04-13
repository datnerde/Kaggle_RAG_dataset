# This Python 3 environment comes with many helpful analytics libraries installed
# It is defined by the kaggle/python docker image: https://github.com/kaggle/docker-python
# For example, here's several helpful packages to load in 

import numpy as np # linear algebra
import pandas as pd # data processing, CSV file I/O (e.g. pd.read_csv)
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

# Input data files are available in the "../input/" directory.
# For example, running this (by clicking run or pressing Shift+Enter) will list the files in the input directory

from subprocess import check_output
print(check_output(["ls", "../input"]).decode("utf8"))

# Any results you write to the current directory are saved as output.

#Data Preparation

#Import the data
#log transform the targets, failure to do so leads to a heavy bias for large losses. 
#Transform categorical data to numerical values
#Split the test data to check model behavior before submission.

train = pd.read_csv("../input/train.csv")
test =  pd.read_csv("../input/test.csv")


features = [x for x in train.columns if x not in ['id','loss']]
cat_features = [x for x in train.select_dtypes(include=['object']).columns if x not in ['id','loss']]
num_features = [x for x in train.select_dtypes(exclude=['object']).columns if x not in ['id','loss']]

#RMSE algorithims prefer symmetric data
train['log_loss'] = np.log(train['loss'])


ntrain = train.shape[0]
ntest = test.shape[0]
train_test = pd.concat((train[features], test[features])).reset_index(drop=True)
for c in range(len(cat_features)):
    train_test[cat_features[c]] = train_test[cat_features[c]].astype('category').cat.codes

train_x = train_test.iloc[:ntrain,:]
test_x = train_test.iloc[ntrain:,:]

X_train, X_test, y_train, y_test = train_test_split(train_x, train['log_loss'], test_size=0.33, random_state=42)
print("Split complete")

from sklearn.ensemble import RandomForestRegressor
model = RandomForestRegressor(n_estimators=100, criterion='mse',
max_depth=None, min_samples_split=2, min_samples_leaf=1,
min_weight_fraction_leaf=0.0, max_features='auto',
max_leaf_nodes=None, min_impurity_split=1e-07, bootstrap=True,
oob_score=False, n_jobs=1, random_state=None, verbose=0, warm_start=False)

#Train model on complete training data, make prediction on test data
model.fit(train_x, train['log_loss'])
predicted = model.predict(test_x)
predicted = np.exp(predicted) 
submission = pd.DataFrame({
       "id": test['id'],
        "loss": predicted
    })
submission.to_csv('RF.csv', index = False)


