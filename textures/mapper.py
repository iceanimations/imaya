'''Contains Texture Handler class'''

import os.path as op
import shutil

import iutil

from .setdict import SetDict
from .base import TextureNode


class TextureMapper(object):
    __texture_types__ = []
    _instance = None

    def __init__(self):
        self._file_textures = None
        self._mapping = None
        self._t_nodes

    @classmethod
    def get_texture_types(cls):
        return cls.__texture_types__[:]

    @classmethod
    def register_texture_type(cls, texture_type):
        if not issubclass(texture_type, TextureNode):
            raise TypeError(
                'register_texture_type argument must be derived from '
                'TextureNode')
        cls.__texture_types__.append(texture_type)

    @classmethod
    def unregister_texture_type(cls, texture_type):
        cls.__texture_types__.remove(texture_type)

    def getAll(self, selection=False, referenceNodes=False):
        ''':return: list of TextureNode'''
        t_nodes = []
        for typ in self.get_texture_types():
            t_nodes.extend(typ.getAll(selection=selection,
                                      referenceNodes=referenceNodes))
        return t_nodes

    def getNodes(self, selection=False, referenceNodes=False):
        return [t_node.node for t_node in
                self.getAll(selection=selection,
                            referenceNodes=referenceNodes)]

    def collect_textures(self, dest, texture_files=None):
        ''':type texture_files: SetDict'''
        mapping = {}

        if not op.exists(dest) or not op.isdir(dest):
            raise IOError('%s does not exist or is not a directory' % dest)

        if not texture_files:
            if not self._file_textures:
                texture_files = self.texture_files()
            else:
                texture_files = self._file_textures

        for myftn in texture_files:
            if myftn in mapping:
                continue
            ftns, texs = iutil.find_related_ftns(myftn, texture_files.copy())
            newmappings = iutil.lCUFTN(dest, ftns, texs)
            for fl, copy_to in newmappings.items():
                if op.exists(fl):
                    shutil.copy(fl, copy_to)
            mapping.update(newmappings)

        return mapping

    def texture_files(self, selection=False, key=lambda x: True,
                      getAuxFiles=True, returnAsDict=True):
        '''return all texture files in the scene'''
        file_texs = SetDict()
        t_nodes = self.getAll()

        for t_node in t_nodes:
            t_texs = t_node.get_textures()
            file_texs.update(t_texs)

        self._file_textures = file_texs

        if returnAsDict:
            return file_texs
        else:
            return list(file_texs.reduced())

    @classmethod
    def map_textures(self, mapping=None, selection=False,
                     referenceNodes=False):
        if mapping is None:
            if self._mapping is None:
                raise ValueError('No Mapping was found')
            else:
                mapping = self._mapping

        reverse = []

        for t_node in self.getAll(selection=selection,
                                  referenceNodes=referenceNodes):
            for k, v in t_node.map_texture(mapping):
                reverse[k] = v

        return reverse
