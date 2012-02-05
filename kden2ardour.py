#!/usr/bin/python

import os,sys


""" Parseador de argumentos en terminal. Ejemplo from kdenparse.py """
import argparse	

""" XML Parser. Ejemplo from kdenparse.py """
from xml.dom import minidom
from decimal import Decimal,getcontext,ROUND_DOWN
from math import modf, floor
from lxml import etree
import subprocess
import shutil

## variables globales
PATH_ = "/home/siroco"

class Kden2Ardour:

    def __init__(self,file):
        	self.xmldoc = minidom.parse(file)
	        
    def getProjectProfile(self):
        profileDict = {}
        profile = self.xmldoc.getElementsByTagName("profile")
        keyList = profile.item(0).attributes.keys()
        for a in keyList:
            profileDict[a] = profile.item(0).attributes[a].value
        return profileDict
        
    def getTracks(self):
        tracks = []
        t = self.xmldoc.getElementsByTagName("track")
        for track in t:
            tracks.append(track.attributes["producer"].value) 
        return tuple(tracks)
    
    def getPlaylists(self):
        playlistList = []
        playlists = self.xmldoc.getElementsByTagName("playlist")
        for p in playlists:
            eventList = []
            plDict = {}
            plDict["pid"] = p.attributes["id"].value
            events = p.getElementsByTagName("entry")
            for event in events:
                evDict = {}
                evDict["producer"] = event.attributes["producer"].value
                evDict["inTime"] = event.attributes["in"].value
                evDict["outTime"] = event.attributes["out"].value
                eventList.append(evDict)
            plDict["events"] = eventList
            playlistList.append(plDict)
        return tuple(playlistList)
    
    def getKProducers(self):
        kProducerList = []
        profile = self.xmldoc.getElementsByTagName("kdenlive_producer")
        for i in profile:

            kpDict = {}
            keyList = i.attributes.keys()

            for a in keyList:
                kpDict[i.attributes[a].name] = i.attributes[a].value
            kProducerList.append(kpDict)
        return tuple(kProducerList)

    def getKProducer(self,resource):
        kProducerList = []
        profile = self.xmldoc.getElementsByTagName("kdenlive_producer")
        for i in profile :
                if i.attributes["name"].value == resource :
                    return i.attributes["resource"].value
    
    def getProducers(self):
        producerList = []
        producers = self.xmldoc.getElementsByTagName("producer")
        for p in producers:
            pDict = {}
            pDict["pid"] = p.attributes["id"].value
            pDict["inTime"] = p.attributes["in"].value
            pDict["outTime"] = p.attributes["out"].value
            properties = p.getElementsByTagName("property")
            for props in properties:
                pDict[props.attributes["name"].value.replace(".","_")] = props.firstChild.data 
                
            producerList.append(pDict)
        return tuple(producerList)
    
    def linkReferences(self):
        sourceLinks = {}
        for i in self.getProducers():
            srcPid = i["pid"]
            sourceLinks[srcPid] = i["resource"]
        return sourceLinks
    
    def derefProxy(self):
        proxyLinks = {}
        for i in self.getKProducers():
            try:
                if i["proxy"]:
                    _proxy = i["proxy"]
                    proxyLinks[_proxy] = i["resource"]
            except KeyError:
                return False
        return proxyLinks

    """ 
        Crear un proyecto ardour es un XML segun las especificaciones de Ardour
        Trabajaremos entonces con un xmldom y al finalizar los procesos trabajaremos la escritura de ese xml
    """   
    def createArdourSession(self):
    
        #ID counter
        id_counter = 1000
        path = "%s/ardour_project"%PATH_
        # Borramos un posible proyecto
        if os.path.isdir(path) : shutil.rmtree(path)
        
        ## Ahora creamos el XML de definicion del proyecto
        
        fps = self.getProjectProfile()["frame_rate_num"]
        fden = self.getProjectProfile()["frame_rate_den"]
        
        #Session
        Session = etree.Element("Session")
        Session.set("version","3.0.0")
        Session.set("name","Project KdenLive2Ardour")
        Session.set("sample-rate","48000")
        Session.set("id-counter","1000")
        Session.set("event-counter","0")
        
        #Config
        Config = etree.SubElement(Session,"Config")
        Option = etree.SubElement(Config,"Option")
        Option.set("name","xfade-mode")
        Option.set("value","FullCrossfade")
        Option = etree.SubElement(Config,"Option")
        Option.set("name","auto-xfade")
        Option.set("value","1")
        
        #Metadata
        Metadata = etree.SubElement(Session,"Metadata")

        
        pass 
        ## Creamos un proyecto Ardour3 limpio
        #Estructura de directorios
        if not os.path.isdir(path) : os.mkdir(path)
        if not os.path.isdir("%s/analysis"%path) : os.mkdir("%s/analysis"%path)
        if not os.path.isdir("%s/dead"%path) : os.mkdir("%s/dead"%path)
        if not os.path.isdir("%s/export"%path) : os.mkdir("%s/export"%path)
        if not os.path.isdir("%s/externals"%path) : os.mkdir("%s/externals"%path)
        if not os.path.isdir("%s/interchange"%path) : os.mkdir("%s/interchange"%path)
        if not os.path.isdir("%s/interchange/Project"%path) : os.mkdir("%s/interchange/Project"%path)
        if not os.path.isdir("%s/interchange/Project/audiofiles"%path) : os.mkdir("%s/interchange/Project/audiofiles"%path)
        if not os.path.isdir("%s/interchange/Project/midifiles"%path) : os.mkdir("%s/interchange/Project/midifiles"%path)
        if not os.path.isdir("%s/peaks"%path) : os.mkdir("%s/peaks"%path)
        if not os.path.isdir("%s/plugins"%path) : os.mkdir("%s/plugins"%path)
        
        print "Creado proyecto: %s"%path
       
        audio_path = "%s/interchange/Project/audiofiles"%path
      

        #Sources
        Sources = etree.SubElement(Session,"Sources")

        ## Recuperamos las fuentes del proyecto de KdenLive (en KProducers)        
        for i in self.getKProducers():

            ## transcodeamos las fuentes a la carpeta de audiofiles
            ## example: ffmpeg -i video.avi -vn audio.wav
            name = ''.join((i["resource"].split("/")[-1]).split(".")[0:-1])
            res = i["resource"]
            p = "%s/%s.wav"%(audio_path,name)
            pl = "%s/%s-L.wav"%(audio_path,name)
            pr = "%s/%s-R.wav"%(audio_path,name)
            channels = i["channels"]
            freq = i["frequency"]
            
            # Extraemos audio del video
            subprocess.Popen(["ffmpeg","-i",res,"-vn","-y","-loglevel","quiet",p]) #input,non_video,force_overwrite
            
            # Separamos los dos canales de audio si es estereo
            if channels == "2" : 
                
                subprocess.Popen(["ecasound","-q","-a:1,2","-i",p,"-a:1","-f:16,1,48000","-o",pl,"-a:2","-f:16,1,48000","-o",pr])
                
                ## Left
                Source = etree.SubElement(Sources,"Source")
                Source.set("name",name+"_L")
                Source.set("type","audio")
                Source.set("flags","Writable,CanRename,RemovableIfEmpty")
                Source.set("id",str(id_counter))
                id_counter=id_counter+1
                Source.set("channel","0")
                Source.set("origin",pl)
                
                ## right
                Source = etree.SubElement(Sources,"Source")
                Source.set("name",name+"_R")
                Source.set("type","audio")
                Source.set("flags","Writable,CanRename,RemovableIfEmpty")
                Source.set("id",str(id_counter))
                id_counter=id_counter+1
                Source.set("channel","0")
                Source.set("origin",pr)
            
            else : 
                
                ## MONO
                Source = etree.SubElement(Sources,"Source")
                Source.set("name",name)
                Source.set("type","audio")
                Source.set("flags","Writable,CanRename,RemovableIfEmpty")
                Source.set("id",str(id_counter))
                id_counter=id_counter+1
                Source.set("channel","0")
                Source.set("origin",p)
            
            print "Exportado fichero %s"%p
            
            ## BUG: No me lee todos los ficheros para convertir.. (03/02/2012)
        
        #Regions
 
        # En Kdenlive se definen estas regiones en la lista de producers
 
        Regions = etree.SubElement(Session,"Regions")

        for i in self.getProducers():

            rname = ''.join((i["resource"].split("/")[-1]).split(".")[0:-1])
            ## 1 fp a 25fps = 40ms -> 1000/25
            if i["resource"] != "black" :
                #print i["inTime"],i["resource"]
                #sys.exit()
                start = int(i["inTime"])*40
                length = int(i["length"])*40
                ## comprobar si el nombre ya existe en el archivo y si es asi anhadirle un .n

                Region = etree.SubElement(Regions,"Region")
                Region.set("name",name)
                Region.set("id",str(id_counter))
                id_counter=id_counter+1
                Region.set("type","audio")
                Region.set("position","0")
                Region.set("start",str(start))
                Region.set("length",str(length))
                Region.set("channels","2")
                Region.set("source-0","317")
                Region.set("source-1","318")
                Region.set("master-source-0","317")
                Region.set("master-source-1","318")
                Region.set("stretch","1")
                Region.set("muted","0")
                Region.set("opaque","1")
                Region.set("automatic","0")
                Region.set("locked","0")
                Region.set("automatic","0")
                Region.set("whole-file","0")
                Region.set("import","0")
                Region.set("external","0")
                Region.set("sync-marked","0")
                Region.set("left-of-split","0")
                Region.set("right-of-split","0")
                Region.set("hidden","0")
                Region.set("position-locked","0")
                Region.set("valid-transcients","0")
                Region.set("sync-position","0")
                Region.set("layer","0")
                Region.set("ancestral-start","0")
                Region.set("ancestral-length","0")
                Region.set("shift","1")
                Region.set("positional-lock-style","AudioTime")
                Region.set("envelope-active","0")
                Region.set("default-fade-in","1")
                Region.set("default-fade-out","1")
                Region.set("fade-in-active","1")
                Region.set("fade-out-active","1")
                Region.set("scale-amplitude","1")
                Region.set("first-edit","nothing")

                Envelope = etree.SubElement(Regions,"Envelope")
                Envelope.set("default","yes")
                FadeIn = etree.SubElement(Regions,"FadeIn")
                FadeIn.set("default","yes")
                FadeOut = etree.SubElement(Regions,"FadeOut")
                FadeOut.set("default","yes")
        
        # Locations
        Locations = etree.SubElement(Session,"Locations")
        Location = etree.SubElement(Locations,"Location") #loop
        Location.set("id","83")
        Location.set("name","Loop")
        Location.set("start","0")
        Location.set("end","1")
        Location.set("flags","IsAutoLoop,IsHidden")
        Location.set("locked","no")
        Location.set("position-lock-style","AudioTime")
        Location = etree.SubElement(Locations,"Location") #puch
        Location.set("id","84")
        Location.set("name","Punch")
        Location.set("start","0")
        Location.set("end","1")
        Location.set("flags","IsAutoPunch,IsHidden")
        Location.set("locked","no")
        Location.set("position-lock-style","AudioTime")
        Location = etree.SubElement(Locations,"Location") #session
        Location.set("id","393")
        Location.set("name","session")
        Location.set("start","0")
        Location.set("end","1") ### <--- duracion final de la sesion
        Location.set("flags","IsSessionRange")
        Location.set("locked","no")
        Location.set("position-lock-style","AudioTime")
        
        #Bundles
        Bundles = etree.SubElement(Session,"Bundles")
        
        #Routes
        Routes = etree.SubElement(Session,"Routes")
        ## debemos definir rutas de salida para cada track y master
        ### plantear posibilidades cuando tengamos planteadas los calculos de las pistas en regiones
        
        #RouteGroups
        RouteGroups = etree.SubElement(Session,"RouteGroups")
        
        #Click
        Click = etree.SubElement(Session,"Click")
        IO = etree.SubElement(Click,"IO")
        IO.set("name","click")
        IO.set("id","47")
        IO.set("direction","Output")
        IO.set("default-type","audio")
        IO.set("user-latency","0")
        Port = etree.SubElement(IO,"Port")
        Port.set("type","audio")
        Port.set("name","click/audio_out 1")
        Connection = etree.SubElement(Port,"Connection")
        Connection.set("other","system:playback_1")
        Port = etree.SubElement(IO,"Port")
        Port.set("type","audio")
        Port.set("name","click/audio_out 2")
        Connection = etree.SubElement(Port,"Connection")
        Connection.set("other","system:playback_2") 
        
        #NamedSelections
        NamedSelections = etree.SubElement(Session,"NamedSelections")
        
        #Speakers
        Speakers = etree.SubElement(Session,"Speakers")
        Speaker = etree.SubElement(Speakers,"Speaker")
        Speaker.set("azimuth","0")
        Speaker.set("elevation","0")
        Speaker.set("distance","1")
        Speaker = etree.SubElement(Speakers,"Speaker")
        Speaker.set("azimuth","100")
        Speaker.set("elevation","0")
        Speaker.set("distance","0")
        
        #Tempo
        TempoMap = etree.SubElement(Session,"TempoMap")
        Tempo = etree.SubElement(TempoMap,"Tempo")
        Tempo.set("start","1|1|0")
        Tempo.set("beats-per-minute","120.000000")
        Tempo.set("note-type","4.000000")
        Tempo.set("movable","no")        
        Meter = etree.SubElement(TempoMap,"Meter")
        Meter.set("start","1|1|0")
        Meter.set("beats-per-bar","4.000000")
        Meter.set("note-type","4.000000")
        Meter.set("movable","no")
        
        #MIDI
        ControlPorts = etree.SubElement(Session,"ControlPorts")
        Protocol = etree.SubElement(ControlPorts,"Protocol")
        Protocol.set("name","Generic MIDI")
        Protocol.set("feedback","0")
        Protocol.set("feedback-interval","10000")
        Protocol.set("active","yes")
        
        #Extra
        Extra = etree.SubElement(Session,"Extra")
        ClockModes = etree.SubElement(Extra,"ClockModes")
        Clock = etree.SubElement(ClockModes,"Clock")
        Clock.set("name","primary")
        Clock.set("mode","Timecode")
        Clock.set("on","yes")
            
        Session.set("id-counter",str(id_counter))

        print(etree.tostring(Session,pretty_print=True))
        
        sys.exit()


