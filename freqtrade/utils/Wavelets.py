'''
This class is factory for creating various kinds of Wavelet Transforms with a consistent interface
'''



# -----------------------------------

# base class - to allow generic treatment of all transforms

from abc import ABC, abstractmethod
from enum import Enum

import numpy as np
import pywt
import scipy
from scipy.fft import fft, hfft, ifft, ihfft, rfft, irfft, fftfreq
from scipy.fft import fht, ifht
from modwt import modwt, imodwt, modwtmra

# all actual instantiations follow this base class

class base_wavelet(ABC):

    # the following are used to store info needed across different calls
    wavelet_type = "db2"
    wavelet = None
    mode = "smooth"
    coeff_slices = None
    coeff_shapes = None
    coeff_format = "wavedec"
    data_shape = None
    lookahead = 0

    detrend_data = False
    smooth_data = False
    smooth_window = 4

    def __init__(self):
        super().__init__()

    # function to get transform coefficients  (different for each wavelet type)
    @abstractmethod
    def get_coeffs(self, data: np.array) -> np.array:
        # this is a DWT transform, for reference:
        coeffs = pywt.wavedec(data, self.wavelet, mode=self.mode, level=2)
        return coeffs

    # function to convert coefficients back into a waveform (inverse of get_coeffs)
    @abstractmethod
    def get_values(self, coeffs):
        # series = pywt.waverec(coeffs, self.wavelet)

        series = pywt.waverec(coeffs, wavelet=self.wavelet, mode=self.mode)
        # print(f'    coeff_slices:{self.coeff_slices}, coeff_shapes:{self.coeff_shapes} series:{np.shape(series)}')

        return series

    # convert wavelet coefficints to 1d numpy array. This works for several variants
    def coeff_to_array(self, coeffs):
        # flatten the coefficient arrays

        # more general purpose (can use with many waveforms)
        array, self.coeff_slices = pywt.coeffs_to_array(coeffs)

        # re-trend
        if self.detrend_data:
            array = retrend(np.array(array))

        # print(f'    coeff_to_array: array:{np.shape(array)}')
        return np.array(array)

    # convert 1d numpy array back to wavelet coefficient format. This works for several variants
    def array_to_coeff(self, array):

        # more general purpose (can use with many waveforms)
        coeffs = pywt.array_to_coeffs(array, self.coeff_slices, output_format=self.coeff_format)

        # print(f'    coeff_slices:{self.coeff_slices}, coeff_shapes:{self.coeff_shapes} array:{np.shape(array)}')
        # print(f'    array_to_coeff:  array:{np.shape(array)}')
        return coeffs


    # set lookahead value (for detrending). Only need to do this if you are projecting ahead
    def set_lookahead(self, lookahead):
        self.lookahead = lookahead
        return

    # function to specify whether or not to detrend data before training/forecasting
    def set_detrend(self, detrend_flag=True):
        self.detrend_data = detrend_flag
        return

    # function to specify whether or not to smooth data before training/forecasting
    def set_smooth(self, smooth_flag=True, smooth_window=4):
        self.smooth_data = smooth_flag
        self.smooth_window = smooth_window
        return

# -----------------------------------
# de-trend and re-trend data
# currently only works for 1d, and detrend/retrend must be paired, i.e. cannot call detrend() multiple times then expect to retrend

trend_line = None


def detrend(x, axis=0):
    global trend_line
    x = np.nan_to_num(x)
    n = x.size

    t = np.arange(0, len(x))
    trend_poly = np.polyfit(t, x, 1)
    trend_line = np.polyval(trend_poly, x)
    x_notrend = x - trend_line

    return x_notrend


def retrend(x_trend, axis=0):
    global trend_line
    return x_trend + trend_line

# -----------------------------------

def smooth(y, window):
    box = np.ones(window) / window
    y_smooth = np.convolve(y, box, mode="same")
    # Hack: constrain to 3 decimal places (should be elsewhere, but convenient here)
    y_smooth = np.round(y_smooth, decimals=3)
    return np.nan_to_num(y_smooth)


# -----------------------------------

# DWT - Discrete Wavelet Transform

