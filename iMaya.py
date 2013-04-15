# Date: Mon 26/11/2012

import os, sys, subprocess, tempfile, stat
import pymel.core as pc
import maya.cmds as cmds
import iutilities as util
import traceback

class Arbitrary(object):
    local_drives = ['c:', 'd:', r'\\']
    presetGeo = {'camera': 'RenderCam',
                 'geometry': 'SphereSurfaceShape',
                 'path': r'r:\Pipe_Repo\Projects\DAM\Data\presetScene\ball.ma',
                 'resolution': [256, 256]}
conf = Arbitrary()
class ExportError(Exception):
    '''
    Maya asset export failed.
    '''
    def __init__(self, *arg, **kwarg):
        self.code = 0
        self.error = "Export failed. Some error occured while exporting maya scene."
        self.value = kwarg.get("obj","")
        self.strerror = self.__str__()
    def __str__(self):
        return (self.value + ". " if self.value else "") + self.error


class ShaderApplicationError(Exception):
    '''
    Unable to apply shader.
    '''
    def __init__(self, *arg, **kwarg):
        self.code = 1
        self.error = "Unable to apply shader"
        self.strerror = self.__str__()
    def __str__(self):
        return "ShaderApplicationError: ", self.error


op = os.path

def referenceExists(path):
    # get the existing references
    exists = cmds.file(r = True, q = True)
    exists = [util.normpath(x) for x in exists]
    path = util.normpath(path)
    if path in exists: return True

def export (filename, filepath, selection = True, pr = True, *arg, **kwarg):
    '''
    '''
    path = os.path.join(filepath, filename)
    try:
        if selection:
            
            pc.exportSelected(path,
                              force=True,
                              expressions = True,
                              constructionHistory = True,
                              channels = True,
                              shader = True,
                              constraints = True,
                              options="v=0",
                              typ="mayaAscii",
                              pr = pr)
        else:
            pc.exportAll(path + ".ma", force = True, typ = "mayaAscii", pr = pr)
        
        #util.setReadOnly(path + ".ma")
        
    except BaseException as e:
        traceback.print_exc()
        print e
        raise BaseException
def extractShadersAndSave (filename, filepath, selection = True):
    '''
    extract all the shaders
    '''
    pass

def referenceInfo(from_file = ""):
    '''
    Query all the top-level reference nodes in a file or in the currently open scene
    @from_file: "" if reference are to be extracted from the currently open scene,
                or else from the provided maya file.
    @return: {refnode_fullpathname:file_path}
    '''
    referenceNode={}
    referenceList=cmds.ls(references=True)
    referenceName = set()
    referencePath=set()
    for ref_List in referenceList:
        try:
            ref_Name=cmds.referenceQuery( ref_List, referenceNode=True, topReference=True )
            ref_Path=cmds.referenceQuery( ref_Name,filename=True )
            referenceName.add(ref_Name)
            referencePath.add(ref_Path)
        except BaseException as e:
            print e
            continue
    k=0
    o=list(referencePath)
    for referenceName in referenceName:
        referenceNode[referenceName ]=o[k]
        k+=1

    if not from_file:
        ref = dict()
        for ref_list in cmds.ls(references = True):
            try:
                ref_Name = cmds.referenceQuery( ref_List, referenceNode = True, topReference = True )
                ref_Path = cmds.referenceQuery( ref_Name, filename = True )
                ref[ref_Name] = ref_Path
            except BaseException as e:
                print e
                continue
        return ref


def objSetDiff(new, cur):
    
    # curSg.union([pc.PyNode(obj) for obj in cur])
    curSgs = set([str(obj) for obj in cur])
    # newSg = pc.sets()
    # newSg.union([pc.PyNode(obj) for obj in new])
    newSgs = set([str(obj) for obj in new])
    diff = newSgs.difference(curSgs)
    return [obj for obj in diff]
    

def newScene(func):
    '''
    Make a bare scene.
    '''
    def wrapper(*arg, **kwarg):
        
        if kwarg.get("newScene"):
            pc.newFile(f=True)
        else: pass
        print "newScene"
        print arg
        print kwarg
        return func(*arg, **kwarg)
    return wrapper

