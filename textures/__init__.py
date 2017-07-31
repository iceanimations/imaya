import os.path as op
import pymel.core as pc

import iutil as util

from .setdict import *
from .base import *
from .mapper import *
from .filenode import *
from .redshiftnodes import *
from .utils import *


TextureMapper.register_texture_type(FileNode)
TextureMapper.register_texture_type(RedshiftSprite)
TextureMapper.register_texture_type(RedshiftNormalMap)
TextureMapper.register_texture_type(RedshiftDisplacement)
_mapper = TextureMapper()


def textureFiles(selection=False, key=lambda x: True, getTxFiles=True,
                 returnAsDict=False):
    '''Collect texturefile paths from the scene'''
    return _mapper.get_texture_files(selection=selection, key=key,
                                     aux=getTxFiles,
                                     return_as_dict=returnAsDict)


def get_nodes(selection=False, rn=False):
    _mapper.get_nodes(selection=selection, reference_nodes=rn)


def texture_mapping(newdir, olddir=None, scene_textures=None):
    ''' Calculate a texture mapping dictionary
    :newdir: the path where the textures should be mapped to
    :olddir: the path from where the textures should be mapped from, if an
    argument is not provided then all are mapped to this directory
    :scene_textures: operate only on this dictionary, if an argument is not
    provided all scene textures are mapped
    :return: dictionary with all the mappings
    '''
    return _mapper.get_mapping(newdir, olddir=olddir,
                               texture_files=scene_textures)


def collect_textures(dest, scene_textures=None):
    '''
    Collect all scene texturefiles to a flat hierarchy in a single directory
    while resolving nameclashes

    @return: {ftn: tmp}
    '''
    return _mapper.collect_textures(dest, texture_files=scene_textures)


def map_textures(mapping, selection=False, rn=True):
    return _mapper.map_textures(mapping, selection=selection,
                                reference_nodes=rn)
