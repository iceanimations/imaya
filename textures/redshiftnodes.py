'''Contains classes for handling redshift texture nodes'''
import os

import pymel.core as pc

import iutil

from .base import TextureNode
from .setdict import SetDict


__all__ = ['RedshiftSprite', 'RedshiftNormalMap']


class _RedshiftTextureNode(TextureNode):
    _path_read_attr = 'tex0'
    _path_write_attr = 'tex0'

    uv_tiling_modes = ['None', 'zbrush', 'mudbox', 'mari', 'explicit']

    def _get_textures(self):
        path = self.get_path()

        files = []

        if pc.getAttr(self.node + '.useFrameExtension'):
            seqTex = iutil.getSequenceFiles(path)
            if seqTex:
                files.extend(seqTex)

        udim_mode = iutil.detectUdim(path)
        if udim_mode:
            tiles = iutil.getUVTiles(path, udim_mode)
            files.extend(tiles)

        if os.path.exists(path) and os.path.isfile(path):
            files.append(path)

        return files

    def get_aux_files(self, texs=None):
        if texs is None:
            texs = self._get_textures()
        auxs = []
        for tex in texs:
            tex = iutil.getFileByExtension(tex, 'tex')
            if tex:
                auxs.append(tex)
        return auxs

    def get_textures(self, aux=True, key=lambda x: True):
        path = self.get_path()
        files = self._get_textures()
        if aux:
            print self.get_aux_files(files)
            files.extend(self.get_aux_files(files))
        files = [file_ for file_ in files if key(file_)]
        return SetDict({path: files})

    @classmethod
    def get_all(cls, selection=False, reference_nodes=False):
        if not pc.pluginInfo('redshift4maya', q=True, l=True):
            return []
        return super(_RedshiftTextureNode, cls).get_all(
                selection=selection, reference_nodes=reference_nodes)


class RedshiftSprite(_RedshiftTextureNode):
    _node_type = 'RedshiftSprite'


class RedshiftNormalMap(_RedshiftTextureNode):
    _node_type = 'RedshiftNormalMap'