def newcomerObjs(func):
    '''
    @return: the list of objects that were added to the scene
    after calling func
    '''
    def wrapper(*arg, **kwarg):
        selection = cmds.ls(sl = True)
        cur = cmds.ls()
        print "newcomerObjs"
        print arg
        print kwarg
        func(*arg, **kwarg)
        new = objSetDiff(cmds.ls(), cur)
        pc.select(selection)
        return new
    return wrapper

@newScene
@newcomerObjs
def addReference(paths=[], *arg, **kwarg):
    '''
    adds reference to the component at 'path' (str)
    @params:
            path: valid path to the asset dir (str)
            component: (Rig, Model, Shaded Model) (str)
    '''
    for path in paths:
        # get the existing references
        if referenceExists(path):
            cmds.file(path, loadReference = True)
        # create reference
        else:
            try:
                cmds.file(path, r = True)
            except RuntimeError:
                pc.error('file not found')
@newScene
@newcomerObjs
def importScene(paths = [], *arg, **kwarg):
    '''
    imports the path
    @params:
            path: path to component (list)
    '''

    for path in paths:
        if referenceExists(path):
            cmds.file(path, importReference = True)
        # create reference
        else:
            try:
                cmds.file(path, i = True)
            except RuntimeError:
                pc.error('file not found')

def addOptionVar(key, value, array = True):
    '''
    creates an option variable
    '''
    if array:
        cmds.optionVar(sva = (key, value))
    else:
        cmds.optionVar(sv = (key, value))

def removeOptionVar(key, index = None):
    if index is not None:
        cmds.optionVar(rfa = (key, index))
    else: cmds.optionVar(rm = key)

def getOptionVars(key):
    return cmds.optionVar(q = key)

def createComponentChecks():
      return any((util.localPath(path, conf.local_drives) for path in referenceInfo().values()))

def getFileNodes(selection):
    print cmds.ls(sl = selection, rn = False)
    return [fileNode for obj in cmds.ls(sl = selection,
                                      rn = False)
            for shader in filter(lambda hist: isinstance(hist,
                                                         pc.nt.ShadingEngine),
                                 pc.listHistory(obj, f = True))
            for fileNode in filter(lambda shaderHist: isinstance(shaderHist,
                                                                 pc.nt.File),
                                   getShadingEngineHistoryChain(shader))]

def imageInRenderView():
    ff = pc.getAttr('defaultRenderGlobals.imageFormat')
    pc.setAttr('defaultRenderGlobals.imageFormat', 32)
    render = pc.renderWindowEditor('renderView', e=1, wi = util.getTemp(suffix = ".png"))
    pc.setAttr('defaultRenderGlobals.imageFormat', ff)
    return render[1]

def renameFileNodePath(mapping):
    if not mapping:
        return False            # an exception should (idly) be raise
    else:
        for fileNode in pc.ls(type= "file"):
            for path in mapping:
                if util.normpath(pc.getAttr(fileNode + ".ftn")) == util.normpath(path):
                    pc.setAttr(fileNode + ".ftn", mapping[path])

def getShadingEngineHistoryChain(shader):
    chain = []
    sets = cmds.sets( str( shader ), q = True )
    for inputs in map(lambda inp: getattr(pc.PyNode(shader),
                                        inp).inputs(),
                    ["vs", "ds", "ss"]):
        if inputs:
            chain.extend([x for x in pc.listHistory(inputs[0])
            if not isinstance( x, pc.nt.Reference )
            and ((not x in sets) if sets else True)
            and not isinstance(x, pc.nt.GroupId)])
    return chain + [shader]

def textureFiles(selection = True):
    return list(set([util.normpath(textureFile) for fileNode in set(getFileNodes(selection))
            if op.exists(util.normpath(pc.getAttr(fileNode + ".ftn")))
            for textureFile in
            util.getSequenceFiles(pc.getAttr(fileNode + ".ftn"))
                     + [util.normpath(pc.getAttr(fileNode + ".ftn"))]]))