if __name__=="__main__":    
	
	version_ = "%(prog)s 0.1.0"

	argparser = argparse.ArgumentParser(prog="kden2ardour.py", 
	    add_help=True,
	    description="Parses .kdenlive project files for Ardour Sessions.")
	argparser.add_argument('-V', '--version', 
	    action='version', 
	    version=version_)
	argparser.add_argument('--ardour3', action='store_true', default=False,
	    dest='ardour_session',
	    help='Convert to Ardour3 session')
   	argparser.add_argument('--deref-proxy', action='store_true', default=False,
	    dest='deref_proxy',
	    help='Dereference proxy clip (show original filenames)')
	argparser.add_argument('--frames', action='store_true', default=False,
	    dest='show_frames',
	    help='Show frames instead of TC when using --edl.')
	argparser.add_argument('--links', action='store_true', default=False,
	    dest='show_links',
	    help='Show source id to filename association.')
	argparser.add_argument('--profile', action='store_true', default=False,
	    dest='get_profile',
	    help='Generate project profile metadata.')
	argparser.add_argument('--producers', action='store_true', default=False,
	    dest='get_producers',
	    help='Show MLT producers (media file) metadata.')
	argparser.add_argument('--kproducers', action='store_true', default=False,
	    dest='get_kproducers',
	    help='Show Kdenlive producers (media file) metadata.')
	argparser.add_argument('projectFile')

	args = argparser.parse_args()

	if not os.path.isfile(args.projectFile):
	    print "Not a file we can work with..."
	    sys.exit(1)

	try: 
	    args.projectFile.rindex(".kdenlive",-9)
	except ValueError:
	    print "Invalid filename. Exiting."
	    sys.exit(1)


	kp = Kden2Ardour(args.projectFile)
	
	if args.ardour_session:
	    kp.createArdourSession()
#	    for i in kp.createArdourSession().keys():
#	        print i + ": "+ kp.createArdourSession()[i]

	
	if args.get_profile:
	    for i in kp.getProjectProfile().keys():
        	print i + ": " + kp.getProjectProfile()[i]    

	if args.get_producers:
	    for i in kp.getProducers():
        	print "\n=================\n"
        	for kv in i:
            		print kv + ": " + i[kv]

	if args.get_kproducers:
	    for i in kp.getKProducers():
	        print "\n=================\n"
	        for kv in i:
	            print kv + ": " + i[kv]
        
	if args.deref_proxy:
	    for i in kp.derefProxy():
	        print i + ": " + kp.derefProxy()[i]
        
	if args.show_links:
	    for i in kp.linkReferences():
	        print i + ": " + kp.linkReferences()[i]

