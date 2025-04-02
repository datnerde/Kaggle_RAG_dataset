import tensorflow as tf
from tensorflow.python.ops import nn
from sklearn import preprocessing
from sklearn.cross_validation import StratifiedKFold
from sklearn.datasets import load_digits
def LoadData(test_size=0.25,is_images=True,one_hot=True):
    digits=load_digits()
    images=digits['images']
    data=digits['data']
    labels=digits['target']
    
    n_folds=int(1/test_size)
    skf=StratifiedKFold(labels,n_folds=n_folds)
    train_index,test_index=list(skf)[0]
    
    lb=preprocessing.LabelBinarizer()
    transformed_labels=lb.fit_transform(labels)
    if(is_images == True):
        if(one_hot ==True):
            return (images[train_index,:,:],images[test_index,:,:],transformed_labels[train_index,:],transformed_labels[test_index,:])
        else:
            return (images[train_index,:,:],images[test_index,:,:],labels[train_index],labels[test_index])
    else:
        if(one_hot == True):
            return (data[train_index,:],data[test_index,:],transformed_labels[train_index,:],transformed_labels[test_index,:])
        else:
            return (data[train_index,:],data[test_index,:],labels[train_index],labels[test_index])

train_x,test_x,train_y,test_y = LoadData(is_images=True,one_hot=True)
num_samples,Width,Height = train_x.shape
num_classes = train_y.shape[1]
num_hidden = 20
num_batches = 10
batch_size = int(num_samples / num_batches)
epoches = 300
display_epochs = 10
learning_rate = 0.04

def conv2d(x,W,b,stride=1):
    convolution_result = nn.conv2d(x,W,strides=[1,stride,stride,1],padding='SAME')
    convolution_result_with_bias = nn.bias_add(convolution_result,b)
    relu_result = nn.relu(convolution_result_with_bias)
    return relu_result
    
def pooling(x,k=2):
    pooling_result = nn.max_pool(x,ksize=[1,k,k,1],strides=[1,k,k,1],padding='SAME')
    return pooling_result

x = tf.placeholder(dtype=tf.float32,shape=[None,Width,Height])
y = tf.placeholder(dtype=tf.float32,shape=[None,num_classes])

Weight = {'Convolution_filter':tf.Variable(tf.random_normal([3,3,1,10]),dtype=tf.float32),
        'Fully_connection':tf.Variable(tf.random_normal([4*4*10,num_hidden]),dtype=tf.float32),
        'Output':tf.Variable(tf.random_normal([num_hidden,num_classes]),dtype=tf.float32)}

Bias = {'Convolution_filter':tf.Variable(tf.random_normal([10]),dtype=tf.float32),
        'Fully_connection':tf.Variable(tf.random_normal([num_hidden]),dtype=tf.float32),
        'Output':tf.Variable(tf.random_normal([num_classes]),dtype=tf.float32)}

keep_prob = tf.placeholder(dtype=tf.float32)
        
def model(x,weight,bias,keep_prob=keep_prob):
    x=tf.expand_dims(x,3)
    convolution = conv2d(x,weight['Convolution_filter'],bias['Convolution_filter'])
    pool = pooling(convolution)
    reshaped_pooling = tf.reshape(pool,[-1,4*4*10])
    hidden_output = nn.relu(nn.bias_add(tf.matmul(reshaped_pooling,weight['Fully_connection']),bias['Fully_connection']))
    dropout_hidden_output = nn.dropout(hidden_output,keep_prob=keep_prob)
    output = nn.relu(nn.bias_add(tf.matmul(dropout_hidden_output,weight['Output']),bias['Output']))
    return output

pred = model(x,Weight,Bias,keep_prob)
cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(pred,y))
accuracy = tf.reduce_mean(tf.cast(tf.equal(tf.argmax(pred,1),tf.argmax(y,1)),tf.float32))
optimizer = tf.train.GradientDescentOptimizer(learning_rate=learning_rate).minimize(cost)
init = tf.initialize_all_variables()

with tf.Session() as sess:
    sess.run(init)
    for epoch in range(epoches):
        for start,end in zip(range(0,num_samples,batch_size),range(batch_size,num_samples,batch_size)):
            sess.run(optimizer,feed_dict={x:train_x[start:end],y:train_y[start:end],keep_prob : 0.8})

        if((epoch+1) % display_epochs == 0):
            print("training epochs %d"%(epoch+1))
            
            accuracy_value = sess.run(accuracy,feed_dict={x:test_x,y:test_y,keep_prob:1.})
            print("accuracy on test set is %f"%accuracy_value)
    print("Optimization finished!")