class dwt_wavelet(base_wavelet):

    def get_coeffs(self, data: np.array) -> np.array:

        x = data

        # de-trend
        if self.detrend_data:
            x = detrend(x)

        # get the DWT coefficients
        self.wavelet_type = 'bior3.9'
        self.wavelet = pywt.Wavelet(self.wavelet_type)
        self.mode = 'symmetric'
        self.coeff_format = "wavedec"
        level = 2
        coeffs = pywt.wavedec(x, self.wavelet, mode=self.mode, level=level)

        # print(f'    wavelet.dec_len:{self.wavelet.dec_len}  wavelet.rec_len:{self.wavelet.rec_len}')

        '''
        # remove higher harmonics
        std = np.std(coeffs[level])
        sigma = (1 / 0.6745) * self.madev(coeffs[-level])
        # sigma = madev(coeff[-level])
        uthresh = sigma * np.sqrt(2 * np.log(length))

        coeffs[1:] = (pywt.threshold(i, value=uthresh, mode='hard') for i in coeffs[1:])

        '''

        # print(f'  get_coeffs() coeffs:')
        # for arr in coeffs:
        #     print(f'  {np.shape(arr)}')

        return coeffs

    def get_values(self, coeffs):

        series = pywt.waverec(coeffs, wavelet=self.wavelet, mode=self.mode)

        # print(f'    coeffs:{np.shape(coeffs)}, series:{np.shape(series)}')

        return series

    def coeff_to_array(self, coeffs):
        array = super().coeff_to_array(coeffs)
        # print(f'  coeff_to_array() {np.shape(array)}')

        return array

    def array_to_coeff(self, array):

        # print(f'  array_to_coeff() {np.shape(array)}')
        coeffs = super().array_to_coeff(array)
        return coeffs

# -----------------------------------

# DWT - Discrete Wavelet Transform, Approximate Coefficients only

class dwta_wavelet(base_wavelet):

    def get_coeffs(self, data: np.array) -> np.array:

        x = data

        # de-trend
        if self.detrend_data:
            x = detrend(x)

        # get the DWT coefficients
        self.wavelet_type = 'bior3.9'
        self.wavelet = pywt.Wavelet(self.wavelet_type)
        self.mode = 'symmetric'
        self.coeff_format = "wavedec"
        level = 2
        coeffs = pywt.wavedec(x, self.wavelet, mode=self.mode, level=level)

        # print(f'    wavelet.dec_len:{self.wavelet.dec_len}  wavelet.rec_len:{self.wavelet.rec_len}')


        # set detailed coeffs to zero (they still need to be there though)
        threshold = 0.001
        # coeffs[1:] = [pywt.threshold(c, value=threshold, mode='hard') for c in coeffs[1:]]
        # coeffs[1:] = [pywt.threshold(c, value=threshold, mode='soft') for c in coeffs[1:]]
        coeffs[1:] = [pywt.threshold(c, value=threshold, mode='garotte') for c in coeffs[1:]]

        return coeffs

    def get_values(self, coeffs):
        # series = pywt.waverec(coeffs, self.wavelet)

        # print(f'  get_values() coeffs:')
        # for arr in coeffs:
        #     print(f'  {np.shape(arr)}')
        series = pywt.waverec(coeffs, wavelet=self.wavelet, mode=self.mode)

        # print(f'    coeffs:{np.shape(coeffs)}, series:{np.shape(series)}')

        return series

    def coeff_to_array(self, coeffs):
        array = np.array(coeffs[0])
        self.save_coeffs = coeffs

        # re-trend
        if self.detrend_data:
            array = retrend(array)

        return array

    def array_to_coeff(self, array):
        coeffs = self.save_coeffs
        coeffs[0] = array
        return coeffs

# -----------------------------------

# FFT - Fast Fourier Transform

