import pandas as pd
import numpy as np
from math import ceil
from matplotlib import pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from utils import dict_active_fun, dict_loss_fun


def _scale_dataset(values, scale_range):
    # normalize features
    scaler = MinMaxScaler(feature_range=scale_range or (0, 1))
    values = scaler.fit_transform(values)
    return values, scaler

# time series
def _series_to_supervised(values, col_names, n_in_timestep, n_out_timestep, dropnan=True, verbose=False):
    n_vars = 1 if type(values) is list else values.shape[1]
    if col_names is None:
        col_names = ["var%d" % (j + 1) for j in range(n_vars)]
    df = pd.DataFrame(values)
    cols, names = list(), list()

    # input sequence (t-n, ... t-1)
    for i in range(n_in_timestep, 0, -1):
        cols.append(df.shift(i))
        names += [("%s(t-%d)" % (col_names[j], i)) for j in range(n_vars)]

    # forecast sequence (t, t+1, ... t+n)
    for i in range(0, n_out_timestep):
        cols.append(df.shift(-i))
        if i == 0:
            names += [("%s(t)" % (col_names[j])) for j in range(n_vars)]
        else:
            names += [("%s(t+%d)" % (col_names[j], i)) for j in range(n_vars)]

    # put it all together
    agg = pd.concat(cols, axis=1)
    agg.columns = names

    # drop rows with NaN values
    if dropnan:
        agg.dropna(inplace=True)

    if verbose:
        print("\nsupervised data shape:", agg.shape)
    return agg


# split data
def _train_test_split(values, train_test_split, target_col_index, n_in_timestep, n_features, verbose=0):
    n_train_count = ceil(values.shape[0] * train_test_split)
    train = values[:n_train_count, :]
    test = values[n_train_count:, :]

    # split into input and outputs
    n_obs = n_in_timestep * n_features
    train_x, train_y = train[:, :n_obs], train[:, target_col_index]

    test_x, test_y = test[:, :n_obs], test[:, target_col_index]

    # reshape input to be 3D [samples, timesteps, features]
    train_x = train_x.reshape((train_x.shape[0], n_in_timestep, n_features))
    test_x = test_x.reshape((test_x.shape[0], n_in_timestep, n_features))

    if verbose:
        print("")
        print("train_X shape:", train_x.shape)
        print("train_y shape:", train_y.shape)
        print("test_X shape:", test_x.shape)
        print("test_y shape:", test_y.shape)
    return train_x, train_y, test_x, test_y


def load_data(file_path, target_col_name, input_dim, output_dim):
    data = pd.read_csv(file_path, encoding='gbk')
    # data.drop('date', axis=1, inplace=True)

    col_names = list(data.columns)
    n_features = len(col_names)
    target_col_index = col_names.index(target_col_name) - n_features

    values, scaler = _scale_dataset(data.values, None)
    data_new = _series_to_supervised(values, col_names=col_names, n_in_timestep=input_dim, n_out_timestep=output_dim)


    trainX, trainy, testX, testy = _train_test_split(values=data_new.values, train_test_split=0.7,
                                                     target_col_index=target_col_index, n_in_timestep=input_dim,
                                                     n_features=n_features)

    return trainX, trainy, testX, testy, scaler



def get_activation(active_name):
    if active_name in ('relu', 'sigmod', 'tanh', 'linear'):
        return dict_active_fun[active_name]
    else:
        raise ValueError('Activation config illegal')


