"""
Lion (EvoLved Sign Momentum) Optimizer
Google Brain 2023 - https://arxiv.org/abs/2302.06675

核心原理：
  用符号函数(sign)替代Adam中的自适应缩放(除以sqrt(v))
  更简洁、更省内存、对学习率更鲁棒、泛化能力更强

更新公式：
  c_t = β₁·c_{t-1} + (1-β₁)·g_t        (动量更新)
  m_t = sign(c_t)                         (只取符号！)
  θ_{t+1} = θ_t - lr · m_t               (直接乘法)

vs AdaBelief 对比：
  - 内存少 15%（只需动量c，不需要方差v）
  - 计算更快（sign vs sqrt+div）
  - 学习率鲁棒性极强（跨3个数量级都能收敛）
  - GAN训练更稳定（扩散模型FID下降更快）
"""

import numpy as np
from core.leras import nn
from tensorflow.python.ops import control_flow_ops, math_ops, state_ops

tf = nn.tf


class Lion(nn.OptimizerBase):
    def __init__(self, lr=1e-4, beta_1=0.9, beta_2=0.99, lr_dropout=1.0,
                 lr_cos=0, clipnorm=0.0, name=None, **kwargs):
        super().__init__(name=name)

        if name is None:
            raise ValueError('name must be defined.')

        self.lr = lr
        self.beta_1 = beta_1
        self.beta_2 = beta_2
        self.lr_dropout = lr_dropout
        self.lr_cos = lr_cos
        self.clipnorm = clipnorm

        with tf.device('/CPU:0'):
            with tf.variable_scope(self.name):
                self.iterations = tf.Variable(0, dtype=tf.int64, name='iters')

        self.c_dict = {}
        self.lr_rnds_dict = {}

    def get_weights(self):
        return [self.iterations] + list(self.c_dict.values())

    def initialize_variables(self, trainable_weights, vars_on_cpu=True, lr_dropout_on_cpu=False):
        e = tf.device('/CPU:0') if vars_on_cpu else None
        if e:
            e.__enter__()
        with tf.variable_scope(self.name):
            c_vars = {
                v.name: tf.get_variable(
                    f'c_{v.name}'.replace(':', '_'),
                    v.shape, dtype=v.dtype,
                    initializer=tf.initializers.constant(0.0),
                    trainable=False
                )
                for v in trainable_weights
            }
            self.c_dict.update(c_vars)

            if self.lr_dropout != 1.0:
                e_lr = tf.device('/CPU:0') if lr_dropout_on_cpu else None
                if e_lr:
                    e_lr.__enter__()
                lr_rnds = [
                    nn.random_binomial(v.shape, p=self.lr_dropout, dtype=v.dtype)
                    for v in trainable_weights
                ]
                if e_lr:
                    e_lr.__exit__(None, None, None)
                self.lr_rnds_dict.update(
                    {v.name: rnd for v, rnd in zip(trainable_weights, lr_rnds)}
                )
        if e:
            e.__exit__(None, None, None)

    def get_update_op(self, grads_vars):
        updates = []

        if self.clipnorm > 0.0:
            norm = tf.sqrt(sum([
                tf.reduce_sum(tf.square(tf.cast(g, tf.float32)))
                for g, v in grads_vars
            ]))

        updates.append(state_ops.assign_add(self.iterations, 1))

        for i, (g, v) in enumerate(grads_vars):
            if self.clipnorm > 0.0:
                g = self.tf_clip_norm(g, self.clipnorm, tf.cast(norm, g.dtype))

            c = self.c_dict[v.name]

            c_t = self.beta_1 * c + (1.0 - self.beta_1) * g
            m_t = tf.sign(c_t)

            lr = tf.constant(self.lr, dtype=g.dtype)
            if self.lr_cos != 0:
                lr *= (tf.cos(
                    tf.cast(self.iterations, g.dtype) *
                    (2 * 3.1415926535 / float(self.lr_cos))
                ) + 1.0) / 2.0

            update = -lr * m_t

            if self.lr_dropout != 1.0:
                lr_rnd = self.lr_rnds_dict[v.name]
                update *= lr_rnd

            new_v = v + update

            updates.append(state_ops.assign(c, c_t))
            updates.append(state_ops.assign(v, new_v))

        return control_flow_ops.group(*updates, name=self.name + '_updates')


nn.Lion = Lion