class fft_wavelet(base_wavelet):
    def get_coeffs(self, data: np.array) -> np.array:

        x = data

        # de-trend
        if self.detrend_data:
            x = detrend(x)

        # freqs = rfft(x)
        freqs = fft(x)

        # # filter out higher harmonics
        # n_param = int(len(freqs) / 2) + 1
        # h=np.sort(freqs)[-n_param]
        # freqs=[ freqs[i] if np.absolute(freqs[i])>=h else 0 for i in range(len(freqs)) ]

        # deal with complex results
        r_coeffs = np.real(freqs)
        i_coeffs = np.imag(freqs)
        coeffs = np.concatenate([r_coeffs, i_coeffs])

        self.data_shape = np.shape(coeffs)
        # print(f'    fft data_shape:{self.data_shape}')

        return coeffs

    def get_values(self, coeffs):
        # reconstruct the data
        # series = irfft(coeffs)
        series = ifft(coeffs)

        return series.real

    def coeff_to_array(self, coeffs):

        array = np.ravel(coeffs)

        # re-trend
        if self.detrend_data:
            array = retrend(np.array(array))

        return array

    def array_to_coeff(self, array):
        # coeffs = np.reshape(array, self.data_shape)
        coeffs = np.array(array)

        # print(f'    coeffs data_shape:{np.shape(coeffs)}')
        # convert back to complex numbers
        split = int(len(array) / 2)
        r_coeffs = np.array(array[:split])
        i_coeffs = np.array(array[split:])
        coeffs = np.vectorize(complex)(r_coeffs, i_coeffs)
        return coeffs

# -----------------------------------

# HFFT - Hermitian Fast Fourier Transform

class hfft_wavelet(base_wavelet):
    def get_coeffs(self, data: np.array) -> np.array:

        x = data

        # de-trend
        if self.detrend_data:
            x = detrend(x)

        coeffs = hfft(x)

        self.data_shape = np.shape(coeffs)

        return coeffs

    def get_values(self, coeffs):
        # reconstruct the data
        series = ihfft(coeffs)

        series = np.abs(series)

        return series

    def coeff_to_array(self, coeffs):

        array = np.ravel(coeffs)

        # re-trend
        if self.detrend_data:
            array = retrend(np.array(array))

        return array

    def array_to_coeff(self, array):
        coeffs = np.reshape(array, self.data_shape)
        return coeffs

# -----------------------------------

# FHT - Fast Hankel Transform

dln = None
class fht_wavelet(base_wavelet):
    def get_coeffs(self, data: np.array) -> np.array:

        x = data

        # de-trend
        if self.detrend_data:
            x = detrend(x)

        # compute the fht
        self.dln = np.log(x[1]/x[0]) 
        coeffs = fht(x, mu=0.0, dln=self.dln)

        return coeffs

    def get_values(self, coeffs):
        series = ifht(coeffs, dln=self.dln, mu=0)

        return series

    def coeff_to_array(self, coeffs):
        self.data_shape = np.shape(coeffs)
        array = coeffs.flatten()

        # re-trend
        if self.detrend_data:
            array = retrend(array)

        return array
        return arra

    def array_to_coeff(self, array):
        series = array.reshape(self.data_shape)
        return series

# -----------------------------------

# MODWT - Maximal Overlap Discrete Wavelet Transform

class modwt_wavelet(base_wavelet):
    def get_coeffs(self, data: np.array) -> np.array:

        x = data

        # de-trend
        if self.detrend_data:
            x = detrend(x)

        # # data must be of even length, so trim if necessary
        # if (len(x) % 2) != 0:
        #     x = x[1:]

        # get the coefficients
        # self.wavelet = 'db8'
        self.wavelet = 'haar'
        # self.wavelet = 'bior3.9' # does not work well with MODWT
        level = 5
        coeffs = modwt(x, self.wavelet, level)
        return coeffs

    def get_values(self, coeffs):
        series = imodwt(coeffs, self.wavelet)

        return series

    def coeff_to_array(self, coeffs):
        array = coeffs.flatten()
        self.data_shape = np.shape(coeffs)

        # re-trend
        if self.detrend_data:
            array = retrend(array)

        return array

    def array_to_coeff(self, array):
        series = array.reshape(self.data_shape)
        return series

# -----------------------------------

# SWT - Standing Wave Transform

