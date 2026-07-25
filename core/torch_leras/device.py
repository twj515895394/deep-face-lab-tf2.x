"""Device management for PyTorch"""

import torch
from core.interact import interact as io


class Device:
    """Single device information"""
    
    def __init__(self, index, name, total_mem_gb):
        self.index = index
        self.name = name
        self.total_mem_gb = total_mem_gb
        self.tf_dev_type = 'GPU'  # For compatibility
    
    def __repr__(self):
        return f"Device({self.index}: {self.name}, {self.total_mem_gb:.1f}GB)"


class Devices:
    """Manage available devices"""
    
    @staticmethod
    def getDevices():
        """Get list of available devices"""
        devices = []
        
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                name = props.name
                total_mem_gb = props.total_memory / (1024**3)
                devices.append(Device(i, name, total_mem_gb))
        
        return devices
    
    @staticmethod
    def get_best_device():
        """Get best available device (most VRAM)"""
        devices = Devices.getDevices()
        if not devices:
            return Device(-1, "CPU", 0)
        
        return max(devices, key=lambda d: d.total_mem_gb)
    
    @staticmethod
    def get_worst_device():
        """Get worst available device (least VRAM)"""
        devices = Devices.getDevices()
        if not devices:
            return Device(-1, "CPU", 0)
        
        return min(devices, key=lambda d: d.total_mem_gb)
    
    @staticmethod
    def get_devices_from_index_list(indexes):
        """Get devices by index list"""
        all_devices = Devices.getDevices()
        return [d for d in all_devices if d.index in indexes]
    
    @staticmethod
    def get_equal_devices(device):
        """Get all devices equal to given device"""
        all_devices = Devices.getDevices()
        return [d for d in all_devices if d.total_mem_gb == device.total_mem_gb]
    
    @staticmethod
    def initialize_main_env():
        """Initialize main environment"""
        if torch.cuda.is_available():
            torch.backends.cudnn.benchmark = True
            torch.backends.cudnn.deterministic = False
