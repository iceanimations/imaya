import pymel.core as pc


class SetDict(dict):
    ''' A type of dictionary which can only have sets as its values and update
    performs union on sets
    '''
    def __getitem__(self, key):
        if key not in self:
            self[key] = set()
        return super(SetDict, self).__getitem__(key)

    def __setitem__(self, key, val):
        if not isinstance(val, set):
            raise TypeError, 'value must be a set'
        super(SetDict, self).__setitem__(key, val)

    def get(self, key, *args, **kwargs):
        return self.__getitem__(key)

    def update(self, d):
        if not isinstance(d, SetDict):
            raise TypeError, "update argument must be a setDict"
        for k, v in d.iteritems():
            self[k].update(v)


def getFileNodes(selection=False, rn=False):
    return pc.ls(type='file', sl=selection, rn=rn)


def renameFileNodePath(mapping):
    if not mapping:
        return False  # an exception should (idly) be raise
    else:
        for fileNode in pc.ls(type="file"):
            for path in mapping:
                if util.normpath(pc.getAttr(fileNode + ".ftn")) == util.normpath(path):
                    pc.setAttr(fileNode + ".ftn", mapping[path])


uvTilingModes = ['None', 'zbrush', 'mudbox', 'mari', 'explicit']


def textureFiles(selection=True, key=lambda x: True, getTxFiles=True,
        returnAsDict=False):
    '''
    @key: filter the tex with it
    :rtype setDict:
    '''
    ftn_to_texs = SetDict()
    fileNodes = getFileNodes(selection)

    for fn in fileNodes:
        texs = getTexturesFromFileNode(fn, key=key, getTxFiles=True)
        ftn_to_texs.update(texs)

    if returnAsDict:
        return ftn_to_texs
    else:
        return list(reduce(lambda a,b: a.union(b), ftn_to_texs.values(), set()))


def getTexturesFromFileNode(fn, key=lambda x:True, getTxFiles=True,
        getTexFiles=True):
    ''' Given a Node of type file, get all the paths and texture files
    :type fn: pc.nt.File
    '''
    if not isinstance(fn, pc.nt.File):
        if not pc.nodeType == 'file':
            raise TypeError, '%s is not a file node' % fn

    texs = SetDict()

    filepath = readPathAttr(fn + '.ftn')
    uvTilingMode = uvTilingModes[0]

    # New in Maya 2015
    if pc.attributeQuery('uvTilingMode', node=fn, exists=True):
        uvTilingMode = uvTilingModes[pc.getAttr(fn + '.uvt')]

    # still attempt to resolve using tokens in string
    if uvTilingMode == 'None':
        uvTilingMode = str(util.detectUdim(filepath))
    elif not uvTilingMode == 'explicit':
        filepath = readPathAttr(fn + '.cfnp')

    # definitely no udim
    if uvTilingMode == 'None':
        if key(filepath) and op.exists(filepath) and op.isfile(filepath):
            texs[filepath].add(filepath)
        if pc.getAttr(fn + '.useFrameExtension'):
            seqTex = util.getSequenceFiles(filepath)
            if seqTex:
                texs[filepath].update(seqTex)

    # explicit naming
    elif uvTilingMode == 'explicit':
        if key(filepath) and op.exists(filepath) and op.isfile(filepath):
            texs[filepath].add(filepath)
        indices = pc.getAttr(fn + '.euvt', mi=True)
        for index in indices:
            filepath = readPathAttr(fn + '.euvt[%d].eutn'%index)
            if key(filepath) and op.exists(filepath) and op.isfile(filepath):
                texs[filepath].add(filepath)

    else: # 'mari', 'zbrush', 'mudbox'
        texs[filepath].update( util.getUVTiles( filepath, uvTilingMode ))

    if getTxFiles:
        for k, files in texs.iteritems():
            texs[k].update(filter(None,
                [util.getFileByExtension(f) for f in files]))

    if getTexFiles:
        for k, files in texs.iteritems():
            texs[k].update(filter(None,
                [util.getFileByExtension(f, ext='tex') for f in files]))

    return texs


