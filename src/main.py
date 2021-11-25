# Copyright (C) 2021 - Abhijit Nandy
# Media player
# Steps:
# pip install numpy
# pip install soundfile
# pip install sounddevice
# pip install pycaw
# > sudo apt-get install python-alsaaudio (on linux cmd shell)
# pip install pyqt5
# python main.py

# Std
import sys
import platform
import enum
import json
import argparse
from time import sleep
from datetime import datetime
import queue
import threading
import sounddevice as sd
import soundfile as sf

# Platform specific volume control
if platform.system() == "Windows":
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    import math
else:
    import alsaaudio

# PyQt 5
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
from PyQt5.QtWidgets import QPushButton, QListWidget
from PyQt5.QtWidgets import QLabel, QSlider
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui     import QPixmap
from PyQt5.QtCore    import Qt
from PyQt5.QtCore    import pyqtSignal


# -------------------------------------------------------------------
# Settings
APP_NAME = "Media Player"

# Audio
PLAYBACK_DEVICE_NUMBER = 8
BUFFER_SIZE = 20
BLOCK_SIZE = 2048
DATA_TYPE = "float32"
NUM_CHANNELS = 1  # 2 does not work
OUTPUT_STREAM_SAMPLE_RATE = 48000
MAX_AUDIO_THREAD_STOP_WAIT_ITERATIONS = 1000

# Image paths
PATH_VISUALIZATION_ANIM = "../resources/images/audioanim.jpg"


# For windows
g_volume = None
if platform.system() == "Windows":
    # Get default audio device using PyCAW
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    g_volume = cast(interface, POINTER(IAudioEndpointVolume))


#---------------------------------------------------------------------
# Return codes, negative codes for errors
# 0 or positive for some form of success
class RC(enum.IntEnum):
    SUCCESS = 0
    NO_FILE_SELECTED = 1
    FINISHED = 2
    FAILED = 3
    #----------------------------
    E_FAIL = -1
    E_INVALID_FILE_PATH = -2


#---------------------------------------------------------------------
# Return codes, negative codes for errors
# 0 or positive for some form of success
class MsgBox(enum.IntEnum):
    INFO = 1
    WARN = 2
    ERROR = 3


#---------------------------------------------------------------------
# Player state
class PlayerState(enum.IntEnum):
    STOPPED = 0
    PLAYING = 1
    PAUSED  = 2

g_previousPlayerState = None
g_playerState = PlayerState.STOPPED

g_audioThreadRunning = False

#---------------------------------------------------------------------
# Logging



#---------------------------------------------------------------------
def showMsg(strTitle, strMsg, msgType):
    msgBox = QMessageBox()
    if msgType == MsgBox.INFO:
        msgBox.setIcon(QMessageBox.Information)
    elif msgType == MsgBox.WARN:
        msgBox.setIcon(QMessageBox.Warning)
    elif msgType == MsgBox.ERROR:
        msgBox.setIcon(QMessageBox.Critical)
    msgBox.setWindowTitle(strTitle)
    msgBox.setText(strMsg)
    msgBox.setStandardButtons(QMessageBox.Ok) #  | QMessageBox.Cancel)
    # msgBox.buttonClicked.connect(msgButtonClick)
    return msgBox.exec()
    # if returnValue == QMessageBox.Ok:
    #   print('OK clicked')

#---------------------------------------------------------------------
class FileBrowser:
    """Generic file browser"""
    # Select audio file
    def selectFile(parent, strTitle, strDir, strFilter):
        # strFilter = "Audio files (*.wav *.mp3)"
        # print(parent, strTitle, strDir, strFilter)
        strFilter = "Audio files (*.wav *.mp3)"
        # fileDialog = QFileDialog(parent, strTitle, strDir, strFilter)
        # strFilter = "Audio files (*.wav *.mp3)"
        # dlg = QFileDialog(parent, strTitle, strDir, strFilter)
        # if dlg.exec_():
        #       lstFilenames = dlg.selectedFiles()
        #     print(lstFilenames)
        #     return lstFilenames
        # fileDialog.setFileMode(QFileDialog.ExistingFiles)
        lstFilenames, _ = QFileDialog.getOpenFileNames(parent, strTitle, "", strFilter)
        if lstFilenames and len(lstFilenames) > 0:
            # print(lstFilenames)
            return lstFilenames
        # options = QFileDialog.Options()
        # options |= QFileDialog.DontUseNativeDialog
        # fileName, _ = QFileDialog.getOpenFileNames(parent, "QFileDialog.getOpenFileName()", "",
        #                                           "All Files (*);;Python Files (*.py)")


