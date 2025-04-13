library(data.table)
library(fasttime)
library(lightgbm)

set.seed(0)

#---------------------------
cat("Defining functions...\n")
prep <- function(dt_fn, meta_fn, weather_fn, drops, sort_timestamp = FALSE, n_max = Inf){
  
  cat("Loading data...\n") 
  dt <- fread(dt_fn, nrows = n_max, verbose = FALSE)
  weather <- fread(weather_fn, nrows = n_max, verbose = FALSE)
  meta <- fread(meta_fn, nrows = n_max, verbose = FALSE)
  
  cat("Merging datasets...\n")
  dt[meta, on = "building_id", names(meta) := mget(names(meta))]
  dt[weather, on = c("site_id", "timestamp"), names(weather) := mget(names(weather))]
  
  rm(meta, weather)
  invisible(gc())  
  
  cat("Processing features...\n")
  dt[, (drops) := NULL
     ][, timestamp := fastPOSIXct(timestamp)
       ][, `:=`(wday = wday(timestamp),
                hour = hour(timestamp), 
                year_built = year_built - 1900,
                square_feet = log1p(square_feet))]

  cat("Converting categorical columns...\n")
  dt[, names(dt) := lapply(.SD, function(x) {if (is.character(x)) x <- as.integer(as.factor(x)); x})]
  
  if (sort_timestamp) setorder(dt, timestamp)
  dt[, timestamp := NULL]
}

#---------------------------
cat("Preparing train data...\n")
cats <- c("building_id", "site_id", "meter", "primary_use", "hour", "wday")
drops <- c("sea_level_pressure", "wind_direction", "wind_speed")
tr <- prep("../input/ashrae-energy-prediction/train.csv",
           "../input/ashrae-energy-prediction/building_metadata.csv",
           "../input/ashrae-energy-prediction/weather_train.csv",
           drops, TRUE)
y <- log1p(tr$meter_reading)
tr[, meter_reading := NULL]
tr <- data.matrix(tr)

#---------------------------
cat("Training model...\n")

p <- list(boosting = "gbdt",
          objective = "regression_l2",
          metric = "rmse",
          nthread = 4,
          learning_rate = 0.05,
          num_leaves = 40,
          colsample_bytree = 0.85,
          lambda = 2)

N <- nrow(tr)
tsf <- caret::createTimeSlices(y, N/2, N/2)
models <- list()
imp <- data.table()

for (i in seq_along(tsf)){
  cat("\nFold:", i, "\n")
  idx <- tsf[[i]][[1]]
  
  xtrain <- lgb.Dataset(tr[-idx, ], label = y[-idx], categorical_feature = cats)
  xval <- lgb.Dataset(tr[idx, ], label = y[idx], categorical_feature = cats)
  models[[i]] <- lgb.train(p, xtrain, 4000, list(val = xval), eval_freq = 200, early_stopping_rounds = 200)
  
  imp <- rbind(imp, lgb.importance(models[[i]]))
  
  rm(xtrain, xval)
  invisible(gc())
}

lgb.plot.importance(imp[, lapply(.SD, mean), by=Feature], ncol(tr), cex=1)

rm(tr, y, imp, p, tsf, N, i, idx)
invisible(gc())

#---------------------------
cat("Preparing test data...\n")
te <- prep("../input/ashrae-energy-prediction/test.csv",
           "../input/ashrae-energy-prediction/building_metadata.csv",
           "../input/ashrae-energy-prediction/weather_test.csv",
           drops)
invisible(gc())
te <- as.matrix(te[, row_id := NULL])
invisible(gc())

#---------------------------
cat("Making predictions...\n")
pred_te <- sapply(models, function(m_lgb) expm1(predict(m_lgb, te)))
invisible(gc())

sub <- fread("../input/ashrae-energy-prediction/sample_submission.csv")
sub[, meter_reading := round(rowMeans(pred_te), 2)
    ][meter_reading < 0, meter_reading := 0]

fwrite(sub, "submission.csv")
