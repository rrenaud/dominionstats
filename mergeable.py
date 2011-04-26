
# I't s quite possible that this is too abstract/clever.
class MergeableObjectImpl(object):
    def Merge(self, other):
        access_func = self._AccessFunc
        self_dict = access_func(self)
        for k, v in access_func(other).iteritems():
            if k not in self_dict:
                self_dict[k] = v
            else:
                if hasattr(self_dict[k], 'Merge'):
                    assert hasattr(v, 'Merge')
                    self_dict[k].Merge(v)
                else:
                    assert type(v) == type(self_dict[k])
                    assert type(v) in [int, float], ('%s %s %s' % (
                            v, k, type(v)))
                    self_dict[k] += v
                    

class MergeableObject(MergeableObjectImpl):
    def _AccessFunc(self, other):
        return other.__dict__

class MergeableDict(MergeableObjectImpl):
    def _AccessFunc(self, other):
        return other
