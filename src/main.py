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
from PyQt5.QtWidgets import QLineEdit, QPushButton, QListWidget
from PyQt5.QtWidgets import QLabel, QSlider
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui     import QPixmap
from PyQt5.QtCore    import Qt


# -------------------------------------------------------------------
# Settings
APP_NAME = "Media Player"


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
        print(parent, strTitle, strDir, strFilter)
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
# Uses model-view
class TrackInfoWithVolumeControlWidget(QWidget):
    """Play list widget"""
    def __init__(self, model=None, ctrlr=None, parent=None):
        QWidget.__init__(self, parent=parent)
        layMain = QHBoxLayout(self)
        self._pixmapAudioAnim = QPixmap("../resources/images/audioanim.jpg")
        self._lblAudioAnim = QLabel()
        self._lblAudioAnim.setPixmap(self._pixmapAudioAnim)

        layTrackInfo = QVBoxLayout(self)
        self._lblTrackName = QLabel("Track 1")
        self._sliderVolume = QSlider(Qt.Horizontal)
        self._sliderVolume.setMinimum(0)
        self._sliderVolume.setMaximum(100)
        self._sliderVolume.setValue(20)
        self._sliderVolume.setTickPosition(QSlider.TicksBelow)
        self._sliderVolume.setTickInterval(5)
        self._sliderVolume.valueChanged.connect(self.volumeChanged)

        layTrackInfo.addWidget(self._lblTrackName)
        layTrackInfo.addWidget(self._sliderVolume)
        # self._btnRem = QPushButton("Rem")
        # self._btnRem.clicked.connect(self.removeMedia)
        layMain.addWidget(self._lblAudioAnim)
        layMain.addLayout(layTrackInfo)

    def addMedia(self):
        """Add media to playlist"""
        lstFilenames = FileBrowser.selectFile(self, "Select Audio File", "Desktop", "Audio files (*.wav *.mp3)")
        if lstFilenames and len(lstFilenames) > 0:
            # self.playerModel.addMedia(lstFilenames)
            # TODO: Update only file names in media list, not full paths: do in separate thread for long lists
            self.lwMediaList.addItems(lstFilenames)
            return RC.SUCCESS
        return RC.NO_FILE_SELECTED

    def removeMedia(self):
        """Remove media from playlist"""
        for item in self.lview.selectedItems():
            self.lwMediaList.takeItem(self.lwMediaList.row(item))

    def volumeChanged(self, value):
        setVolume(value)


#---------------------------------------------------------------------
# Uses model-view
class PlayListWidget(QWidget):
    """Play list widget"""
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

    def addMedia(self):
        """Add media to playlist"""
        lstFilenames = FileBrowser.selectFile(self, "Select Audio File", "Desktop", "Audio files (*.wav *.mp3)")
        print(lstFilenames)
        if lstFilenames and len(lstFilenames) > 0:
            # self.playerModel.addMedia(lstFilenames)
            # TODO: Update only file names in media list, not full paths: do in separate thread for long lists
            numItems = self._lwMediaList.count()
            self._lwMediaList.addItems(lstFilenames)
            if numItems == 0:
                self._lwMediaList.setCurrentRow(0)
            return RC.SUCCESS
        return RC.NO_FILE_SELECTED

    def removeMedia(self):
        """Remove media from playlist"""
        for item in self._lwMediaList.selectedItems():
            self._lwMediaList.takeItem(self._lwMediaList.row(item))

    def getSelectedMedia(self):
        # The ctrlr will look up the media path in the model & play it
        lstSelectedItems = self._lwMediaList.selectedItems()
        print("lstSelectedItems:", lstSelectedItems)
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        # Main layout
        dlgLayout = QVBoxLayout()
        # File browse
        # fileBrowserLayout = QHBoxLayout()
        # self._leditFilePath = QLineEdit()
        # self._btnBrowse = QPushButton("Browse")
        # fileBrowserLayout.addWidget(self._leditFilePath)
        # fileBrowserLayout.addWidget(self._btnBrowse)
        # self._btnBrowse.clicked.connect(self.selectFile)
        # Buttons layout
        btnsLayout = QHBoxLayout()
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
        # Add buttons
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

    # Play audio
    def playAudio(self):
        # strFilePath = self._leditFilePath.text()
        strSelectedPath = self._playlist.getSelectedMedia()
        if strSelectedPath:
            strSelectedPath = strSelectedPath.strip()
            if not strSelectedPath:
                print("Invalid file path")
                showMsg(APP_NAME, "Invalid file path", MsgBox.ERROR)
                return RC.E_INVALID_FILE_PATH
            # play
            data, fs = sf.read(strSelectedPath, dtype="float32")
            sd.stop()
            sd.play(data, fs)
            return RC.SUCCESS
        showMsg(APP_NAME, "Invalid file path", MsgBox.ERROR)
        return RC.E_INVALID_FILE_PATH

    # Stop audio
    def stopAudio(self):
        sd.stop()

    def pauseAudio(self):
        pass

    def previousTrack(self):
        pass

    def nextTrack(self):
        pass

    def shuffleTracks(self):
        pass

    def loopCurrentTrack(self):
        pass


#---------------------------------------------------------------------

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dlg = PlayerView()
    dlg.show()
    sys.exit(app.exec_())