'''Contains functions related to maya scene files inside maya'''

import pymel.core as pc
import maya.cmds as cmds
import traceback
import os.path as op
import os

from .utils import newScene, newcomerObjs
from .references import referenceExists


class FileInfo(object):

    @classmethod
    def save(cls, key, value):
        pc.fileInfo[key] = value

    @classmethod
    def get(cls, key):
        return pc.fileInfo.get(key, '').decode('unicode_escape')

    @classmethod
    def remove(cls, key):
        if cls.get(key):
            return pc.fileInfo.pop(key)


def addFileInfo(key, value):
    FileInfo.save(key, value)


def getFileInfo(key=None, all=False):
    if all:
        return pc.fileInfo(q=True)
    return FileInfo.get(key)


def getFileType():
    return cmds.file(q=True, type=True)[0]


def getExtension():
    '''returns the extension of the file name'''
    return '.ma' if getFileType() == 'mayaAscii' else '.mb'


def export(filename, filepath, selection=True, pr=True, *args, **kwargs):
    ''' export selection '''
    path = os.path.join(filepath, filename)
    filetype = cmds.file(q=True, typ=True)[0]
    try:
        if selection:

            pc.exportSelected(path,
                              force=True,
                              expressions=True,
                              constructionHistory=True,
                              channels=True,
                              shader=True,
                              constraints=True,
                              options="v=0",
                              typ=filetype,
                              pr=pr)
        else:
            pc.exportAll(path, force=True, typ=filetype, pr=pr)

    except BaseException as e:
        traceback.print_exc()
        print e
        raise BaseException


def extractShadersAndSave(filename, filepath, selection=True):
    '''
    extract all the shaders
    '''
    pass


def openFile(filename, prompt=1, onError='rename'):
    if op.exists(filename):
        if op.isfile(filename):
            ext = op.splitext(filename)[-1]
            if ext in ['.ma', '.mb']:
                typ = 'mayaBinary' if ext == '.mb' else 'mayaAscii'
                try:
                    cmds.file(
                            filename.replace('\\', '/'), f=True,
                            options="v=0;", ignoreVersion=True, prompt=prompt,
                            loadReference="asPrefs", type=typ, o=True)
                except RuntimeError as error:
                    if 'rename' == onError:
                        cmds.file(rename=filename)
                    if 'raise' == onError:
                        raise error
            else:
                pc.error('Specified path is not a maya file: %s' % filename)
        else:
            pc.error('Specified path is not a file: %s' % filename)
    else:
        pc.error('File path does not exist: %s' % filename)


def saveSceneAs(path):
    cmds.file(rename=path)
    cmds.file(save=True)


def save_scene(ext):
    type = 'mayaBinary' if ext == '.mb' else 'mayaAscii'
    cmds.file(save=True, type=type)


def is_modified():
    return cmds.file(q=True, modified=True)


def get_file_path():
    return cmds.file(q=True, location=True)


def rename_scene(name):
    cmds.file(rename=name)


@newcomerObjs
def importScene(paths=[], *arg, **kwarg):
    ''' imports the paths

    @params:
            path: path to component (list)
    '''

    for path in paths:
        if referenceExists(path):
            cmds.file(path, importReference=True)
        # create reference
        else:
            try:
                cmds.file(path, i=True)
            except RuntimeError:
                pc.error('File not found.')
