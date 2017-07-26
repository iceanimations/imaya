''' Contains the base class for texture nodes '''


from abc import ABCMeta, abstractproperty, abstractmethod
import pymel.core as pc


from .setdict import SetDict
from .utils import expandPath

__all__ = ['TextureNode']


class TextureNode(object):
    ''' Base class for different types of texture nodes '''

    __metaclass__ = ABCMeta
    __subc__ = []

    @abstractproperty
    def nodeType(self):
        pass

    @abstractproperty
    def pathReadAttr(self):
        pass

    @abstractproperty
    def pathWriteAttr(self):
        pass

    @property
    def node(self):
        return self._node

    def getAuxFiles(self, path):
        return []

    def __init__(self, node):
        node = pc.nt.PyNode(node)
        if node.nodeType() != self.nodeType:
            raise TypeError('node should be of type %s' % self.nodeType)
        self._node = pc.nt.PyNode(node)

    @classmethod
    def create(cls):
        newNode = pc.createNode(cls.nodeType)
        return cls(newNode)

    def getFullPath(self):
        return expandPath(self.getPath())

    def getPath(self):
        if self.pathReadAttr:
            attr = self.node.attr(self.pathReadAttr)
            return attr.get()
        else:
            return NotImplemented

    def setPath(self, val):
        if self.pathWriteAttr:
            attr = self.node.attr(self.pathWriteAttr)
        elif self.pathReadAttr:
            attr = self.node.attr(self.pathReadAttr)
        else:
            return NotImplemented
        attr.set(val)

    def getAllPaths(self):
        return [self.getPath()]

    @abstractmethod
    def collect(self, dest, scene_textures=None):
        pass

    def map_texture(self, mapping):
        reverse = []
        path = self.getPath()
        if path in mapping:
            self.setPath(mapping[path])
            reverse.append(mapping[path], path)
        return reverse

    def get_textures(self, getAuxFiles=True):
        ''':return: SetDict'''
        path = self.getPath()
        paths = self.getAllPaths()
        paths.extend(self.getAuxFiles())
        return SetDict({path: paths})

    @classmethod
    def getAll(cls, selection=False, referenceNodes=False):
        return [cls(node) for node in
                cls.getAllNodes(
                    selection=selection, referenceNodes=referenceNodes)]

    @classmethod
    def getNodes(cls, selection=False, referenceNodes=False):
        return pc.ls(type=cls.nodeType, sl=selection, rn=referenceNodes)
