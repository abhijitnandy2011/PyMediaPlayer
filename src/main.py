# Copyright (C) 2021 - Abhijit Nandy
# Media player

import sys
import sounddevice as sd
import soundfile as sf

# PyQt 5
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtWidgets import QLineEdit, QPushButton, QListView
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout


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
        self.setWindowTitle('Media Player')
        # Main layout
        dlgLayout = QVBoxLayout()
        # File browse
        fileBrowserLayout = QHBoxLayout()
        self._leditFilePath = QLineEdit()
        self._btnBrowse = QPushButton("Browse")
        fileBrowserLayout.addWidget(self._leditFilePath)
        fileBrowserLayout.addWidget(self._btnBrowse)
        self._btnBrowse.clicked.connect(self.selectFile)
        # Buttons layout
        btnsLayout = QHBoxLayout()
        self_btnPlay = QPushButton("Play")
        self_btnPlay.clicked.connect(self.playAudio)
        self_btnStop = QPushButton("Stop")
        self_btnStop.clicked.connect(self.stopAudio)
        btnsLayout.addWidget(self_btnPlay)
        btnsLayout.addWidget(self_btnStop)
        # Play list
        playlistView = QListView()
        # Add to main layout
        dlgLayout.addLayout(fileBrowserLayout)
        dlgLayout.addLayout(btnsLayout)
        dlgLayout.addWidget(playlistView)
        self.setLayout(dlgLayout)

    # Select audio file
    def selectFile(self):
        strFilter = "Audio files (*.wav *.mp3)"
        dlg = QFileDialog(self, "Select Audio File", "Desktop", strFilter)
        if dlg.exec_():
            lstFilenames = dlg.selectedFiles()
            print(lstFilenames)
            self._leditFilePath.setText(lstFilenames[0])

    # Play audio
    def playAudio(self):
        strFilePath = self._leditFilePath.text()
        strFilePath = strFilePath.strip()
        if not strFilePath:
            print("Invalid file path")
            return -1
        # play
        data, fs = sf.read(strFilePath, dtype="float32")
        sd.play(data, fs)
        return 0

    # Stop audio
    def stopAudio(self):
        sd.stop()


#---------------------------------------------------------------------

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dlg = PlayerView()
    dlg.show()
    sys.exit(app.exec_())