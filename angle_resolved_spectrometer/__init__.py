'''Control and analysis software for a home-built angle-resolved reflectance spectrometer.'''

from .calibration import MELBOURNE_CALIBRATION
from .instrument import AngleResolvedSpectrometer

__all__ = ['AngleResolvedSpectrometer', 'MELBOURNE_CALIBRATION']
