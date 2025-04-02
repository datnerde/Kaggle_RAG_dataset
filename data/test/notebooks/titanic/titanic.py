#coding=utf-8
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.cross_validation import KFold
from sklearn import preprocessing
from sklearn.ensemble import GradientBoostingClassifier

#Print you can execute arbitrary python code
train = pd.read_csv("../input/train.csv", dtype={"Age": np.float64}, )
test = pd.read_csv("../input/test.csv", dtype={"Age": np.float64}, )

#Print to standard output, and see the results in the "log" section below after running your script

# print("\n\nSummary statistics of training data")
# print(train.describe())

# change the sex
train.loc[train["Sex"] == "male", "Sex"] = 0.0
train.loc[train["Sex"] == "female", "Sex"] = 1.0

test.loc[test["Sex"] == "male", "Sex"] = 0.0
test.loc[test["Sex"] == "female", "Sex"] = 1.0

# change "Embarked"
train["Embarked"]=train["Embarked"].fillna("S")
train.loc[train["Embarked"] == "S", "Embarked"] = 0.0
train.loc[train["Embarked"] == "C", "Embarked"] = 1.0
train.loc[train["Embarked"] == "Q", "Embarked"] = 2.0

test["Embarked"]=test["Embarked"].fillna("S")
test.loc[test["Embarked"] == "S", "Embarked"] = 0.0
test.loc[test["Embarked"] == "C", "Embarked"] = 1.0
test.loc[test["Embarked"] == "Q", "Embarked"] = 2.0

# change "cabin"
train["Cabin"] = train["Cabin"].fillna("N")
train.loc[train["Cabin"] != "N", "Cabin"] = 1
train.loc[train["Cabin"] == "N", "Cabin"] = 0

test["Cabin"] = test["Cabin"].fillna("N")
test.loc[test["Cabin"] != "N", "Cabin"] = 1
test.loc[test["Cabin"] == "N", "Cabin"] = 0

# change "Age"
train["Age"]=train["Age"].fillna(train["Age"].median())

test["Age"]=test["Age"].fillna(train["Age"].median())

# change "Fare"
train["Fare"]=train["Fare"].fillna(train["Fare"].median())

test["Fare"]=test["Fare"].fillna(train["Fare"].median())

print("\n\nTop of the training data:")
# train
predictors = ["Pclass", "Sex", "Age", "SibSp", "Parch", "Fare", "Embarked","Cabin"]
#print(train[predictors].head())
alg = clf_gbrt = GradientBoostingClassifier(n_estimators=50, learning_rate=0.1,max_depth=4, random_state=0)
train_predictors=train[predictors]
train_target = train["Survived"]
# train_predictors = preprocessing.scale(train_predictors)
clf_lg=alg.fit(train_predictors, train_target)

accuracy=clf_lg.score(train_predictors,train_target)
print(accuracy)

# test
# Make predictions using the test set.
predictions = clf_lg.predict(test[predictors])

print(predictions)
predictions[predictions > .5] = 1
predictions[predictions <=.5] = 0

submission = pd.DataFrame({
        "PassengerId": test["PassengerId"],
        "Survived": predictions
    })
print(submission)

#Any files you save will be available in the output tab below
# train.to_csv('copy_of_the_training_data.csv', index=False)

#Any files you save will be available in the output tab below
submission.to_csv('submission.csv', index=False)