def getFullpathFromAttr(attr):
    ''' get full path from attr
    :type attr: pymel.core.general.Attribute
    '''
    node = pc.PyNode(attr).node()
    val = node.cfnp.get()
    #if '<f>.' not in val: val = node.ftn.get()
    return val


def remapFileNode(fn, mapping):
    ''' Update file node with given mapping
    '''
    if not isinstance(fn, pc.nt.File):
        if not pc.nodeType == 'file':
            raise TypeError, '%s is not a file node' % fn

    reverse = []
    uvTilingMode = uvTilingModes[0]
    if pc.attributeQuery('uvTilingMode', node=fn, exists=True):
        uvTilingMode = uvTilingModes[pc.getAttr(fn + '.uvt')]

    if uvTilingMode == 'None' or uvTilingMode == 'explicit':
        path = readPathAttr(fn + '.ftn')
        if mapping.has_key(path):
            pc.setAttr(fn + '.ftn', mapping[path])
            reverse.append((mapping[path], path))

    if uvTilingMode == 'explicit':
        reverse = []
        indices = pc.getAttr(fn + '.euvt', mi=True)
        for index in indices:
            path = readPathAttr(fn + '.euvt[%d].eutn'%index)
            if mapping.has_key(path):
                pc.setAttr(fn + '.euvt[%d].eutn'%index, mapping[path])
                reverse.append((mapping[path], path))

    elif uvTilingMode in uvTilingModes[1:4]:
        path = readPathAttr(fn + '.cfnp')
        if mapping.has_key(path):
            pc.setAttr(fn + '.ftn', mapping[path])
            reverse.append( (mapping[path], path) )

    return reverse

def readPathAttr(attr):
    '''the original function to be called from some functions this module
    returns fullpath according to the current workspace'''
    val = pc.getAttr(unicode( attr ))
    val = pc.workspace.expandName(val)
    val = op.abspath(val)
    return op.normpath(val)


def texture_mapping(newdir, olddir=None, scene_textures=None):
    ''' Calculate a texture mapping dictionary
    :newdir: the path where the textures should be mapped to
    :olddir: the path from where the textures should be mapped from, if an
    argument is not provided then all are mapped to this directory
    :scene_textures: operate only on this dictionary, if an argument is not
    provided all scene textures are mapped
    :return: dictionary with all the mappings
    '''
    if not scene_textures:
        scene_textures = textureFiles(selection=False, returnAsDict=True)

    mapping = {}

    for ftn, texs in scene_textures.items():
        alltexs = [ftn] + list(texs)
        for tex in alltexs:
            tex_dir, tex_base = os.path.split(tex)
            if olddir is None or util.paths_equal(tex_dir, olddir):
                mapping[tex] = os.path.join(newdir, tex_base)

    return mapping


def texture_mapping(newdir, olddir=None, scene_textures=None):
    ''' Calculate a texture mapping dictionary
    :newdir: the path where the textures should be mapped to
    :olddir: the path from where the textures should be mapped from, if an
    argument is not provided then all are mapped to this directory
    :scene_textures: operate only on this dictionary, if an argument is not
    provided all scene textures are mapped
    :return: dictionary with all the mappings
    '''
    if not scene_textures:
        scene_textures = textureFiles(selection=False, returnAsDict=True)

    mapping = {}

    for ftn, texs in scene_textures.items():
        alltexs = [ftn] + list(texs)
        for tex in alltexs:
            tex_dir, tex_base = os.path.split(tex)
            if olddir is None or util.paths_equal(tex_dir, olddir):
                mapping[tex] = os.path.join(newdir, tex_base)

    return mapping


def collect_textures(dest, scene_textures=None):
    '''
    Collect all scene texturefiles to a flat hierarchy in a single directory while resolving
    nameclashes

    @return: {ftn: tmp}
    '''

    # normalized -> temp
    mapping = {}
    if not op.exists(dest):
        return mapping

    if not scene_textures:
        scene_textures = textureFiles(selection = False, key = op.exists,
                returnAsDict=True)

    for myftn in scene_textures:
        if mapping.has_key(myftn):
            continue
        ftns, texs = util.find_related_ftns(myftn, scene_textures.copy())
        newmappings=util.lCUFTN(dest, ftns, texs)
        for fl, copy_to in newmappings.items():
            if op.exists(fl):
                shutil.copy(fl, copy_to)
        mapping.update(newmappings)
    return mapping


