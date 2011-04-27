#!/usr/bin/python
# -*- coding: utf-8 -*-

import primitive_util
import mergeable

class MeanVarStat(primitive_util.PrimitiveConversion, 
                  mergeable.MergeableObject):
    __slots__ = ('freq', 'sum', 'sum_sq')
    
    def __init__(self):
        self.freq = 0
        self.sum = 0.0
        self.sum_sq = 0.0

    def AddOutcome(self, val):
        self.freq += 1
        self.sum += val
        self.sum_sq += val * val

    def Frequency(self):
        return self.freq

    def Mean(self):
        return (self.sum + 2) / (self.freq + 2)

    def Variance(self):
        if self.freq <= 1:
            return 1e10
        return (((self.sum_sq + 4) - ((self.sum + 2) ** 2) / (self.freq + 2)) /
                (self.freq + 1))

    def StdDev(self):
        return self.Variance() ** .5
 
    def SampleStdDev(self):
        return (self.Variance() / (self.freq + 2)) ** .5

    def __add__(self, o):
        ret = MeanVarStat()
        ret.freq = self.freq + o.freq
        ret.sum = self.sum + o.sum
        ret.sum_sq = self.sum_sq + o.sum_sq
        return ret
    
    def __sub__(self, o):
        ret = MeanVarStat()
        ret.freq = self.freq - o.freq
        ret.sum = self.sum - o.sum
        ret.sum_sq = self.sum_sq - o.sum_sq
        return ret

    def meanDiff(self, o):
        return DiffStat(self, o)

    def RenderInterval(self, factor=2, sig_digits=2):
        if self.SampleStdDev() >= 10000:
            return u'-'
        return u'%.2f ± %.2f' % (self.Mean(), factor * self.SampleStdDev())

    def __eq__(self, o):
        assert type(o) == MeanVarStat
        return (self.freq == o.freq and 
                self.sum == o.sum and
                self.sum_sq == o.sum_sq)

    def to_primitive_object(self):
        return [self.freq, self.sum, self.sum_sq]

    def from_primitive_object(self, obj):
        if type(obj) == list:
            self.freq, self.sum, self.sum_sq = obj
        elif type(obj) == dict:
            self.__dict__ = obj
        else:
            assert 'Confused by obj %s' % str(obj) and False

    def __str__(self):
        return '%s, %s, %s' % (self.freq, self.sum, self.sum_sq)

class DiffStat(object):
    """
    Statistics about the difference in means of two distributions.
    """
    def __init__(self, mvs1, mvs2):
        self.mvs1 = mvs1
        self.mvs2 = mvs2

    @property
    def freq(self):
        return self.mvs1.freq

    def render_interval(self, factor=2, sig_digits=2):
        if self.sample_std_dev() >= 10000:
            return u'-'
        return u'%.2f ± %.2f' % (self.mean(), factor * self.sample_std_dev())
        
    def render_std_devs(self):
        if not self.freq:
            return u'-'
        return u'%.2f' % (self.mean() / self.sample_std_dev())

    def mean(self):
        return self.mvs1.mean() - self.mvs2.mean()

    def sample_std_dev(self):
        return (self.mvs1.sample_std_dev() ** 2 + self.mvs2.sample_std_dev() ** 2) ** 0.5

    def mean_diff(self, o):
        return DiffStat(self, o)