def _rendShader(shaderPath,
               renderImagePath,
               geometry = r"SphereSurfaceShape",
               cam = "RenderCam",
               res = (256, 256),
               presetScenePath = r"d:\user_files\hussain.parsaiyan\Desktop\Scenes\V-Ray\V-Ray Ball Scene\ball.ma"):
    rl = "1:masterLayer"
    mel = """setAttr vraySettings.vfbOn 0; setAttr defaultRenderLayer.renderable 1; setAttr defaultRenderGlobals.animation 0; setAttr vraySettings.relements_enableall 0; setAttr vraySettings.relements_separateFolders 0; file -r \\"{shaderPath}\\"; $shader = ls(\\"-rn\\", \\"-type\\", \\"shadingEngine\\"); connectAttr \\"{geometry}.iog\\" ($shader[0] + \\".dsm[0]\\"); setAttr \\"vraySettings.vfbOn\\" 1;""".format(geometry = geometry, shaderPath = shaderPath.replace(r"\\", "\\").replace("\\", r"\\"))
   
    r = "vray"
    x, y = res
    rd = op.dirname(renderImagePath)
    basename = op.basename(renderImagePath)
    of = "png"
    rl = "1:masterLayer"
    status = util.silentShellCall(r'render -r {r} -preRender "{mel}"  -of "{of}" -rd "{rd}" -im "{basename}" -x {x} -y {y} -rl {rl}  "{path}"'.format(
            **{"r": r,
               "cam": cam,
               "x": x,
               "y": y,
               "rd": rd,
               "of": of,
               "basename": basename,
               "mel": mel,
               "path": presetScenePath,
               "rl": rl}
              ))
    return status

def render(*arg, **kwarg):
    '''
    @return: path to render image and shader n/w that was exported. tuple
    '''
    selection = pc.ls(sl = True)
    try:
        if kwarg.get("sg"):
            presetGeo = conf.presetGeo
            with tempfile.NamedTemporaryFile(suffix = ".ma") as fobj:
                shader = op.splitext(fobj.name)[0]
            pc.select(getShadingEngineHistoryChain(kwarg.get("sg").keys()[0]),
                      ne = True)
            pc.Mel.eval('file -type "mayaAscii"')
            export(op.basename(shader),
                   op.dirname(shader),
                   selection = True,
                   pr = False)
            with tempfile.NamedTemporaryFile(suffix = ".png") as fobj:
                renImage = op.splitext(fobj.name)[0]
           
            status = _rendShader(shader + ".ma",
                             renImage,
                             geometry = presetGeo["geometry"],
                             cam = presetGeo["camera"],
                             res = presetGeo["resolution"],
                             presetScenePath = presetGeo["path"]
                             )
            
            result = (renImage + ".png", shader + ".ma")
            print "result: ", result
            if int(status) != 0 or not all(map(op.exists, result)):
                raise ExportError(obj = kwarg["sg"].keys()[0])
            
        else:
            pc.runtime.mayaPreviewRenderIntoNewWindow()
            result = imageInRenderView()
    except BaseException as e:
        traceback.print_exc()
        raise e
    finally:
        pc.select(selection, ne = True)        
    return result

def snapshot():
    snapLocation = op.join(os.getenv("tmp"), str(int(util.randomNumber()*100000)))
    command = """float $currFrame = `currentTime -q`;
int $format = `getAttr "defaultRenderGlobals.imageFormat"`;
setAttr "defaultRenderGlobals.imageFormat" 8;
playblast -frame $currFrame -format "image" -cf "{image}" -orn 0 -v 0 -wh {res} -p 100;
setAttr "defaultRenderGlobals.imageFormat" $format;""".format(res =
                                                              " ".join(map(str, conf.presetGeo["resolution"])),
                                                              image =
                                                              snapLocation.replace("\\",
                                                                                   "/"))
    pc.mel.eval(command)
    return snapLocation
    
def selected():
    '''
    @return True, if selection exists in the current scene
    '''
    s = pc.ls(sl = True, dag = True, geometry = True)
    if s:
        return True
    else:
        return False

def openComp(path, f = False):
    pc.openFile(path, force = f)

