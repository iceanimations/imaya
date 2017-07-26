'''Contains SetDict utility class'''


class SetDict(dict):
    ''' A type of dictionary which can only have sets as its values and update
    performs union on sets
    '''
    def __init__(self, *args, **kwargs):
        super(SetDict, self).__init__(*args, **kwargs)
        for k, v in self.iteritems():
            if not isinstance(v, set):
                self[k] = set(v)

    def __getitem__(self, key):
        if key not in self:
            self[key] = set()
        return super(SetDict, self).__getitem__(key)

    def __setitem__(self, key, val):
        if not isinstance(val, set):
            raise TypeError('value must be a set')
        super(SetDict, self).__setitem__(key, val)

    def get(self, key, *args, **kwargs):
        return self.__getitem__(key)

    def update(self, d):
        if not isinstance(d, SetDict):
            raise TypeError("update argument must be a SetDict")
        for k, v in d.iteritems():
            self[k].update(v)

    def reduced(self):
        '''returns a set which is a union union of all values'''
        return reduce(lambda a, b: a.union(b), self.values(), set())
