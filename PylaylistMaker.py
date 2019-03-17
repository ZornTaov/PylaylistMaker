import os
import sys
import json
import logging
from collections import OrderedDict
import datetime

zipTypes = [".7z", ".zip", ".gz"]
coresJson = []

jsonTemplate={
    "version": "1.0",
    "items": []
}
templateOrder = ["version", "items"]
keyOrder = ["path", "label", "core_path", "core_name", "crc32", "db_name"]
def generateOldPlaylistEntry(fileName, ext, romDir, systemName, core=""):
    if core:
        core_path = Settings["coresPath"]+core+"_libretro_libnx.nro"
    else:
        core_path = "DETECT"
    info =[
        romDir+"/"+fileName+ext, #file path
        fileName, #game name, derived from file
        core_path, #core used, only going to care if there's one core, let the player choose inside RA instead
        core, #core name, only really caring if there's only one core
        "DETECT", #crc, I don't care
        systemName+".lpl"
    ]
    return info
def generatePlaylistEntry(fileName, ext, romDir, systemName, core=""):
    if core:
        core_path = Settings["coresPath"]+core+"_libretro_libnx.nro"
    else:
        core = "DETECT"
        core_path = "DETECT"
    info = {
        "path": romDir+"/"+fileName+ext,
        "label": fileName,
        "core_path": core_path,
        "core_name": core,
        "crc32": "DETECT",
        "db_name": systemName+".lpl"
    }
    return info

def oldToNew(entry):
    info = {
        "path": entry[0],
        "label": entry[1],
        "core_path": entry[2],
        "core_name": entry[3],
        "crc32": entry[4],
        "db_name": entry[5]
    }
    return info

def newToOld(entry):
    info =[
        entry["path"],
        entry["label"],
        entry["core_path"],
        entry["core_name"],
        entry["crc32"],
        entry["db_name"]
    ]
    return info

def getRomPath():
    if not os.path.isdir(Settings["romsPaths"][Settings["indexRomPathUsed"]]):
        os.mkdir(Settings["romsPaths"][Settings["indexRomPathUsed"]])
    return Settings["romsPaths"][Settings["indexRomPathUsed"]]

def getCoreFolder(core):
    return core["name"] if Settings["useShorthandName"] else core["system"][0]

def toOrderedDict(entry, order):
    return OrderedDict([(key, entry[key]) for key in order])

def validateFolders():
    global state
    for core in coresJson:
        logger.info("validating rom folder at "+getRomPath()+getCoreFolder(core))
        if not os.path.isdir(getRomPath()+getCoreFolder(core)):
            logger.debug("Missing "+getRomPath()+getCoreFolder(core))
            os.mkdir(getRomPath()+getCoreFolder(core))
            with open(getRomPath()+getCoreFolder(core)+"/files.txt", "w") as info:
                info.write("put files in here ending with: ")
                for i in zipTypes:
                    info.write(i+", ")
                for i in core["allExt" if Settings["useAllExtentions"] else "systemExt"]:
                    info.write(i+", ")
    state = "Validate: Complete"


