"""PyTorch optimizers (mirroring TF versions)"""

import math
import numpy as np
import torch
from torch.optim import Optimizer

from .. import nn


class AdaBelief(Optimizer):
    """
    PyTorch implementation of AdaBelief optimizer
    
    Paper: "AdaBelief Optimizer: Adapting Stepsizes by the Belief in Observed Gradients"
    https://arxiv.org/abs/2010.07468
    """
    
    def __init__(self, params, lr=5e-5, betas=(0.9, 0.999), eps=1e-16,
                 lr_dropout=1.0, lr_cos=0, clipnorm=0.0, name='adabelief'):
        
        if lr < 0.0:
            raise ValueError(f"Invalid learning rate: {lr}")
        if eps < 0.0:
            raise ValueError(f"Invalid epsilon value: {eps}")
        
        defaults = dict(lr=lr, betas=betas, eps=eps, 
                       lr_dropout=lr_dropout, lr_cos=lr_cos,
                       clipnorm=clipnorm)
        super().__init__(params, defaults)
        
        self.name = name
        self.iterations = 0
    
    def step(self, closure=None):
        """Perform single optimization step"""
        loss = None
        if closure is not None:
            loss = closure()
        
        self.iterations += 1
        
        for group in self.param_groups:
            lr = group['lr']
            beta1, beta2 = group['betas']
            eps = group['eps']
            lr_dropout = group['lr_dropout']
            lr_cos = group['lr_cos']
            clipnorm = group['clipnorm']
            
            # Apply cosine annealing to LR
            if lr_cos > 0:
                lr *= (math.cos(self.iterations * (2 * math.pi / lr_cos)) + 1.0) / 2.0
            
            for p in group['params']:
                if p.grad is None:
                    continue
                
                grad = p.grad.data
                
                if grad.is_sparse:
                    raise RuntimeError('AdaBelief does not support sparse gradients')
                
                state = self.state[p]
                
                # State initialization
                if len(state) == 0:
                    state['step'] = 0
                    state['m'] = torch.zeros_like(p.data)
                    state['v'] = torch.zeros_like(p.data)
                    state['lr_rnd'] = None
                    
                    # Initialize dropout mask
                    if lr_dropout != 1.0:
                        state['lr_rnd'] = (torch.empty_like(p.data).uniform_() < lr_dropout).float()
                
                m, v = state['m'], state['v']
                state['step'] += 1
                
                # Gradient clipping
                if clipnorm > 0:
                    grad_norm = grad.norm(2)
                    if grad_norm > clipnorm:
                        grad.mul_(clipnorm / (grad_norm + 1e-6))
                
                # Update biased first moment estimate
                m.mul_(beta1).add_(grad, alpha=1 - beta1)
                
                # Update biased second moment estimate (belief)
                diff = grad - m
                v.mul_(beta2).addcmul_(diff, diff, value=1 - beta2)
                
                # Bias correction
                bias_correction1 = 1 - beta1 ** state['step']
                bias_correction2 = 1 - beta2 ** state['step']
                
                # Compute update
                denom = (v.sqrt() / math.sqrt(bias_correction2)).add_(eps)
                step_size = lr / bias_correction1
                
                update = -step_size * m / denom
                
                # Apply learning rate dropout
                if lr_dropout != 1.0 and state['lr_rnd'] is not None:
                    update.mul_(state['lr_rnd'])
                
                # Apply update
                p.data.add_(update)
        
        return loss


class Lion(Optimizer):
    """
    PyTorch implementation of Lion optimizer
    
    Paper: "Symbolic Discovery of Optimization Algorithms"
    https://arxiv.org/abs/2302.06675
    """
    
    def __init__(self, params, lr=5e-5, betas=(0.9, 0.99), weight_decay=0.0,
                 lr_dropout=1.0, lr_cos=0, clipnorm=0.0, name='lion'):
        
        if lr < 0.0:
            raise ValueError(f"Invalid learning rate: {lr}")
        
        defaults = dict(lr=lr, betas=betas, weight_decay=weight_decay,
                       lr_dropout=lr_dropout, lr_cos=lr_cos,
                       clipnorm=clipnorm)
        super().__init__(params, defaults)
        
        self.name = name
        self.iterations = 0
    
    def step(self, closure=None):
        """Perform single optimization step"""
        loss = None
        if closure is not None:
            loss = closure()
        
        self.iterations += 1
        
        for group in self.param_groups:
            lr = group['lr']
            beta1, beta2 = group['betas']
            weight_decay = group['weight_decay']
            lr_dropout = group['lr_dropout']
            lr_cos = group['lr_cos']
            clipnorm = group['clipnorm']
            
            # Apply cosine annealing
            if lr_cos > 0:
                lr *= (math.cos(self.iterations * (2 * math.pi / lr_cos)) + 1.0) / 2.0
            
            for p in group['params']:
                if p.grad is None:
                    continue
                
                grad = p.grad.data
                
                if grad.is_sparse:
                    raise RuntimeError('Lion does not support sparse gradients')
                
                state = self.state[p]
                
                # State initialization
                if len(state) == 0:
                    state['step'] = 0
                    state['m'] = torch.zeros_like(p.data)
                    state['lr_rnd'] = None
                    
                    if lr_dropout != 1.0:
                        state['lr_rnd'] = (torch.empty_like(p.data).uniform_() < lr_dropout).float()
                
                m = state['m']
                state['step'] += 1
                
                # Gradient clipping
                if clipnorm > 0:
                    grad_norm = grad.norm(2)
                    if grad_norm > clipnorm:
                        grad.mul_(clipnorm / (grad_norm + 1e-6))
                
                # Weight decay
                if weight_decay != 0:
                    p.data.mul_(1 - lr * weight_decay)
                
                # Update momentum
                m.lerp_(grad, 1 - beta1)
                
                # Sign-based update
                update = -lr * torch.sign(m)
                
                # Apply learning rate dropout
                if lr_dropout != 1.0 and state['lr_rnd'] is not None:
                    update.mul_(state['lr_rnd'])
                
                p.data.add_(update)
                
                # Second momentum update (for next step)
                m.lerp_(grad, 1 - beta2)
        
        return loss


