import time
import numpy as np
import tensorflow as tf

np.random.seed(1)
tf.compat.v1.set_random_seed(1)

class DeepQNetwork:
    def __init__(
            self,
            n_actions,
            n_features,
            learning_rate=0.01,
            reward_decay=0.9,
            e_greedy=0.9,
            replace_target_iter=300,
            memory_size=500,
            batch_size=32,
            e_greedy_increment=None,
            output_graph=False,
            e_greedy_init=0.0,
            file_path=None,
    ):
        self.n_actions = n_actions
        self.n_features = n_features
        self.lr = learning_rate
        self.gamma = reward_decay
        self.epsilon_max = e_greedy
        self.replace_target_iter = replace_target_iter
        self.memory_size = memory_size
        self.batch_size = batch_size
        self.epsilon_increment = e_greedy_increment
        self.epsilon = e_greedy_init if e_greedy_increment is not None else self.epsilon_max

        self.learn_step_counter = 0

        self.memory = np.zeros((self.memory_size, n_features * 2 + 2))

        self._build_net()
        t_params = tf.compat.v1.get_collection(tf.compat.v1.GraphKeys.GLOBAL_VARIABLES, scope='target_net')
        e_params = tf.compat.v1.get_collection(tf.compat.v1.GraphKeys.GLOBAL_VARIABLES, scope='eval_net')
        with tf.compat.v1.variable_scope('hard_replacement'):
            self.target_replace_op = [tf.compat.v1.assign(t, e) for t, e in zip(t_params, e_params)]
        self.saver = tf.compat.v1.train.Saver(max_to_keep=1)
        
        self.memory_counter = 0
        self.sess = tf.compat.v1.Session()

        if output_graph:
            tf.summary.FileWriter("logs/", self.sess.graph)

        self.sess.run(tf.compat.v1.global_variables_initializer())
        self.cost_his = []
        if file_path is not None:
            self.saver.restore(self.sess, file_path)

    def _build_net(self):
        # ------------------ all inputs ------------------------
        self.s = tf.compat.v1.placeholder(tf.float32, [None, self.n_features], name='s')  # input State
        self.s_ = tf.compat.v1.placeholder(tf.float32, [None, self.n_features], name='s_')  # input Next State
        self.r = tf.compat.v1.placeholder(tf.float32, [None, ], name='r')  # input Reward
        self.a = tf.compat.v1.placeholder(tf.int32, [None, ], name='a')  # input Action

        w_initializer, b_initializer = tf.random_normal_initializer(0., 0.3), tf.constant_initializer(0.1)

        # ------------------ build evaluate_net ------------------
        with tf.compat.v1.variable_scope('eval_net'):
            e1 = tf.layers.dense(self.s, 512, tf.nn.relu, kernel_initializer=w_initializer,
                                 bias_initializer=b_initializer, name='e1')
            e2 = tf.layers.dense(e1, 512, tf.nn.relu, kernel_initializer=w_initializer,
                                 bias_initializer=b_initializer, name='e2')
            self.q_eval = tf.layers.dense(e2, self.n_actions, kernel_initializer=w_initializer,
                                          bias_initializer=b_initializer, name='q')

        # ------------------ build target_net ------------------
        with tf.compat.v1.variable_scope('target_net'):
            t1 = tf.layers.dense(self.s_, 512, tf.nn.relu, kernel_initializer=w_initializer,
                                 bias_initializer=b_initializer, name='t1')
            t2 = tf.layers.dense(t1, 512, tf.nn.relu, kernel_initializer=w_initializer,
                                 bias_initializer=b_initializer, name='t2')
            self.q_next = tf.layers.dense(t2, self.n_actions, kernel_initializer=w_initializer,
                                          bias_initializer=b_initializer, name='t3')

        with tf.compat.v1.variable_scope('q_target'):
            q_target = self.r + self.gamma * tf.reduce_max(self.q_next, axis=1, name='Qmax_s_')    # shape=(None, )
            self.q_target = tf.stop_gradient(q_target)
        with tf.compat.v1.variable_scope('q_eval'):
            a_indices = tf.stack([tf.range(tf.shape(self.a)[0], dtype=tf.int32), self.a], axis=1)
            self.q_eval_wrt_a = tf.gather_nd(params=self.q_eval, indices=a_indices)    # shape=(None, )
        with tf.compat.v1.variable_scope('loss'):
            self.loss = tf.reduce_mean(tf.math.squared_difference(self.q_target, self.q_eval_wrt_a, name='TD_error'))
        with tf.compat.v1.variable_scope('train'):
            self._train_op = tf.compat.v1.train.RMSPropOptimizer(self.lr).minimize(self.loss)

    def store_transition(self, s, a, r, s_):
        transition = np.hstack((s, [a, r], s_))

        index = self.memory_counter % self.memory_size
        self.memory[index, :] = transition

        self.memory_counter += 1

    def choose_action(self, observation):
        observation = observation[np.newaxis, :]

        if np.random.uniform() < self.epsilon:
            actions_value = self.sess.run(self.q_eval, feed_dict={self.s: observation})
            action = np.argmax(actions_value)
        else:
            action = np.random.randint(0, self.n_actions)
        return action

    def aver_q(self, states):
        sum_q = 0
        for state in states:
            state = state[np.newaxis, :]
            actions_value = self.sess.run(self.q_eval, feed_dict={self.s: state})
            sum_q += max(actions_value[0])
        return sum_q / len(states)

    def learn(self):
        if self.learn_step_counter % self.replace_target_iter == 0:
            self.sess.run(self.target_replace_op)
            print('\ntarget_params_replaced\n')
            print('\nparams all saved\n')

        if self.memory_counter > self.memory_size:
            sample_index = np.random.choice(self.memory_size, size=self.batch_size)
        else:
            sample_index = np.random.choice(self.memory_counter, size=self.batch_size)
        batch_memory = self.memory[sample_index, :]

        _, cost, q_target = self.sess.run(
            [self._train_op, self.loss, self.q_target],
            feed_dict={
                self.s: batch_memory[:, :self.n_features],
                self.a: batch_memory[:, self.n_features],
                self.r: batch_memory[:, self.n_features + 1],
                self.s_: batch_memory[:, -self.n_features:],
            })

        self.cost_his.append(cost)
        print("\n")
        print("Cost_Tag: ", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), self.learn_step_counter, str(cost))
        # increasing epsilon
        self.epsilon = self.epsilon + self.epsilon_increment if self.epsilon < self.epsilon_max else self.epsilon_max
        self.learn_step_counter += 1