#---------------------------------------------------------------------
def setVolume(levelPercent):
    if platform.system() == "Windows":
        # Get current volume
        currentVolumeDb = g_volume.GetMasterVolumeLevel()
        g_volume.SetMasterVolumeLevel(currentVolumeDb - 6.0, None)
        # NOTE: -6.0 dB = half volume !
    else:
        # Linux, Mac, other OS
        m = alsaaudio.Mixer()
        # current_volume = m.getvolume()  # Get the current Volume
        m.setvolume(levelPercent)  # Set the volume to 70% if level=70



#---------------------------------------------------------------------

# def createRunningOutputStream(deviceIndex):
#     print("Opening output stream for device:", deviceIndex)
#     output = sd.OutputStream(
#         device = deviceIndex,
#         dtype  = DATA_TYPE,
#         samplerate = OUTPUT_STREAM_SAMPLE_RATE,
#         channels   = NUM_CHANNELS
#     )
#     output.start()
#     return output

def setPlayerState(newState):
    global g_previousPlayerState, g_playerState
    g_previousPlayerState = g_playerState
    g_playerState = newState

def playAudioOnDevice(deviceNum, strAudioFilePath):
    global g_previousPlayerState, g_playerState, g_audioThreadRunning
    g_audioThreadRunning = True
    # Local queue created every time
    q = queue.Queue(maxsize=BUFFER_SIZE)
    event = threading.Event()
    # Local nested closure
    def callback(outdata, frames, time, status):
        # print("callback")
        assert frames == BLOCK_SIZE
        if status.output_underflow:
            print('Output underflow: increase blocksize?', file=sys.stderr)
            raise sd.CallbackAbort
        assert not status
        try:
            data = q.get_nowait()
        except queue.Empty:
            print('Buffer is empty: increase buffersize?', file=sys.stderr)
            raise sd.CallbackAbort
        if len(data) < len(outdata):
            # Last blk
            outdata[:len(data)] = data
            outdata[len(data):] = b'\x00' * (len(outdata) - len(data))
            raise sd.CallbackStop
        else:
            outdata[:] = data
    # Actual code to initiate & control playback
    try:
        with sf.SoundFile(strAudioFilePath) as f:
            for _ in range(BUFFER_SIZE):
                data = f.buffer_read(BLOCK_SIZE, dtype=DATA_TYPE)
                if not data:
                    break
                q.put_nowait(data)  # Pre-fill queue
            stream = sd.RawOutputStream(
                samplerate=f.samplerate, blocksize=BLOCK_SIZE,
                device=deviceNum, channels=NUM_CHANNELS, dtype=DATA_TYPE,
                callback=callback, finished_callback=event.set)
            with stream:
                timeout = BLOCK_SIZE * BUFFER_SIZE/ f.samplerate
                while data:
                    if g_playerState == PlayerState.PLAYING:
                        if g_previousPlayerState == PlayerState.PAUSED:
                            stream.start()
                        data = f.buffer_read(BLOCK_SIZE, dtype=DATA_TYPE)
                        q.put(data, timeout=timeout)
                    elif g_playerState == PlayerState.STOPPED:
                        stream.stop()
                        # print("Player stopped")
                        break
                    elif g_playerState == PlayerState.PAUSED:
                        # print("Player paused")
                        stream.stop()
                event.wait()  # Wait until playback is finished
                setPlayerState(PlayerState.STOPPED)
    except queue.Full:
        # A timeout occurred, i.e. there was an error in the callback
        print("Queue full")
    except Exception as e:
        print(type(e).__name__ + ': ' + str(e))
    finally:
        g_audioThreadRunning = False

#---------------------------------------------------------------------
# Uses model-view
class TrackInfoWithVolumeControlWidget(QWidget):
    """Track info widget"""
    def __init__(self, model=None, ctrlr=None, parent=None):
        QWidget.__init__(self, parent=parent)
        layMain = QHBoxLayout(self)
        self._pixmapAudioAnim = QPixmap(PATH_VISUALIZATION_ANIM)
        self._lblAudioAnim = QLabel()
        self._lblAudioAnim.setPixmap(self._pixmapAudioAnim)
        layTrackInfo = QVBoxLayout(self)
        self._lblTrackName = QLabel("No track playing")
        self._sliderVolume = QSlider(Qt.Horizontal)
        self._sliderVolume.setMinimum(0)
        self._sliderVolume.setMaximum(100)
        self._sliderVolume.setValue(20)
        self._sliderVolume.setTickPosition(QSlider.TicksBelow)
        self._sliderVolume.setTickInterval(5)
        self._sliderVolume.valueChanged.connect(self.volumeChanged)
        # Add widgets to layouts
        layTrackInfo.addWidget(self._lblTrackName)
        layTrackInfo.addWidget(self._sliderVolume)
        layMain.addWidget(self._lblAudioAnim)
        layMain.addLayout(layTrackInfo)
        # Connect track changed signal
        parent.sigTrackChanged.connect(self.trackChanged)

    def volumeChanged(self, value):
        setVolume(value)

    def trackChanged(self, strTrackName):
        self._lblTrackName.setText(strTrackName)