class RNN():
    def __init__(self, hidden_dim=10, activation=('tanh', 'linear'), loss='mse', learning_rate=0.001, num_iter=100,
                 batch_size=10):
        # para
        self.learning_rate = learning_rate
        self.num_iter = num_iter
        self.batch_size = batch_size

        self.input_dim = None
        self.hidden_dim = hidden_dim
        self.output_dim = None
        self.paras = dict()
        self.lst_loss = []
        self.active_name = activation
        self.active = dict()
        self.loss_name = loss
        self.loss_fun = dict()

    def init_paras(self, X, y):
        self.input_dim = X.shape[-1]
        self.output_dim = 1 if len(y.shape) == 1 else y.shape[1]


        np.random.seed(5)
        self.paras['U'] = np.random.uniform(-np.sqrt(1. / self.input_dim), np.sqrt(1. / self.input_dim),
                                            (self.hidden_dim, self.input_dim))
        self.paras['V'] = np.random.uniform(-np.sqrt(1. / self.hidden_dim), np.sqrt(1. / self.hidden_dim),
                                            (self.output_dim, self.hidden_dim))
        self.paras['W'] = np.random.uniform(-np.sqrt(1. / self.hidden_dim), np.sqrt(1. / self.hidden_dim),
                                            (self.hidden_dim, self.hidden_dim))
        self.paras['ba'] = np.zeros((self.hidden_dim, 1))
        self.paras['by'] = np.zeros((self.output_dim, 1))

        # activation function
        self.active['a'], self.active['da'] = get_activation(self.active_name[0])
        self.active['y'], self.active['dy'] = get_activation(self.active_name[1])

        # loss function
        if self.loss_name == 'mse':
            self.loss_fun['fun'], self.loss_fun['d_fun'] = dict_loss_fun['mse']

    def forward(self, xi):
        a = list()
        a.append(np.zeros((self.hidden_dim, xi.shape[0])))
        for t in range(xi.shape[1]):
            a_next = self.active['a'](np.dot(self.paras['U'], xi[:, t].T) + np.dot(self.paras['W'], a[-1]) +
                                      self.paras['ba'])
            a.append(a_next)
        yt = self.active['y'](np.dot(self.paras['V'], a[-1]) + self.paras['by'])
        return a, yt

    def backward(self, xi, ai, yi, yi_pred):
        # Initialization gradient
        d_paras = dict()
        d_paras['U'] = np.zeros_like(self.paras['U'])
        d_paras['W'] = np.zeros_like(self.paras['W'])
        d_paras['ba'] = np.zeros_like(self.paras['ba'])

        dLdy = self.loss_fun['d_fun'](yi, yi_pred)
        d_paras['V'] = np.dot(dLdy * self.active['dy'](yi_pred), ai[-1].T)
        d_paras['by'] = dLdy.sum(axis=1)

        da = np.dot(self.paras['V'].T, dLdy)
        dzt = da * self.active['da'](ai[-1])

        # Time series backtracking
        for t in range(xi.shape[1])[::-1]:
            d_paras['W'] += np.dot(dzt, ai[t - 1].T)
            d_paras['U'] += np.dot(dzt, xi[:, t - 1])
            d_paras['ba'] += dzt.sum(axis=1)[:, np.newaxis]

            # update dzt :=  dz(t-1)
            dzt = np.dot(self.paras['W'].T, dzt) * self.active['da'](ai[t - 1])

        return d_paras

    def cal_loss(self, y_true, y_pred):
        return self.loss_fun['fun'](y_true, y_pred)

    def update_paras(self, d_paras):
        for i in d_paras.keys():
            self.paras[i] -= self.learning_rate * d_paras[i]

    def fit(self, X, y):
        self.init_paras(X, y)

        # Calculate the number of iterations according to batch size
        batch_count = ceil(X.shape[0] / self.batch_size)


        for iter in range(self.num_iter):
            iter_loss = 0

            for batch_i in range(batch_count):
                batch_start = batch_i * self.batch_size
                batch_end = (batch_i + 1) * self.batch_size

                # forward
                ai, yit = self.forward(X[batch_start:batch_end])

                # loss
                iter_loss += self.cal_loss(y[batch_start:batch_end], yit)

                # backward
                d_paras = self.backward(X[batch_start:batch_end], ai, y[batch_start:batch_end], yit)

                # update
                self.update_paras(d_paras)
            self.lst_loss.append(iter_loss)
            print('[iter %d]: loss:%.4f' % (iter, iter_loss))

    def predict(self, X, y, scaler):
        y_pred = np.zeros((X.shape[0], 1))
        for i in range(X.shape[0]):
            _, y_pred[i] = self.forward(X[[i]])

        # invert scaling for predict
        tmp = X[:, -1].copy()
        tmp[:, -1] = y_pred[:, 0]
        inv_yhat_t1 = scaler.inverse_transform(tmp)
        inv_yhat_t1 = inv_yhat_t1[:, -1]

        # invert scaling for actual
        tmp = X[:, -1].copy()
        tmp[:, -1] = y
        inv_y_t1 = scaler.inverse_transform(tmp)
        inv_y_t1 = inv_y_t1[:, -1]
        return inv_y_t1, inv_yhat_t1


if __name__ == '__main__':
    # parameter settings
    n_in_timestep = 3
    n_out_timestep = 1

    # data load
    trainX, trainy, testX, testy, scaler = load_data('./parsed.csv', 'cgm', n_in_timestep,
                                                     n_out_timestep)

    # create model
    model = RNN(hidden_dim=10, activation=('tanh', 'linear'), loss='mse', learning_rate=0.001, num_iter=100,
                      batch_size=32)
    model.fit(trainX, trainy)
    train_true, train_pred = model.predict(trainX, trainy, scaler)
    plt.plot(train_true, label='cgm')
    plt.plot(train_pred, label='forecast')
    fig = plt.gcf()
    plt.legend()
    fig.savefig('./train.png')
    plt.show()

    testy_true, testy_pred = model.predict(testX, testy, scaler)
    # print(type(testy_pred))

    print('test_loss:',model.cal_loss(testy_true, testy_pred) / len(testy_pred) / 10)
    # print(type(testy_pred))
    # plt.plot(testy_true, label= 'cgm')
    # plt.show()

    # plot
    plt.plot(testy_true, label='cgm')
    plt.plot(testy_pred, label='forecast')
    plt.legend()
    fig = plt.gcf()

    fig.savefig('./test.png')
    plt.show()
