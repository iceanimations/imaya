''' Contains the base class for texture nodes '''


from abc import ABCMeta, abstractmethod

__all__ = ['TextureNode']


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


class TextureNode(object):
    ''' Base class for different types of texture nodes '''
    __metaclass__ = ABCMeta
    __subc__ = []
    node = None
    nodeType = None

    def getPath(self):
        pass

    def renamePath(self):
        pass

    def textureFiles(self, *args, **kwargs):
        pass

    @classmethod
    def getAllNodes(cls):
        for subcls in cls.__subclasses__():
            print subcls

    @classmethod
    def register(cls, subclass):
        cls.__subc__.append(cls)
        ABCMeta.register(cls, subclass)

    def inheritors(cls):
        return cls.__subc__[:]

    @abstractmethod
    def collect(self, dest, scene_textures=None):
        pass

    @abstractmethod
    def map_texture(self, mapping):
        pass