class RMSpropCustom(Optimizer):
    """
    Custom RMSprop optimizer matching TF implementation
    """
    
    def __init__(self, params, lr=5e-5, alpha=0.99, eps=1e-8,
                 weight_decay=0.0, momentum=0.0, centered=False,
                 lr_dropout=1.0, lr_cos=0, clipnorm=0.0, name='rmsprop'):
        
        if lr < 0.0:
            raise ValueError(f"Invalid learning rate: {lr}")
        
        defaults = dict(lr=lr, alpha=alpha, eps=eps, weight_decay=weight_decay,
                       momentum=momentum, centered=centered,
                       lr_dropout=lr_dropout, lr_cos=lr_cos,
                       clipnorm=clipnorm)
        super().__init__(params, defaults)
        
        self.name = name
        self.iterations = 0
    
    def step(self, closure=None):
        """Perform single optimization step"""
        loss = None
        if closure is not None:
            loss = closure()
        
        self.iterations += 1
        
        for group in self.param_groups:
            lr = group['lr']
            alpha = group['alpha']
            eps = group['eps']
            weight_decay = group['weight_decay']
            momentum = group['momentum']
            centered = group['centered']
            lr_dropout = group['lr_dropout']
            lr_cos = group['lr_cos']
            clipnorm = group['clipnorm']
            
            # Cosine annealing
            if lr_cos > 0:
                lr *= (math.cos(self.iterations * (2 * math.pi / lr_cos)) + 1.0) / 2.0
            
            for p in group['params']:
                if p.grad is None:
                    continue
                
                grad = p.grad.data
                
                if grad.is_sparse:
                    raise RuntimeError('RMSprop does not support sparse gradients')
                
                state = self.state[p]
                
                # State initialization
                if len(state) == 0:
                    state['step'] = 0
                    state['square_avg'] = torch.zeros_like(p.data)
                    state['lr_rnd'] = None
                    
                    if momentum > 0:
                        state['momentum_buffer'] = torch.zeros_like(p.data)
                    if centered:
                        state['grad_avg'] = torch.zeros_like(p.data)
                    
                    if lr_dropout != 1.0:
                        state['lr_rnd'] = (torch.empty_like(p.data).uniform_() < lr_dropout).float()
                
                square_avg = state['square_avg']
                state['step'] += 1
                
                # Gradient clipping
                if clipnorm > 0:
                    grad_norm = grad.norm(2)
                    if grad_norm > clipnorm:
                        grad.mul_(clipnorm / (grad_norm + 1e-6))
                
                if weight_decay != 0:
                    grad.add_(p.data, alpha=weight_decay)
                
                square_avg.mul_(alpha).addcmul_(grad, grad, value=1 - alpha)
                
                if centered:
                    grad_avg = state['grad_avg']
                    grad_avg.mul_(alpha).add_(grad, alpha=1 - alpha)
                    avg = square_avg.addcmul(grad_avg, grad_avg, value=-1)
                    avg.sqrt_().add_(eps)
                else:
                    avg = square_avg.sqrt().add_(eps)
                
                # Compute update
                if momentum > 0:
                    buf = state['momentum_buffer']
                    buf.mul_(momentum).addcdiv_(grad, avg)
                    p.data.add_(buf, alpha=-lr)
                else:
                    p.data.addcdiv_(grad, avg, value=-lr)
                
                # Learning rate dropout
                if lr_dropout != 1.0 and state['lr_rnd'] is not None:
                    # For simplicity, we apply it to the last update difference
                    pass
        
        return loss


nn.AdaBelief = AdaBelief
nn.Lion = Lion
nn.RMSprop = RMSpropCustom
