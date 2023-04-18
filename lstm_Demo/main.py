from math import sqrt
from numpy import concatenate
from matplotlib import pyplot
import numpy as np
from sklearn.metrics import mean_squared_error
from keras.models import Sequential
from keras.layers import Dense, Dropout
from keras.layers import LSTM
from pandas import read_csv
from pandas import DataFrame
from pandas import concat
from sklearn.preprocessing import MinMaxScaler
from keras.optimizers import Adam
from keras.initializers import Constant
from sklearn.preprocessing import LabelEncoder
from keras.regularizers import l2
import pandas as pd








pd.set_option('display.max_columns',1000)
pd.set_option('display.width', 1000)
pd.set_option('display.max_colwidth',1000)



class LSTM_Demo:
    def __init__(self,n_hours = 3):
        self.n_hours=n_hours
        self.n_features=12
        self.model=None
        self.scaler=None
        self.history=None
    def load_data(self):
        # load dataset
        dataset = read_csv('../data_processing/result.csv', header=0, index_col=0,encoding="ANSI")
        # dataset = read_csv('single.csv', header=0, index_col=0,encoding="ANSI")
        self.n_features=dataset.shape[1]
        return dataset

    def split_train_test(self,reframed):

        # split into train and test sets
        values = reframed.values

        n_train_hours = 13460
        train = values[:n_train_hours, :]
        test = values[n_train_hours:, :]

        # split into input and outputs
        n_obs = self.n_hours * self.n_features
        # 有32=(4*8)列数据，取前24=(3*8) 列作为X，倒数第8列=(第25列)作为Y
        train_X, train_y = train[:, :n_obs], train[:, -self.n_features]
        test_X, test_y = test[:, :n_obs], test[:, -self.n_features]
        return train_X,test_X, test_y, train_y
    def maxmin_scaler(self,dataset):

        #处理缺失值
        dataset=dataset.fillna(dataset.mean())
        # print(dataset.isnull().sum())
        values = dataset.values
        values = values.astype('float32')
        # 标准化/放缩 特征值在（0,1）之间
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        scaled = self.scaler.fit_transform(values)
        return scaled

    def series_to_supervised(self,data, n_in=1, n_out=1, dropnan=True):

        n_vars = 1 if type(data) is list else data.shape[1]
        df = DataFrame(data)
        cols, names = list(), list()
        # input sequence (t-n, ... t-1)
        # 将3组输入数据依次向下移动3，2，1行，将数据加入cols列表（技巧：(n_in, 0, -1)中的-1指倒序循环，步长为1）
        for i in range(n_in, 0, -1):
            cols.append(df.shift(i))
            names += [('var%d(t-%d)' % (j + 1, i)) for j in range(n_vars)]
        # forecast sequence (t, t+1, ... t+n)
        # 将一组输出数据加入cols列表（技巧：其中i=0）
        for i in range(0, n_out):
            cols.append(df.shift(-i))
            if i == 0:
                names += [('var%d(t)' % (j + 1)) for j in range(n_vars)]
            else:
                names += [('var%d(t+%d)' % (j + 1, i)) for j in range(n_vars)]
        # cols列表(list)中现在有四块经过下移后的数据(即：df(-3),df(-2),df(-1),df)，将四块数据按列 并排合并
        agg = concat(cols, axis=1)
        # 给合并后的数据添加列名
        agg.columns = names
        print(agg)
        # 删除NaN值列
        if dropnan:
            agg.dropna(inplace=True)
        return agg
    def get_splited_data(self):
        dataset=self.load_data()
        scaled=self.maxmin_scaler(dataset)


        # 转换成监督数据，四列数据，3->1，三组预测一组
        # 用3小时数据预测一小时数据，10个特征值

        # 构造一个3->1的监督学习型数据
        reframed = self.series_to_supervised(scaled, self.n_hours, 2)
        train_X,test_X, test_y, train_y=self.split_train_test(reframed)
        # 将数据转换为3D输入，timesteps=3，3条数据预测1条 [samples, timesteps, features]
        train_X = train_X.reshape((train_X.shape[0], self.n_hours, self.n_features))
        test_X = test_X.reshape((test_X.shape[0], self.n_hours, self.n_features))
        print(train_X.shape, train_y.shape, test_X.shape, test_y.shape)
        return train_X,test_X, test_y, train_y

    def do_train(self):
        train_X, test_X, test_y, train_y = self.get_splited_data()


        # 设计网络
        self.model = Sequential()
        # kernel_initializer = Constant(value=1.0), bias_initializer = 'zeros'
        self.model.add(LSTM(10, input_shape=(train_X.shape[1], train_X.shape[2]), kernel_initializer=Constant(value=1.0), bias_initializer='zeros',kernel_regularizer=l2(0.1), bias_regularizer=l2(0.05)))
        self.model.add(Dropout(0.2))
        self.model.add(Dense(1))
        self.model.compile(loss='mae', optimizer=Adam(learning_rate=1e-3))
        # 拟合网络
        self.history = self.model.fit(train_X, train_y, epochs=30, batch_size=50, validation_data=(test_X, test_y), verbose=1,
                            shuffle=False)

        print(self.model.evaluate(test_X, test_y))


    def do_predict(self):
        train_X, test_X, test_y, train_y = self.get_splited_data()

        # 执行预测
        model=self.model
        yhat = model.predict(test_X)
        # 将数据格式化成 n行 * 24列
        test_X = test_X.reshape((test_X.shape[0], self.n_hours * self.n_features))
        # 将预测列据和后7列数据拼接，因后续逆缩放时，数据形状要符合 n行*8列 的要求
        inv_yhat = concatenate((yhat, test_X[:, (-self.n_features+1):]), axis=1)
        # 对拼接好的数据进行逆缩放
        inv_yhat = self.scaler.inverse_transform(inv_yhat)
        inv_yhat = inv_yhat[:, 0]

        test_y = test_y.reshape((len(test_y), 1))
        # 将真实列据和后7列数据拼接，因后续逆缩放时，数据形状要符合 n行*8列 的要求
        inv_y = concatenate((test_y, test_X[:, (-self.n_features+1):]), axis=1)
        # 对拼接好的数据进行逆缩放
        inv_y = self.scaler.inverse_transform(inv_y)
        inv_y = inv_y[:, 0]

        # 计算RMSE误差值
        rmse = sqrt(mean_squared_error(inv_y, inv_yhat))
        self.plot(inv_y,inv_yhat)
        print('Test RMSE: %.3f' % rmse)

    def plot(self,inv_y,inv_yhat):
        # plot history
        pyplot.subplot(211)
        pyplot.plot(self.history.history['loss'], label='loss')
        pyplot.plot(self.history.history['val_loss'], label='val_loss')
        pyplot.legend()

        # pyplot.plot(self.history.history['acc'], label='acc')
        # pyplot.plot(self.history.history['val_acc'], label='val_acc')
        pyplot.subplot(223)
        pyplot.plot(inv_y, label='y')
        pyplot.plot(inv_yhat, label='yhat')
        pyplot.legend()
        pyplot.show()


if __name__ == "__main__":
    demo = LSTM_Demo()     #加载类
    demo.do_train()
    demo.do_predict()