def addToPlaylist(system, entries, asJson=False):
    logger.debug("Starting addToPlaylist")
    if os.path.isfile(Settings["playlistsPath"]+system+".lpl"):
        logger.debug("Found playlist " + system)
        #there's already a file, so read from it to get what's already there
        newentries = []
        known = []
        jsonPlaylist = {}
        lastChar = ""
        with open(Settings["playlistsPath"]+system+".lpl", "r", newline='') as playlist:
            firstChar = playlist.read(1)
            
            if firstChar:
                playlist.seek(0, os.SEEK_SET)
                if firstChar in ["{","["]:
                    logger.debug("playlist is json")
                    #convert from old to new format
                    entries = [toOrderedDict(oldToNew(entries[i:i+6]), keyOrder) for i in range(0,len(entries),6)]

                    jsonPlaylist = json.load(playlist, object_pairs_hook=OrderedDict)
                    #get list of known entries
                    known = [x["path"] for x in jsonPlaylist["items"]]
                    #check if entry is known
                    for entry in entries:
                        if entry["path"] not in known:                            
                            newentries.append(entry)
                    #add newentries to existing playlist
                    if newentries:
                        logger.debug("Adding "+str(len(newentries))+" new entries to "+system)
                        #write to the file those that are new
                        with open(Settings["playlistsPath"]+system+".lpl", "w", newline="\n") as playlist:
                            jsonPlaylist["items"].extend(newentries)
                            json.dump(OrderedDict([(key, jsonPlaylist[key]) for key in templateOrder]), playlist, sort_keys=False, indent=2)
                        logger.info(system+" playlist modified.")
                else:
                    logger.debug("playlist is old format")
                    #get list of known entries
                    line = playlist.readline()
                    while line:
                        known.append(line[:-1])#os.path.split(line)[1][:-1])
                        playlist.readline()#playlist are always multiple of 6
                        playlist.readline()
                        playlist.readline()
                        playlist.readline()
                        lastLine = playlist.readline()
                        lastChar = lastLine[:-1]
                        line = playlist.readline()
                        if line == "" and lastChar == "\n":
                            lastChar = "\n" 
                            break
                    #check if entry is known
                    for i in range(0,len(entries),6):
                        if entries[i] not in known: #os.path.split(entries[i])[1]
                            newentries.extend(entries[i:i+6])
                    #add newentries to existing playlist
                    if newentries:
                        logger.debug("Adding "+str(len(newentries))+" new entries to "+system)
                        with open(Settings["playlistsPath"]+system+".lpl", "a", newline='') as playlist:
                            if lastChar != "\n":
                                playlist.write("\n")

                            for entry in newentries:
                                playlist.write(entry+"\n")
                        logger.info(system+" playlist modified.")
    else:
        logger.debug("Making playlist "+system)
        #first time creation
        with open(Settings["playlistsPath"]+system+".lpl", "w", newline="\n") as playlist:
            if asJson:
                #make json playlist
                plist = jsonTemplate
                entries = [toOrderedDict(oldToNew(entries[i:i+6]), keyOrder) for i in range(0,len(entries),6)]

                plist["items"] = entries
                json.dump(OrderedDict([(key, plist[key]) for key in templateOrder]), playlist, sort_keys=False, indent=2)
            else:
                #make old playlist
                for entry in entries:
                    playlist.write(entry+"\n")
            logger.info(system+" playlist created")
                
def generatePlaylist():
    global state
    logger.debug("Starting generatePlaylist at "+str(datetime.datetime.now()))
    for core in coresJson:
        if core["allExt"]:
            playlist = []
            romList = []
            if os.path.isdir(getRomPath()+getCoreFolder(core)):
                romList = os.listdir(getRomPath()+getCoreFolder(core))
            #generate entry per rom
            if romList:
                #filter if there are .m3u's
                if getCoreFolder(core) == "psx":
                    result = []
                    for rom in romList:
                        romsplit = os.path.splitext(rom)
                        if romsplit[1].lower() == ".m3u":
                            #load m3u, filter out cue names
                            with open(getRomPath()+getCoreFolder(core)+"/"+rom) as f:
                                result.extend([line.rstrip('\n') for line in f if line != "\n"])
                    logger.debug("ignoring PSX cue's")
                    logger.debug(result)
                    romList = [x for x in romList if not x in result]
                for rom in romList:
                    romsplit = os.path.splitext(rom)
                    #it's a zip file 
                    if (romsplit[1].lower() in zipTypes or
                        #using all extentions
                        Settings["useAllExtentions"] and romsplit[1].lower() in core["allExt"] or 
                        #use only extentions for system
                        core["systemExt"] and romsplit[1].lower() in core["systemExt"] or 
                        #fallback if systemExt is empty
                        not Settings["useAllExtentions"] and not core["systemExt"] and 
                        romsplit[1].lower() in core["allExt"]):

                        coreUsed = ""
                        if len(core["cores"]) == 1:
                            coreUsed = core["cores"][0]
                        romInfo = generateOldPlaylistEntry(romsplit[0],
                                                               romsplit[1],
                                                               getRomPath()+getCoreFolder(core),
                                                               core["system"][0],
                                                               coreUsed)
                        playlist.extend(romInfo)
            
            #for line in playlist:
            #    logger.info(line)
            #create playlist file
            if playlist:
                logger.debug("Number of Files Found: "+str(len(playlist)))
                addToPlaylist(core["system"][0], playlist, Settings["makeJsonPlaylists"])
    state = "Playlists: Complete"
def colorToFloat(t):
    nt = ()
    for v in t:
        nt += ((1/255) * v, )
    return nt

sys.argv = [""]  # workaround needed for runpy
# (r, g, b)
BOOL_FALSE_COLOR = colorToFloat((230, 126, 34))
STRING_COLOR = colorToFloat((46, 204, 113))
BOOL_TRUE_COLOR = colorToFloat((41, 128, 185))
TILED_DOUBLE = 1
state = "idle"

logger = 0

