'''Contains implementation of FileNode class'''

import os.path as op

import pymel.core as pc

import iutil

from .setdict import SetDict
from .base import TextureNode
from .utils import read_full_path_from_attribute


__all__ = ['FileNode', 'renameFileNodePath', 'getFullpathFromAttr',
           'createFileNodes', 'getFileNodes']


class FileNode(TextureNode):
    _node_type = 'file'
    _path_read_attr = 'cfnp'
    _path_write_attr = 'ftn'

    uv_tiling_modes = ['None', 'zbrush', 'mudbox', 'mari', 'explicit']

    @classmethod
    def create(cls, path, place='2d'):
        '''creates a file node with its '''
        file_node = pc.shadingNode(cls.nodeType, asTexture=True)
        file_node.attr('ftn').set(path)

        if place == '2d':
            place_node = pc.shadingNode('place2dTexture', asUtility=True)

            place_node.coverage >> file_node.coverage
            place_node.translateFrame >> file_node.translateFrame
            place_node.rotateFrame >> file_node.rotateFrame
            place_node.mirrorU >> file_node.mirrorU
            place_node.mirrorV >> file_node.mirrorV
            place_node.stagger >> file_node.stagger
            place_node.wrapU >> file_node.wrapU
            place_node.wrapV >> file_node.wrapV
            place_node.repeatUV >> file_node.repeatUV
            place_node.offset >> file_node.offset
            place_node.rotateUV >> file_node.rotateUV
            place_node.noiseUV >> file_node.noiseUV
            place_node.vertexUvOne >> file_node.vertexUvOne
            place_node.vertexUvTwo >> file_node.vertexUvTwo
            place_node.vertexUvThree >> file_node.vertexUvThree
            place_node.vertexCameraOne >> file_node.vertexCameraOne
            place_node.outUV >> file_node.uv
            place_node.outUvFilterSize >> file_node.uvFilterSize

        return cls(file_node)

    def _get_textures(self):
        texs = SetDict()

        filepath = read_full_path_from_attribute(self.node + '.ftn')
        uv_tiling_mode = self.uv_tiling_modes[0]

        # New in Maya 2015
        if pc.attributeQuery('uvTilingMode', node=self.node, exists=True):
            uv_tiling_mode = self.uv_tiling_modes[pc.getAttr(self.node +
                                                  '.uvt')]

        # still attempt to resolve using tokens in string
        if uv_tiling_mode == 'None':
            uv_tiling_mode = str(iutil.detectUdim(filepath))
        elif not uv_tiling_mode == 'explicit':
            filepath = read_full_path_from_attribute(self.node + '.cfnp')

        # definitely no udim
        if uv_tiling_mode == 'None':
            texs[filepath].add(filepath)
            if pc.getAttr(self.node + '.useFrameExtension'):
                seqTex = iutil.getSequenceFiles(filepath)
                if seqTex:
                    texs[filepath].update(seqTex)

        # explicit naming
        elif uv_tiling_mode == 'explicit':
            # if key(filepath) and op.exists(filepath) and op.isfile(filepath):
            texs[filepath].add(filepath)
            indices = pc.getAttr(self.node + '.euvt', mi=True)
            for index in indices:
                filepath = read_full_path_from_attribute(
                        self.node + '.euvt[%d].eutn' % index)
                texs[filepath].add(filepath)

        else:  # 'mari', 'zbrush', 'mudbox'
            texs[filepath].update(iutil.getUVTiles(filepath, uv_tiling_mode))

        return texs

    def get_all_paths(self, texs=None):
        if texs is None:
            texs = self._get_textures()
        return texs.keys()

    def get_aux_files(self, tx_files=True, tex_files=True, texs=None):
        if texs is None:
            texs = self._get_textures()

        auxs = SetDict()
        for k, files in texs.items():
            aux_files = []
            for file_ in files:
                if tx_files:
                    tx = iutil.getFileByExtension(file_, ext='tx')
                    if tx:
                        aux_files.append(tx)
                if tex_files:
                    tex = iutil.getFileByExtension(file_, ext='tex')
                    if tex:
                        aux_files.append(tex)
            auxs[k].update(aux_files)

        return auxs

    def get_textures(self, key=lambda _op: True, aux=True, tx=True, tex=True):
        texs = self._get_textures()

        if aux:
            auxs = self.get_aux_files(tx_files=tx, tex_files=tex, texs=texs)
            texs.update(auxs)

        for path, _files in texs.items():
            files = []
            for filepath in _files:
                if (key(filepath) and op.exists(filepath) and
                        op.isfile(filepath)):
                    files.append(filepath)
            texs[path] = set(files)

        return texs
    
    def set_path(self, val):
        cs = self.node.colorSpace.get()
        super(FileNode, self).set_path(val)
        self.node.colorSpace.set(cs)
        


def renameFileNodePath(mapping):
    if not mapping:
        return False  # an exception should (idly) be raise
    else:
        for fileNode in pc.ls(type="file"):
            for path in mapping:
                if iutil.normpath(
                        pc.getAttr(fileNode + ".ftn")) == iutil.normpath(path):
                    cs = fileNode.colorSpace.get()
                    pc.setAttr(fileNode + ".ftn", mapping[path])
                    fileNode.colorSpace.set(cs)


def createFileNodes(paths=[]):
    file_nodes = []
    for path in paths:
        if op.exists(path):
            t_node = FileNode.create()
            file_nodes.append(t_node.node)
    return file_nodes


def getFileNodes(selection=False, rn=False):
    return FileNode.get_nodes(selection=selection, reference_nodes=rn)


def getFullpathFromAttr(attr):
    ''' get full path from attr
    :type attr: pymel.core.general.Attribute
    '''
    node = pc.PyNode(attr).node()
    val = node.cfnp.get()
    # if '<f>.' not in val: val = node.ftn.get()
    return val