#---------------------------------------------------------------------
# Uses model-view
class PlayListWidget(QWidget):
    """Play list widget"""
    # Signals
    # List of media added as strings & total items currently
    sigMediaAdded         = pyqtSignal(list, int, name='sigMediaAdded')
    # List of media removed as strings & total items currently
    sigMediaRemoved       = pyqtSignal(list, int, name='sigMediaRemoved')
    # TODO: Index of item clicked - view needs to get path from model
    # sigMediaPlayRequested = pyqtSignal(int,  name='sigMediaPlayRequested')
    # Temp: Completed path of clicked item as str till we have a model in place
    sigMediaPlayRequested = pyqtSignal(str, name='sigMediaPlayRequested')

    def __init__(self, model=None, ctrlr=None, parent=None):
        QWidget.__init__(self, parent=parent)
        layPlayList = QVBoxLayout(self)
        self._lwMediaList = QListWidget()
        layPlayList.addWidget(self._lwMediaList)
        btnsLayout = QHBoxLayout()
        self._btnAdd = QPushButton("Add")
        self._btnAdd.clicked.connect(self.addMedia)
        self._btnRem = QPushButton("Remove")
        self._btnRem.clicked.connect(self.removeMedia)
        btnsLayout.addWidget(self._btnAdd)
        btnsLayout.addWidget(self._btnRem)
        layPlayList.addLayout(btnsLayout)
        self._lwMediaList.doubleClicked.connect(lambda: self.sigMediaPlayRequested.emit(""))

    def addMedia(self):
        """Add media to playlist"""
        lstFilenames = FileBrowser.selectFile(self, "Select Audio File", "Desktop", "Audio files (*.wav *.mp3)")
        # print(lstFilenames)
        if lstFilenames and len(lstFilenames) > 0:
            # self.playerModel.addMedia(lstFilenames)
            # TODO: Update only file names in media list, not full paths: do in separate thread for long lists
            numItems = self._lwMediaList.count()
            self._lwMediaList.addItems(lstFilenames)
            # print("self.parent:", self, self.parent())
            if numItems == 0:
                self._lwMediaList.setCurrentRow(0)
            self.sigMediaAdded.emit(lstFilenames, self._lwMediaList.count())
            return RC.SUCCESS
        return RC.NO_FILE_SELECTED

    def removeMedia(self):
        """Remove media from playlist"""
        lstFilenamesRemoved = []
        for item in self._lwMediaList.selectedItems():
            self._lwMediaList.takeItem(self._lwMediaList.row(item))
            lstFilenamesRemoved.append(item.text())
        self.sigMediaRemoved.emit(lstFilenamesRemoved, self._lwMediaList.count())

    def getSelectedMedia(self):
        # The ctrlr will look up the media path in the model & play it
        lstSelectedItems = self._lwMediaList.selectedItems()
        # print("lstSelectedItems:", lstSelectedItems)
        if lstSelectedItems and len(lstSelectedItems) > 0:
            return lstSelectedItems[0].text()

#---------------------------------------------------------------------
# Model
class PlayerModel:
    pass


#---------------------------------------------------------------------
# Controller
class PlayerCtrlr:
    pass

