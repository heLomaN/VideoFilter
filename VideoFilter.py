import sys
import os
import cv2
import sqlite3
import configparser
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QFileDialog, QLabel, QListWidget, \
    QListWidgetItem, QHBoxLayout
from PyQt5.QtGui import QPixmap, QImage, QKeyEvent, QColor, QDesktopServices
from PyQt5.QtCore import Qt, QUrl

class RecentDirectoryHandler:
    def __init__(self):
        self.config_file = 'config.ini'

    def get_last_used_directory(self):
        config = configparser.ConfigParser()
        config.read(self.config_file)

        try:
            return config['DEFAULT']['LastDirectory']
        except KeyError:
            return os.getcwd()  # 默认使用当前工作目录

    def save_last_used_directory(self, directory):
        config = configparser.ConfigParser()
        config['DEFAULT'] = {'LastDirectory': directory}
        with open(self.config_file, 'w') as configfile:
            config.write(configfile)
class VideoThumbnailer(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.last_directory = RecentDirectoryHandler()
        self.db_connection = None
        self.to_delete = []

    def initUI(self):
        self.layout = QVBoxLayout()

        self.btnLayout = QHBoxLayout()
        self.previewLayout = QHBoxLayout()

        self.btnOpen = QPushButton('Open Directory', self)
        self.btnOpen.clicked.connect(self.openDirectory)
        self.btnLayout.addWidget(self.btnOpen)

        self.btnPreview = QPushButton('Preview', self)
        self.btnPreview.setEnabled(False)
        self.btnPreview.clicked.connect(self.previewNext)
        self.btnLayout.addWidget(self.btnPreview)

        self.btnDisplayImage = QPushButton('Display Image', self)
        self.btnDisplayImage.setEnabled(False)
        self.btnDisplayImage.clicked.connect(self.displayImage)
        self.btnLayout.addWidget(self.btnDisplayImage)

        self.btnPlay = QPushButton('Play Video', self)
        self.btnPlay.setEnabled(False)
        self.btnPlay.clicked.connect(self.playItem)
        self.btnLayout.addWidget(self.btnPlay)

        self.btnDelete = QPushButton('Delete Selected', self)
        self.btnDelete.clicked.connect(self.deleteSelected)
        self.btnLayout.addWidget(self.btnDelete)
        self.layout.addLayout(self.btnLayout)

        self.listWidget = QListWidget(self)
        self.listWidget.itemClicked.connect(self.listItemClicked)
        self.listWidget.setMaximumWidth(400)
        self.listWidget.setMinimumWidth(200)
        self.previewLayout.addWidget(self.listWidget)

        self.imageLabel = QLabel(self)
        self.imageLabel.setText("Mouse right click to switch between delete and Keep, else to skip")
        self.imageLabel.mouseReleaseEvent = self.imageClicked
        self.imageLabel.setMinimumSize(600, 300)
        self.previewLayout.addWidget(self.imageLabel)
        self.layout.addLayout(self.previewLayout)

        self.setLayout(self.layout)
        self.setGeometry(300, 300, 1024, 768)
        self.setWindowTitle('Video Thumbnailer')
        self.show()

    def openDirectory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory", self.last_directory.get_last_used_directory())
        if dir_path:
            self.last_directory.save_last_used_directory(dir_path)
            self.processDirectory(dir_path)

    def processDirectory(self, root):
        preview_dir = os.path.join(root, '.preview')
        os.makedirs(preview_dir, exist_ok=True)
        db_path = os.path.join(preview_dir, 'thumbnails.sqldb')
        previewCreated = os.path.exists(db_path)
        self.setupDatabase(db_path)
        if not previewCreated:
            for subdir, dirs, files in os.walk(root):
                for file in files:
                    filepath = os.path.join(subdir, file)
                    if '.del' not in filepath and filepath.lower().endswith((".mp4", ".wmv", ".avi", ".mkv", ".avi", ".mpg", ".flv")):
                        self.generateThumbnail(filepath, preview_dir)

        self.loadVideoList()

    def setupDatabase(self, db_path):
        self.db_connection = sqlite3.connect(db_path)
        cursor = self.db_connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Thumbnails (
                id INTEGER PRIMARY KEY,
                video_path TEXT,
                thumbnail_path TEXT
            )
        ''')
        self.db_connection.commit()

    def generateThumbnail(self, video_path, preview_dir):
        cap = cv2.VideoCapture(video_path)
        length = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frames_to_capture = [length // 6 * i for i in range(1, 7)]
        images = []

        for frame_number in frames_to_capture:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            if ret:
                images.append(frame)

        cap.release()

        thumbnail_path = os.path.join(preview_dir, os.path.basename(video_path) + '.jpg')
        self.saveConcatenatedImages(images, thumbnail_path)
        self.saveThumbnailRecord(video_path, thumbnail_path)

    def saveConcatenatedImages(self, images, thumbnail_path):
        if images:
            while len(images) < 6:
                images.append(images[-1])
        concatenated_image = cv2.vconcat([cv2.hconcat(images[0:3]), cv2.hconcat(images[3:6])])
        # do not support utf8 path
        # cv2.imwrite(thumbnail_path, concatenated_image)
        is_success, im_buf_arr = cv2.imencode(".jpg", concatenated_image)
        im_buf_arr.tofile(thumbnail_path)

    def saveThumbnailRecord(self, video_path, thumbnail_path):
        cursor = self.db_connection.cursor()
        cursor.execute('INSERT INTO Thumbnails (video_path, thumbnail_path) VALUES (?, ?)', (video_path, thumbnail_path))
        self.db_connection.commit()

    def loadVideoList(self):
        cursor = self.db_connection.cursor()
        cursor.execute('SELECT video_path FROM Thumbnails')
        videos = cursor.fetchall()
        self.listWidget.clear()
        for video in videos:
            self.listWidget.addItem(video[0])

        self.btnDisplayImage.setEnabled(True)
        self.btnPreview.setEnabled(True)
        self.btnPlay.setEnabled(True)

    def listItemClicked(self):
        thumbnail_path = self.getCurrentItemThumbnailPath()
        self.updateThumbnail(thumbnail_path)

    def getCurrentItemThumbnailPath(self):
        video_path = self.listWidget.currentItem().text()
        thumbnail_path = self.getThumbnailpathFromVideoPath(video_path)
        return thumbnail_path

    def getThumbnailpathFromVideoPath(self, video_path):
        cursor = self.db_connection.cursor()
        cursor.execute('SELECT thumbnail_path FROM Thumbnails WHERE video_path=?', (video_path,))
        return cursor.fetchone()[0]
    def displayImage(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.getCurrentItemThumbnailPath()))

    def playItem(self):
        video_path = self.listWidget.currentItem().text()
        QDesktopServices.openUrl(QUrl.fromLocalFile(video_path))

    def imageClicked(self, event):
        if not self.listWidget.currentItem():
            return None
        video_path = self.listWidget.currentItem().text()
        if event.button() == Qt.RightButton:
            if video_path not in self.to_delete:
                self.to_delete.append(video_path)
                self.listWidget.currentItem().setBackground(Qt.red)
            else:
                self.to_delete.remove(video_path)
                self.listWidget.currentItem().setBackground(Qt.white)
        self.previewNext()

    def updateThumbnail(self, thumbnail_path):
        pixmap = QPixmap(thumbnail_path)
        scaled_pixmap = pixmap.scaled(self.imageLabel.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.imageLabel.setPixmap(scaled_pixmap)
    def previewNext(self):
        current_row = self.listWidget.currentRow()
        next_row = current_row + 1 if current_row + 1 < self.listWidget.count() else 0
        self.listWidget.setCurrentRow(next_row)
        self.listItemClicked()

    def deleteSelected(self):
        del_dir = os.path.join(self.last_directory.get_last_used_directory(), '.del')
        os.makedirs(del_dir, exist_ok=True)

        # 获取与待删除视频路径对应的数据库记录
        conn = self.db_connection
        cursor = conn.cursor()

        for video_path in self.to_delete:
            # 移动缩略图到.del文件夹
            thumbnail_path = self.getThumbnailpathFromVideoPath(video_path)
            os.rename(thumbnail_path, os.path.join(del_dir, os.path.basename(thumbnail_path)))
            os.rename(video_path, os.path.join(del_dir, os.path.basename(video_path)))
            # 从数据库中删除记录
            cursor.execute('DELETE FROM Thumbnails WHERE video_path=?', (video_path,))
            conn.commit()

        self.to_delete.clear()
        self.loadVideoList()
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = VideoThumbnailer()
    sys.exit(app.exec_())