def getMeshes(selection = False):
    '''
    returns only meshes from the scene or selection
    '''
    meshSet = set()
    for mesh in pc.ls(sl = selection):
        if type(mesh) == pc.nt.Transform:
            try:
                m = mesh.getShape()
                if type(m) == pc.nt.Mesh:
                    meshSet.add(m)
            except AttributeError:
                pass
        elif type(mesh) == pc.nt.Mesh:
            meshSet.add(mesh)
        else: pass
    return list(meshSet)
    
def getShadingEngines(selection = False):
    '''
    returns the materials and shading engines
    @param:
        selection: if True, returns the materials and shading engines of selected meshes else all
    @return: dictionary {material: [shadingEngine1, shadingEngine2, ...]}
    '''
    sgMtl = {}
    sg = set()
    if selection:
        #meshes = getMeshes(selection = selection)
        meshes = pc.ls(sl=True, dag=True, type='mesh')
        otherNodes = pc.ls(sl=True, dep=True)
        meshes += otherNodes 
        for mesh in meshes:
            for s in pc.listConnections(mesh, type = 'shadingEngine'):
                sg.add(s)
        sg.update(pc.ls(sl=True, type = 'shadingEngine' ))
    else:
        sg.update(set(pc.ls(type = 'shadingEngine')))
    for x in sg:
        ss = x.surfaceShader.inputs()
        ds = x.displacementShader.inputs()
        vs = x.volumeShader.inputs()
        imgs = x.imageShader.inputs()
        
        if ss: mtl = ss[0]
        elif ds: mtl = ds[0]
        elif vs: mtl = vs[0]
        elif imgs: mtl = imgs[0]
        else: continue
            
        #x = str(x)
        mtl = str(mtl)
        if not mtl: continue
        if sgMtl.has_key(mtl):
            if x not in sgMtl[mtl]:
                sgMtl[mtl].append(x)
        else:
            sgMtl[mtl] = [x]
    return sgMtl

def bins():
    binScenes = pc.getAttr("defaultRenderGlobals.hyperShadeBinList")
    if binScenes:
        return binScenes.split(";")
    else:
        return []

def objFilter(objType, objList):
    '''
    filter an objList for a particular type of maya obj
    @objType: currently only accepts PyNodes
    '''
    return filter(lambda obj: isinstance(pc.PyNode(obj),
                                         objType),
                  objList)

def addShadersToBin(binName, paths = [], new = True):
    '''
    bin is a group of shaders
    '''
    if paths and any(map(op.exists, paths)):
        pc.runtime.HypershadeWindow()
        pc.Mel.eval('refreshHyperShadeBinsUI "hyperShadePanel1Window|TearOffPane|hyperShadePanel1|mainForm|mainPane|createBarWrapForm|createAndOrganizeForm|createAndOrganizeTabs|Bins" true;')   
        thisBin = pc.Mel.eval('hyperShadeCreateNewBin("hyperShadePanel1Window|TearOffPane|hyperShadePanel1|mainForm|mainPane|createBarWrapForm|createAndOrganizeForm|createAndOrganizeTabs|Bins|binsScrollLayout|binsGridLayout", "%s")' %binName) if new else binName
    for path in paths:
        if op.exists(path):
            for sg in objFilter(pc.nt.ShadingEngine,
                                importScene(paths = [path], new = False)):
                pc.Mel.eval('hyperShadeAddNodeAndUpstreamNodesToBin("%s", "%s")'%(thisBin, str(sg)))

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

def applyShaderToSelection(path):
    '''
    applies a shader to selected mesh in the current scene
    @params:
        @path: path to a maya file, which contains a shader
    '''
    try:
        if op.exists(path):
            sgs = objFilter(pc.nt.ShadingEngine, importScene(paths = [path], new = False))
            for sg in sgs:
                pc.hyperShade(assign = sg)
                break
            if len(sgs) > 1:
                pc.warning("Number of shader were more then one but only applied " + str(sg))
    except ShaderApplicationError as e:
        print e
        raise e

if __name__ == "__main__":
    for _ in xrange(1):
        snapshot()
    print "loaded"