def collect_textures(dest, scene_textures=None):
    '''
    Collect all scene texturefiles to a flat hierarchy in a single directory while resolving
    nameclashes

    @return: {ftn: tmp}
    '''

    # normalized -> temp
    mapping = {}
    if not op.exists(dest):
        return mapping

    if not scene_textures:
        scene_textures = textureFiles(selection = False, key = op.exists,
                returnAsDict=True)

    for myftn in scene_textures:
        if mapping.has_key(myftn):
            continue
        ftns, texs = util.find_related_ftns(myftn, scene_textures.copy())
        newmappings=util.lCUFTN(dest, ftns, texs)
        for fl, copy_to in newmappings.items():
            if op.exists(fl):
                shutil.copy(fl, copy_to)
        mapping.update(newmappings)

    return mapping


def collect_textures(dest, scene_textures=None):
    '''
    Collect all scene texturefiles to a flat hierarchy in a single directory while resolving
    nameclashes

    @return: {ftn: tmp}
    '''

    # normalized -> temp
    mapping = {}
    if not op.exists(dest):
        return mapping

    if not scene_textures:
        scene_textures = textureFiles(selection = False, key = op.exists,
                returnAsDict=True)

    for myftn in scene_textures:
        if mapping.has_key(myftn):
            continue
        ftns, texs = util.find_related_ftns(myftn, scene_textures.copy())
        newmappings=util.lCUFTN(dest, ftns, texs)
        for fl, copy_to in newmappings.items():
            if op.exists(fl):
                shutil.copy(fl, copy_to)
        mapping.update(newmappings)

    return mapping


def collect_textures(dest, scene_textures=None):
    '''
    Collect all scene texturefiles to a flat hierarchy in a single directory while resolving
    nameclashes

    @return: {ftn: tmp}
    '''

    # normalized -> temp
    mapping = {}
    if not op.exists(dest):
        return mapping

    if not scene_textures:
        scene_textures = textureFiles(selection = False, key = op.exists,
                returnAsDict=True)

    for myftn in scene_textures:
        if mapping.has_key(myftn):
            continue
        ftns, texs = util.find_related_ftns(myftn, scene_textures.copy())
        newmappings=util.lCUFTN(dest, ftns, texs)
        for fl, copy_to in newmappings.items():
            if op.exists(fl):
                shutil.copy(fl, copy_to)
        mapping.update(newmappings)

    return mapping


def createFileNodes(paths=[]):
    for path in paths:
        if op.exists(path):
            # createNodes and setAttrs
            fileNode = pc.shadingNode('file', asTexture=True)
            pc.setAttr(str(fileNode)+".ftn", path)
            placeNode = pc.shadingNode('place2dTexture', asUtility=True)

            # default connect placeNode and fileNode
            placeNode.coverage >> fileNode.coverage
            placeNode.translateFrame >> fileNode.translateFrame
            placeNode.rotateFrame >> fileNode.rotateFrame
            placeNode.mirrorU >> fileNode.mirrorU
            placeNode.mirrorV >> fileNode.mirrorV
            placeNode.stagger >> fileNode.stagger
            placeNode.wrapU >> fileNode.wrapU
            placeNode.wrapV >> fileNode.wrapV
            placeNode.repeatUV >> fileNode.repeatUV
            placeNode.offset >> fileNode.offset
            placeNode.rotateUV >> fileNode.rotateUV
            placeNode.noiseUV >> fileNode.noiseUV
            placeNode.vertexUvOne >> fileNode.vertexUvOne
            placeNode.vertexUvTwo >> fileNode.vertexUvTwo
            placeNode.vertexUvThree >> fileNode.vertexUvThree
            placeNode.vertexCameraOne >> fileNode.vertexCameraOne
            placeNode.outUV >> fileNode.uv
            placeNode.outUvFilterSize >> fileNode.uvFilterSize


def map_textures(mapping):
    reverse = {}

    for fileNode in getFileNodes():
        for k, v in remapFileNode(fileNode, mapping):
            reverse[k]=v

    return reverse

