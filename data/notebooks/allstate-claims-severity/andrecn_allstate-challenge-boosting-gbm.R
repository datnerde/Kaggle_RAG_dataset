# Allstate challenge
#Boosting with trees prediction
library('ggplot2')
library('caret')
library('dplyr')

trainRAW <- read.csv("../input/train.csv", na.strings = c("", "NA"))
testRAW <- read.csv("../input/test.csv")

summary(trainRAW)
# the numeric attributes are already between [0,1]
sum(is.na(trainRAW))
hist(log(trainRAW$loss))

# removing columns that nlevels_train data is different from the nlevels_test data
# and removing columns that have nlevels > 5
cols <- rep(TRUE, length(names(testRAW)))
for (i in 1:length(names(testRAW))){
    if (class(testRAW[[i]]) == "factor"){
        if (!isTRUE(all.equal(levels(trainRAW[[i]]), levels(testRAW[[i]]))) | nlevels(testRAW[[i]]) > 5){
            cols[i] <- FALSE  
        } 
    }
}
trainMOD <- trainRAW[,cols]
testMOD <- testRAW[,cols]

#creating dummies
dummies <- dummyVars( ~., data = testMOD)
trainDUM <- data.frame((predict(dummies, newdata = trainMOD)), loss = trainMOD$loss)
testDUM <- data.frame((predict(dummies, newdata = testMOD)))

# check for NearZeroValues
nz <- nearZeroVar(trainDUM, saveMetrics = TRUE)
nznames <- rownames(nz[nz$nzv == TRUE,])
trainNZ <- trainDUM[,!(names(trainDUM) %in% nznames)]
testNZ <- testDUM[,!(names(testDUM) %in% nznames)]
trainNZ$loss <- log(trainNZ$loss)

#boosting GBM
inTrain <- createDataPartition(y=trainRAW$loss, p=0.7, list = FALSE)
trainingGBM <- trainNZ[inTrain,]
testingGBM <- trainNZ[-inTrain,]

modfit <- train(loss ~., method = "gbm", data = trainingGBM, verbose = FALSE)
prediction <- predict(modfit, testingGBM)
plot(prediction, testingGBM$loss, pch = 19)
error <- prediction/testingGBM$loss - 1
summary(error)
boxplot(error, main = "Testing Error (Prediction/test.loss -1)", ylab = "Absolute error")

# saving prediction data.frame
prediction.test <- exp(predict(modfit, testNZ))
predictionDF <- data.frame(id = testRAW$id, loss = prediction.test)
write.csv(predictionDF, file = 'prediction_test_GBM_1.csv', row.names = F)