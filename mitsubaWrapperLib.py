import os, sys

"""  mitsubaWrapperLib.py - This lib is used to operate Mitsuba  """ 

mitsuba_path = 'C:/Users/addalin/Mitsuba 0.5.0 64bit/Mitsuba 0.5.0'
sys.path.append(mitsuba_path + '/python/2.7')

# Ensure that Python will be able to find the Mitsuba core libraries
os.environ['PATH'] = mitsuba_path + os.pathsep + os.environ['PATH']

import mitsuba
from mitsuba.core import *
from mitsuba.render import SceneHandler
from mitsuba.render import RenderQueue, RenderJob
from mitsuba.render import Scene
import multiprocessing
#import cv2
import numpy as np


# Each row is a cam & light location in Mitsuba's LookAt format,
# i.e. [Point(position) Point(looking towards) Vector(up direction)].
# For example: [1,2,3,  0,0,0,  0,0,1] is a cam/light positioned at [1 2 3], looking 
# towards [0 0 0] with an up vector of [0,0,1]


class Mitsuba(object):
        
    # Constructor
        def __init__(self, base_path,scene_name,params):    

                self.params = params
                # Get a reference to the thread's file resolver
                self.fileResolver = Thread.getThread().getFileResolver()
                scenes_path = base_path + '/' + scene_name + '/mitsuba' 
                self.fileResolver.appendPath(scenes_path)
                paramMap = StringMap()
                paramMap['myParameter'] = 'value'
                # Load the scene from an XML file
                self.scene = SceneHandler.loadScene(self.fileResolver.resolve(scene_name+'.xml'), paramMap)

                self.scheduler = Scheduler.getInstance()
                # Start up the scheduling system with one worker per local core
                for i in range(0, multiprocessing.cpu_count()):
                        self.scheduler.registerWorker(LocalWorker(i, 'wrk%i' % i))
                self.scheduler.start()
                # Create a queue for tracking render jobs
                self.queue = RenderQueue()
                self.sceneResID = self.scheduler.registerResource(self.scene)

        # ----------------------SET SUNSKY -----------------------
        def SetSunSky(self, dir_vec, radiance=1):
                pmgr = PluginManager.getInstance()
                obj = pmgr.create({
                    'type' : 'sun',
                    'radiance' : Spectrum(radiance)
                })
                self.light = obj
        
        # ----------------------SET SPOTLIGHT -----------------------
        def SetSpotlight(self, dir_vec):
                pmgr = PluginManager.getInstance()
                obj = pmgr.create({
                    'type' : 'spot',
                    'cutoffAngle' : 40.0,
                    'intensity' : Spectrum(50),
                    'toWorld' : Transform.lookAt(
                        Point( dir_vec[0,0] , dir_vec[0,1] , dir_vec[0,2]),
                        Point( dir_vec[0,3] , dir_vec[0,4] , dir_vec[0,5]),
                        Vector(dir_vec[0,6] , dir_vec[0,7] , dir_vec[0,8])
                    )
                })
                self.light = obj
                                    

        # ----------------------SET CAMERA -----------------------
        def SetCamera(self,dir_vec):
                pmgr = PluginManager.getInstance()
                obj = pmgr.create({
                    'type' : 'perspective',
                    'toWorld' : Transform.lookAt(
                        Point( dir_vec[0,0] , dir_vec[0,1] , dir_vec[0,2]),
                        Point( dir_vec[0,3] , dir_vec[0,4] , dir_vec[0,5]),
                        Vector(dir_vec[0,6] , dir_vec[0,7] , dir_vec[0,8])
                    ),
                    'film' : {
                        'type' : 'ldrfilm',
                        'width' :  self.params['camWidth'],
                        'height' : self.params['camHeight'],
                    },
                    'sampler' : {
                    'type' : 'independent',
                    'sampleCount' : 100
                    }#,
                    #'medium' : {
                        #'type' : 'homogeneous',
                        #'sigmaT' : Spectrum(0.45),
                        #'albedo' : Spectrum([0.7,0.7,0.9]),
                        #'phase' : {
                            #'type' : 'hg',
                            #'g' : 0.2
                        #}
                    #}
                })
                self.cam = obj
                
        def __createSampler(self,sampleCount):
                pmgr = PluginManager.getInstance()
                obj = pmgr.create({
                    'type' : 'independent',
                    'sampleCount' : sampleCount 
                    })
                self.sampler = obj                
                
                
        # ----------------------RENDER-----------------------         
        def Render(self,sampleCount):
                currScene = Scene(self.scene)
                currScene.addChild(self.light)
                currScene.configure()    
                currScene.addSensor(self.cam)   
                currScene.setSensor(self.cam) 
                self.__createSampler(sampleCount) # sample count
                currScene.setSampler(self.sampler)
             
                currScene.setDestinationFile('')
                # Create a render job and insert it into the queue
                job = RenderJob('myRenderJob', currScene, self.queue )
                job.start()
                self.queue.waitLeft(0)
                self.queue.join()
                
                film = currScene.getFilm()
                size = film.getSize()
                bitmap = Bitmap(Bitmap.ERGBA, Bitmap.EFloat16, size)
                film.develop(Point2i(0, 0), size, Point2i(0, 0), bitmap)
                # End of render - get result
                result_image = np.array(bitmap.getNativeBuffer())                                
                
                return result_image