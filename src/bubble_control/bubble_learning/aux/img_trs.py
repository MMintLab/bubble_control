import numpy as np
import torch
import copy
import abc


class BlockDownSamplingBaseTr(abc.ABC):
    def __init__(self, factor_x, factor_y, keys_to_tr=None):
        super().__init__()
        self.factor_x = factor_x
        self.factor_y = factor_y
        self.keys_to_tr = keys_to_tr

    def __call__(self, sample):
        if self.keys_to_tr is None:
            # transform all that has quat in the key
            old_keys = copy.deepcopy(list(sample.keys()))
            for k in old_keys:
                v = sample[k]
                if 'imprint' in k:
                    sample['{}_undownsampled'.format(k)] = v  # store the unsampled one
                    sample[k] = self._tr(v)
        else:
            for key in self.keys_to_tr:
                if key in sample:
                    v = sample[key]
                    sample['{}_undownsampled'.format(key)] = v  # store the unsample one
                    sample[key] = self._tr(sample[key])
        return sample

    def inverse(self, sample):
        # apply the inverse transformation
        if self.keys_to_tr is None:
            # trasform all that has quat in the key
            for k, v in sample.items():
                if 'imprint' in k:
                    sample[k] = sample['{}_undownsampled'.format(k)] # restore the original
        else:
            for key in self.keys_to_tr:
                if key in sample:
                    sample[key] = sample['{}_undownsampled'.format(key)] # restore the original
        return sample

    def _tr(self, x):
        # downsample the image using block mean
        in_shape = x.shape
        size_x, size_y = x.shape[-2], x.shape[-1]
        factor_x = self.factor_x
        factor_y = self.factor_y
        new_size_x = size_x//factor_x
        new_size_y = size_y//factor_y

        x_r = x.reshape(*in_shape[:-2], new_size_x, factor_x, size_y)
        x_rr = x_r.swapaxes(-2, -1).reshape(*in_shape[:-2], new_size_x, factor_x, new_size_y, factor_y)
        x_rrr = x_rr.reshape(*in_shape[:-2], new_size_x, new_size_y, factor_y*factor_x)
        x_down = self._reduction(x_rrr)
        return x_down

    @abc.abstractmethod
    def _reduction(self, x_rrr):
        pass


class BlockMeanDownSamplingTr(BlockDownSamplingBaseTr):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _reduction(self, x_rrr):
        x_down = np.mean(x_rrr, axis=-1)
        return x_down


class BlockMaxDownSamplingTr(BlockDownSamplingBaseTr):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _reduction(self, x_rrr):
        x_down = np.max(x_rrr, axis=-1)
        return x_down


class BlockDownSamplingTr(BlockDownSamplingBaseTr):

    def __init__(self, *args, reduction='mean', **kwargs):
        self.reduction = reduction
        super().__init__(*args, **kwargs)

    def _reduction(self, x_rrr):
        implemented_reductions = ['mean', 'max', 'min']
        if self.reduction == 'mean':
            x_down = np.mean(x_rrr, axis=-1)
        elif self.reduction == 'max':
            x_down = np.max(x_rrr, axis=-1)
        elif self.reduction == 'min':
            x_down = np.min(x_rrr, axis=-1)
        else:
            raise NotImplemented('Reduction {} not yet implemented. Only {} available'.format(implemented_reductions))
        return x_down