#---------------------------------------------------------------------
# View
class PlayerView(QDialog):
    """Player view"""
    # Signal for currently playing track changed - will be emitted by model later, now view emits it
    sigTrackChanged = pyqtSignal(str, name='sigTrackChanged')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        # Main layout
        dlgLayout = QVBoxLayout()
        # Play
        self._btnPlay = QPushButton("P")
        self._btnPlay.setToolTip("Play selected track")
        self._btnPlay.setEnabled(False)
        self._btnPlay.clicked.connect(self.playAudio)
        # Pause
        self._btnPause = QPushButton("||")
        self._btnPause.setToolTip("Pause currently playing track")
        self._btnPause.setEnabled(False)
        self._btnPause.clicked.connect(self.pauseAudio)
        # Stop
        self._btnStop = QPushButton("S")
        self._btnStop.setToolTip("Stop currently playing track")
        self._btnStop.setEnabled(False)
        self._btnStop.clicked.connect(self.stopAudio)
        # Previous
        self._btnPrevious = QPushButton("|<")
        self._btnPrevious.setToolTip("Play previous track in playlist")
        self._btnPrevious.setEnabled(False)
        self._btnPrevious.clicked.connect(self.previousTrack)
        # Next
        self._btnNext = QPushButton(">|")
        self._btnNext.setToolTip("Play next track in playlist")
        self._btnNext.setEnabled(False)
        self._btnNext.clicked.connect(self.nextTrack)
        # Shuffle
        self._btnShuffle = QPushButton("~")
        self._btnShuffle.setToolTip("Shuffle and play tracks in playlist")
        self._btnShuffle.setEnabled(False)
        self._btnShuffle.clicked.connect(self.shuffleTracks)
        # Loop
        self._btnLoopCurrentTrack = QPushButton("O")
        self._btnLoopCurrentTrack.setToolTip("Loop currently playing track")
        self._btnLoopCurrentTrack.setEnabled(False)
        self._btnLoopCurrentTrack.clicked.connect(self.loopCurrentTrack)
        # Add buttons to layout
        btnsLayout = QHBoxLayout()
        btnsLayout.addWidget(self._btnPrevious)
        btnsLayout.addWidget(self._btnPlay)
        btnsLayout.addWidget(self._btnPause)
        btnsLayout.addWidget(self._btnStop)
        btnsLayout.addWidget(self._btnNext)
        btnsLayout.addWidget(self._btnShuffle)
        btnsLayout.addWidget(self._btnLoopCurrentTrack)
        # Play list
        self._playlist = PlayListWidget(parent=self)
        # Add to main layout
        # dlgLayout.addLayout(fileBrowserLayout)
        self._trackInfo = TrackInfoWithVolumeControlWidget(parent=self)
        dlgLayout.addWidget(self._trackInfo)
        dlgLayout.addLayout(btnsLayout)
        dlgLayout.addWidget(self._playlist)
        self.setLayout(dlgLayout)
        # signals
        self._playlist.sigMediaAdded.connect(self.playlistMediaAdded)
        self._playlist.sigMediaPlayRequested.connect(self.playlistMediaPlayRequested)

    def closeEvent(self, evnt):
        setPlayerState(PlayerState.STOPPED)

    # Play audio
    def playAudio(self):
        global g_playerState
        if  g_playerState == PlayerState.STOPPED:
            # strFilePath = self._leditFilePath.text()
            strSelectedPath = self._playlist.getSelectedMedia()
            if strSelectedPath:
                strSelectedPath = strSelectedPath.strip()
                if not strSelectedPath:
                    print("Invalid file path")
                    showMsg(APP_NAME, "Invalid file path", MsgBox.ERROR)
                    return RC.E_INVALID_FILE_PATH
                # play
                # data, fs = sf.read(strSelectedPath, dtype="float32")
                # sd.stop()
                # sd.play(data, fs)
                thrd = threading.Thread(target=playAudioOnDevice, args=[PLAYBACK_DEVICE_NUMBER, strSelectedPath])
                thrd.start()
                # thrd.join()
                self.sigTrackChanged.emit(strSelectedPath)
            else:
                print("Empty file path")
                showMsg(APP_NAME, "Empty file path", MsgBox.ERROR)
                return RC.E_INVALID_FILE_PATH
        # Audio thread started successfully, switching now from stopped or paused state
        self._btnPlay.setEnabled(False)
        self._btnPause.setEnabled(True)
        self._btnStop.setEnabled(True)
        setPlayerState(PlayerState.PLAYING)
        return RC.SUCCESS

    def stopAudio(self):
        self._btnPlay.setEnabled(True)
        self._btnPause.setEnabled(False)
        self._btnStop.setEnabled(False)
        setPlayerState(PlayerState.STOPPED)
        # sd.stop()

    def pauseAudio(self):
        self._btnPlay.setEnabled(True)
        self._btnPause.setEnabled(False)
        setPlayerState(PlayerState.PAUSED)

    def previousTrack(self):
        pass

    def nextTrack(self):
        pass

    def shuffleTracks(self):
        pass

    def loopCurrentTrack(self):
        pass

    def enableTrackCtrl(self):
        pass

    # Play audio
    def playlistMediaAdded(self):
        self._btnPlay.setEnabled(True)

    def playlistMediaPlayRequested(self):
        global g_audioThreadRunning
        self.stopAudio()
        sleep(0.20)
        numTries = 0
        while(g_audioThreadRunning):
            sleep(0.20)     # this sleep() is needed or this thread will hog CPU
            numTries += 1
            if numTries > MAX_AUDIO_THREAD_STOP_WAIT_ITERATIONS:
                print("Failed to stop audio thread". numTries)
                return RC.E_FAIL
        print(f"Stopped audio thread in {numTries} tries")
        self.playAudio()
        return RC.SUCCESS

#---------------------------------------------------------------------


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # createRunningOutputStream(PLAYBACK_DEVICE_NUMBER)
    dlg = PlayerView()
    dlg.show()
    sys.exit(app.exec_())