"""Base classes for PyTorch layers"""

import torch
import torch.nn as nn_torch
import pickle
from pathlib import Path

from .. import nn


class Saveable:
    """Base class for saveable objects"""
    
    def save_weights(self, filename):
        """Save weights to file"""
        weights = self.get_weights_dict()
        
        # Convert tensors to numpy
        numpy_weights = {}
        for k, v in weights.items():
            if isinstance(v, torch.Tensor):
                numpy_weights[k] = v.detach().cpu().numpy()
            else:
                numpy_weights[k] = v
        
        with open(filename, 'wb') as f:
            pickle.dump(numpy_weights, f)
    
    def load_weights(self, filename, force=False):
        """Load weights from file"""
        path = Path(filename)
        if not path.exists():
            return False
        
        try:
            with open(filename, 'rb') as f:
                weights = pickle.load(f)
            
            self.set_weights_dict(weights)
            return True
        except Exception as e:
            print(f"Warning: Failed to load weights from {filename}: {e}")
            return False
    
    def get_weights_dict(self):
        """Get all weights as dict (override in subclasses)"""
        return {}
    
    def set_weights_dict(self, weights):
        """Set weights from dict (override in subclasses)"""
        pass
    
    def init_weights(self):
        """Initialize weights (override in subclasses)"""
        pass


class LayerBase(Saveable, nn_torch.Module):
    """Base class for all layers"""
    
    def __init__(self, name=None, **kwargs):
        super().__init__()
        self.name = name or self.__class__.__name__
        self._built = False
    
    def build_weights(self):
        """Build layer weights (called once)"""
        pass
    
    def forward(self, *args, **kwargs):
        """Forward pass (override in subclasses)"""
        raise NotImplementedError
    
    def __call__(self, *args, **kwargs):
        return self.forward(*args, **kwargs)
    
    def get_weights(self):
        """Get list of trainable variables"""
        return list(self.parameters())
    
    def get_weights_dict(self):
        """Get weights as dictionary"""
        weights = {}
        for name, param in self.named_parameters():
            if param is not None:
                weights[f"{self.name}/{name}"] = param.data
        for name, buf in self.named_buffers():
            if buf is not None:
                weights[f"{self.name}/{name}"] = buf.data
        return weights
    
    def set_weights_dict(self, weights):
        """Set weights from dictionary"""
        own_state = self.state_dict()
        for name, param in self.named_parameters():
            key = f"{self.name}/{name}"
            if key in weights:
                w = weights[key]
                if isinstance(w, type(param.data)):
                    own_state[name].copy_(w)
                elif hasattr(w, 'shape'):
                    import numpy as np
                    if isinstance(w, np.ndarray):
                        w = torch.from_numpy(w)
                    own_state[name].copy_(w)
        self.load_state_dict(own_state)
    
    def init_weights(self):
        """Initialize weights with default initialization"""
        for m in self.modules():
            if isinstance(m, nn_torch.Conv2d):
                nn_torch.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='leaky_relu')
                if m.bias is not None:
                    nn_torch.init.zeros_(m.bias)
            elif isinstance(m, nn_torch.Linear):
                nn_torch.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn_torch.init.zeros_(m.bias)


class ModelBase(LayerBase):
    """Base class for models composed of layers"""
    
    def __init__(self, name=None, **kwargs):
        super().__init__(name=name, **kwargs)
        self._submodels = []
    
    def add_submodel(self, model):
        """Add a submodel"""
        self._submodels.append(model)
        setattr(self, model.name or id(model), model)
    
    def get_out_ch(self):
        """Get output channels (override in subclasses)"""
        raise NotImplementedError
    
    def get_out_res(self, res):
        """Get output resolution (override in subclasses)"""
        return res


nn.LayerBase = LayerBase
nn.ModelBase = ModelBase
nn.Saveable = Saveable
