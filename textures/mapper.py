'''Contains Texture Handler class'''

import os.path as op
import shutil

import iutil

from .setdict import SetDict
from .base import TextureNode


__all__ = ['TextureMapper']


class TextureMapper(object):
    __texture_types__ = []
    _instance = None

    def __init__(self):
        self._file_textures = None
        self._mapping = None

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

    def get_all(self, selection=False, reference_nodes=False):
        ''':return: list of TextureNode'''
        t_nodes = []
        for typ in self.get_texture_types():
            new_t_nodes = typ.get_all(selection=False,
                                      reference_nodes=False)
            t_nodes.extend(new_t_nodes)
        return t_nodes

    def get_nodes(self, selection=False, reference_nodes=False):
        return [t_node.node for t_node in
                self.get_all(selection=selection,
                             reference_nodes=reference_nodes)]

    def collect_textures(self, dest, texture_files=None):
        ''':type texture_files: SetDict'''
        mapping = {}

        if not op.exists(dest) or not op.isdir(dest):
            raise IOError('%s does not exist or is not a directory' % dest)

        if not texture_files:
            texture_files = self.get_texture_files()

        for myftn in texture_files:
            if myftn in mapping:
                continue
            ftns, texs = iutil.find_related_ftns(myftn, texture_files.copy())
            new_mappings = iutil.lCUFTN(dest, ftns, texs)
            for fl, copy_to in new_mappings.items():
                if op.exists(fl):
                    shutil.copy(fl, copy_to)
            mapping.update(new_mappings)

        return mapping

    def get_texture_files(self, selection=False, key=lambda x: True,
                          aux=True, return_as_dict=True):
        '''return all texture files in the scene'''
        file_texs = SetDict()
        t_nodes = self.get_all()

        for t_node in t_nodes:
            t_texs = t_node.get_textures()
            file_texs.update(t_texs)

        self._file_textures = file_texs

        if return_as_dict:
            return file_texs
        else:
            return list(file_texs.reduced())

    def map_textures(self, mapping, selection=False, reference_nodes=False):

        reverse = {}

        for t_node in self.get_all(selection=selection,
                                   reference_nodes=reference_nodes):
            for k, v in t_node.map_texture(mapping):
                reverse[k] = v

        return reverse

    def get_mapping(self, newdir, olddir=None, texture_files=None):
        ''' Calculate a texture mapping dictionary
        :newdir: the path where the textures should be mapped to
        :olddir: the path from where the textures should be mapped from, if an
        argument is not provided then all are mapped to this directory
        :scene_textures: operate only on this dictionary, if an argument is not
        provided all scene textures are mapped
        :return: dictionary with all the mappings
        '''
        if not texture_files:
            if not self._file_textures:
                texture_files = self.get_texture_files()
            else:
                texture_files = self._file_textures

        mapping = {}
        for ftn, texs in texture_files.items():
            alltexs = [ftn] + list(texs)
            for tex in alltexs:
                tex_dir, tex_base = op.split(tex)
                if olddir is None or iutil.paths_equal(tex_dir, olddir):
                    mapping[tex] = op.join(newdir, tex_base)

        return mapping
