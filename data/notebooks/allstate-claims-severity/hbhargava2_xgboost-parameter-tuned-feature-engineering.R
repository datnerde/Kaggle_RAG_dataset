# This R environment comes with all of CRAN preinstalled, as well as many other helpful packages
# The environment is defined by the kaggle/rstats docker image: https://github.com/kaggle/docker-rstats
# For example, here's several helpful packages to load in 

library(ggplot2) # Data visualization
library(readr) # CSV file I/O, e.g. the read_csv function
library(data.table)
library(xgboost)
library(stringr)
library(caret)

# Input data files are available in the "../input/" directory.
# For example, running this (by clicking run or pressing Shift+Enter) will list the files in the input directory
system("ls ../input")

# Any results you write to the current directory are saved as output.
#read train and test data set to new variable.
train <- fread("../input/train.csv")
test <- fread("../input/test.csv")

#have a new data frame with the target column.
train$loss <- log1p(train$loss)
train$loss <- scale(train$loss)
train_target <- data.frame(train[,loss])
setnames(train_target, "loss")

#remove the id and loss value so that both the test and train data set would be similar
train$id <- NULL
train$loss <- NULL
test$id <- NULL

#merge the train and test data set so that we can prepare the integer data for both of them
ntrains <- nrow(train)
train_test <- rbind(train,test)

#convert the all character column to integer
instanceconvert <- colnames(train_test[2:116])
for (i in instanceconvert)
{
  train_test[[i]] <- as.numeric(as.factor(train_test[[i]]))
}

#divide the train and test data set
x_train <- as.matrix(train_test[1:ntrains,])
x_test <- train_test[(ntrains+1):nrow(train_test),]

set.seed(1024)
#cv.res <- xgb.cv(data=as.matrix(x_train), label=as.matrix(train_target),nfold =4,nrounds =68,objective ="reg:linear")
#cv.res

param <- list("objective" =  "reg:linear","bst:eta" = 0.3,"bst:max_depth" = 5,
"silent" = 1,"nthread" = 16,"scale_pos_weight" = 1)

xgb_model <- xgboost(data=as.matrix(x_train), label=as.matrix(train_target),nrounds =68
,params = param,gamma = 0.1,subsample = 0.75,colsample_bytree = 1,min_child_weight=1
,max_delta_step = 0.1,lambda = 0.1)

#submitting the file.
submission <- fread("../input/sample_submission.csv")
submission$loss <- expm1(predict(xgb_model, as.matrix(x_test)))
write.csv(submission,"xgb.csv",row.names = FALSE)


