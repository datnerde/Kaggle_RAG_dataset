library(Matrix)
library(glmnet)

# load data
train <- read.csv("../input/train.csv",sep=",",header=T)
test <- read.csv("../input/test.csv",sep=",",header = T)

# separate target column
y <- log(train[,"loss"]+200)
train <- train[,-which(names(train)=="loss")]

# deal with factors (one-hot)
full <- rbind(train,test)
x.full <- sparse.model.matrix(~.,full)[,-1]
x.train <- x.full[1:nrow(train),]
x.test <- x.full[(nrow(train)+1):nrow(full),]
rm(full,x.full)

# fit linear model with lasso penalty regularization
linmod <- glmnet(x.train,y,
                 family = "gaussian",
                 alpha=1,
                 lambda=exp(-8.383838))

# predict
pred <- exp(predict(linmod,x.test))-200
submission <- data.frame(id=test$id,loss=pred[,1])
write.table(submission,file="submission.csv",sep=",",row.names=FALSE)