class swt_wavelet(base_wavelet):
    def get_coeffs(self, data: np.array) -> np.array:

        x = data

        # de-trend
        if self.detrend_data:
            x = detrend(x)

        # data must be of even length, so trim if necessary
        if (len(x) % 2) != 0:
            x = x[1:]

        self.wavelet = 'bior3.9'
        self.coeff_format = "wavedec"

        # (cA2, cD2), (cA1, cD1) = pywt.swt(data, wavelet, level=2)
        # swt returns an array, with each element being 2 arrays - cA_n and cD_n, where n is the level
        levels = min(2, pywt.swt_max_level(len(x)))
        coeffs = pywt.swt(x, self.wavelet, level=levels, trim_approx=True)
        return coeffs

    def get_values(self, coeffs):
        series = pywt.iswt(coeffs, wavelet=self.wavelet)

        return series

    def coeff_to_array(self, coeffs):
        return super().coeff_to_array(coeffs)

    def array_to_coeff(self, array):
        return super().array_to_coeff(array)

# -----------------------------------

# SWT - Standing Wave Transform, Approximate coefficients only

class swta_wavelet(base_wavelet):
    def get_coeffs(self, data: np.array) -> np.array:

        x = data

        # de-trend
        if self.detrend_data:
            x = detrend(x)

        # data must be of even length, so trim if necessary
        if (len(x) % 2) != 0:
            x = x[1:]

        self.wavelet = 'bior3.9'
        self.coeff_format = "wavedec"

        # (cA2, cD2), (cA1, cD1) = pywt.swt(data, wavelet, level=2)
        # swt returns an array, with each element being 2 arrays - cA_n and cD_n, where n is the level
        levels = min(3, pywt.swt_max_level(len(x)))
        coeffs = pywt.swt(x, self.wavelet, level=levels, trim_approx=True)

        print(f'pywt.__version__: {pywt.__version__}')
        print (f'coeffs:{coeffs}')

        # Zero out the detail coefficients
        coeffs0 = [coeffs[0]] + [np.zeros_like(cD) for cD in coeffs[1:]]

        return coeffs0

    def get_values(self, coeffs):
        series = pywt.iswt(coeffs, wavelet=self.wavelet)

        return series

    def coeff_to_array(self, coeffs):
        return super().coeff_to_array(coeffs)

    def array_to_coeff(self, array):
        return super().array_to_coeff(array)

# -----------------------------------

# WPT - Wavelet Packet Transform

wp = None
nodes = None

class wpt_wavelet(base_wavelet):
    def get_coeffs(self, data: np.array) -> np.array:

        x = data

        # de-trend
        if self.detrend_data:
            x = detrend(x)

        # # data must be of even length, so trim if necessary
        # if (len(x) % 2) != 0:
        #     x = x[1:]

        self.wavelet = 'bior3.9'
        self.coeff_format = "wavedec"

        level = 1

        self.wp = pywt.WaveletPacket(data=x, wavelet=self.wavelet,  maxlevel=level, mode='symmetric')

        self.nodes = self.wp.get_level(level, 'natural')
        coeffs = self.nodes
        return coeffs

    def get_values(self, coeffs):
        # set the coefficients of the nodes at level 2
        for node, chunk in zip(self.nodes, coeffs):
            node.data = chunk

        series = self.wp.reconstruct(update=True)

        return series

    def coeff_to_array(self, coeffs):
        array = np.concatenate([coeff.data for coeff in coeffs])

        # re-trend
        if self.detrend_data:
            array = retrend(array)

        return array

    def array_to_coeff(self, array):
        coeffs = np.array_split(array, len(self.nodes))
        return coeffs

# -----------------------------------


# enum of all available wavelet types

class WaveletType(Enum):
    DWT = dwt_wavelet
    DWTA = dwta_wavelet
    FFT = fft_wavelet
    HFFT = hfft_wavelet
    FHT = fht_wavelet
    MODWT = modwt_wavelet
    SWT = swt_wavelet
    SWTA = swta_wavelet
    WPT = wpt_wavelet


def make_wavelet(wavelet_type: WaveletType) -> base_wavelet:
    return wavelet_type.value()

# -----------------------------------
