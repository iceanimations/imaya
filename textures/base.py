''' Contains the base class for texture nodes '''


from abc import ABCMeta, abstractproperty
import pymel.core as pc


from .setdict import SetDict
from .utils import expand_path

__all__ = ['TextureNode']


class TextureNode(object):
    ''' Base class for different types of texture nodes '''

    __metaclass__ = ABCMeta
    __subc__ = []

    @abstractproperty
    def _node_type(self):
        return ''

    @abstractproperty
    def _path_read_attr(self):
        return None

    @abstractproperty
    def _path_write_attr(self):
        return None

    @property
    def node(self):
        return self._node

    def get_aux_files(self):
        return []

    def __init__(self, node):
        node = pc.PyNode(node)
        if node.nodeType() != self._node_type:
            raise TypeError('node should be of type %s' % self._node_type)
        self._node = node

    @classmethod
    def create(cls):
        newNode = pc.createNode(cls._node_type)
        return cls(newNode)

    def get_full_path(self):
        return expand_path(self.get_path())

    def get_path(self):
        if self._path_read_attr:
            attr = self.node.attr(self._path_read_attr)
            return expand_path(attr.get())
        else:
            raise NotImplementedError

    def set_path(self, val):
        if self._path_write_attr:
            attr = self.node.attr(self._path_write_attr)
        elif self._path_read_attr:
            attr = self.node.attr(self._path_read_attr)
        else:
            raise NotImplementedError
        attr.set(val)

    def get_all_paths(self):
        return [self.get_path()]

    def map_texture(self, mapping):
        reverse = []
        path = self.get_path()
        mapping
        if path in mapping:
            self.set_path(mapping[path])
            reverse.append((mapping[path], path))
        return reverse

    def get_textures(self, aux=True, key=lambda x: True):
        ''':return: SetDict'''
        path = self.get_path()
        paths = self.get_all_paths()
        if aux:
            paths.extend(self.get_aux_files())
        paths = [_path for _path in paths if key(_path)]
        return SetDict({path: paths})

    @classmethod
    def get_all(cls, selection=False, reference_nodes=False):
        return [cls(node) for node in
                cls.get_nodes(
                    selection=selection, reference_nodes=reference_nodes)]

    @classmethod
    def get_nodes(cls, selection=False, reference_nodes=False):
        return pc.ls(type=cls._node_type, sl=selection, rn=reference_nodes)