Settings = {}
def setup():
    global coresJson
    global Settings
    global logger
    FORMAT = '%(asctime)s:%(levelname)-8s: %(message)s'
    logging.basicConfig(filename='PylaylistMakerLog.log', level=logging.DEBUG, format=FORMAT, datefmt='%m-%d %H:%M')

    logger = logging.getLogger()
    #console = logging.StreamHandler()
    #console.setLevel(logging.INFO)
    #logging.getLogger('').addHandler(console)
    try:
        with open("PyLaylistMaker/systems.json", "r") as coresFile:
            coresJson = json.load(coresFile)
    except Exception as err:
        logger.critical("MISSING systems.json")
        print("MISSING: settings.json")
        print(err)
        import time
        time.sleep(5)
        return 0
    try:
        with open("PyLaylistMaker/settings.json", "r") as SettingsFile:
            Settings = json.load(SettingsFile)
    except Exception as err:
        logger.critical("MISSING: settings.json")
        print("MISSING: settings.json")
        print(err)
        import time
        time.sleep(5)
        return 0
    logger.setLevel(logging.DEBUG if Settings["printDebugLogs"] else logging.INFO)
    logger.debug("setup complete")

def main():
    import imgui
    import imguihelper
    import _nx
    import runpy
    from imgui.integrations.nx import NXRenderer

    renderer = NXRenderer()
    currentDir = os.getcwd()
    while True:
        renderer.handleinputs()

        imgui.new_frame()

        width, height = renderer.io.display_size
        imgui.set_next_window_size(width, height)
        imgui.set_next_window_position(0, 0)
        imgui.begin("", 
            flags=imgui.WINDOW_NO_TITLE_BAR | imgui.WINDOW_NO_RESIZE | imgui.WINDOW_NO_MOVE | imgui.WINDOW_NO_SAVED_SETTINGS
        )
        imgui.text("Welcome to Pylaylist Maker for RetroArch!")
        imgui.text("Touch is supported")
        imgui.text("Settings:")
        imgui.text("RetroArch Path: "+Settings["retroarchPATH"])
        imgui.text("Roms Path: "+Settings["romsPaths"][Settings["indexRomPathUsed"]])
        imgui.text("Playlists Path: "+Settings["playlistsPath"])
        
        imgui.push_style_color(imgui.COLOR_BUTTON, *STRING_COLOR)
        if imgui.button("Toggle Roms Path", width=200, height=60):
            Settings["indexRomPathUsed"] = 0 if Settings["indexRomPathUsed"]==1 else 1
        imgui.pop_style_color(1)
        
        if Settings["useAllExtentions"]:
            imgui.push_style_color(imgui.COLOR_BUTTON, *BOOL_TRUE_COLOR )
        else:
            imgui.push_style_color(imgui.COLOR_BUTTON, *BOOL_FALSE_COLOR )
        if imgui.button("Use All Extentions: "+("True" if Settings["useAllExtentions"] else "False"), width=200, height=60):
            Settings["useAllExtentions"] = not Settings["useAllExtentions"]
        imgui.pop_style_color(1)

        if Settings["useShorthandName"]:
            imgui.push_style_color(imgui.COLOR_BUTTON, *BOOL_TRUE_COLOR )
        else:
            imgui.push_style_color(imgui.COLOR_BUTTON, *BOOL_FALSE_COLOR )
        if imgui.button("Use Shorthand Name: "+("True" if Settings["useShorthandName"] else "False"), width=200, height=60):
            Settings["useShorthandName"] = not Settings["useShorthandName"]
        imgui.pop_style_color(1)

        imgui.text("Commands")
        
        imgui.push_style_color(imgui.COLOR_BUTTON, *STRING_COLOR)
        if imgui.button("Validate/Generate Folders", width=200, height=60):
            validateFolders()
            logger.info("Folders Validated")
            
        imgui.pop_style_color(1)
        imgui.text("THIS WILL ADD A BUNCH OF FOLDERS TO YOUR ROM PATH!")

        imgui.push_style_color(imgui.COLOR_BUTTON, *STRING_COLOR)
        if imgui.button("Generate/Update Playlists", width=200, height=60):
            generatePlaylist()
            logger.info("Complete")
        imgui.pop_style_color(1)
        imgui.text("THIS WILL MODIFY PLAYLISTS, MAKE BACKUPS FIRST!")
        imgui.text("State: "+state+"\n\n\n")
        quitme = False
        imgui.push_style_color(imgui.COLOR_BUTTON, *STRING_COLOR)
        if imgui.button("Quit", width=200, height=60):
            quitme = True
        imgui.pop_style_color(1)
        
        imgui.end()


        imgui.render()
        renderer.render()
        if quitme:
            break
    renderer.shutdown()
    return 0

if __name__ == "__main__":
    try:
        setup()
        main()
    except Exception:
        logging.exception("fatal error")
        raise 
    #generatePlaylist()
