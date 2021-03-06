import sys
from Client import LoginRegisterForm, WebHandler, MessengerForm, StartConversationForm, InfoForm
from PyQt5 import QtCore, QtWidgets, QtGui
from Crypto.Cipher import AES
import enum
import os


class ConversationType(enum.Enum):
    dialog = 0
    group = 1


class InfoWindow(QtWidgets.QDialog, InfoForm.Ui_Dialog):
    def __init__(self, web_handler, conversation, login):
        super().__init__()
        self.setupUi(self)
        self.web_handler = web_handler
        self.conversation = conversation
        self.login = login
        if self.conversation['conversation_type'] == ConversationType.dialog.value:
            self.addMemberButton.hide()
            self.memberNickname.hide()
            self.label.hide()
            if self.conversation['persons'][0] == self.login:
                self.conversationTitle.setText(self.conversation['persons'][1])
            else:
                self.conversationTitle.setText(self.conversation['persons'][0])
            self.membersList.addItems(self.conversation['persons'])
        else:
            self.conversationTitle.setText(self.conversation['title'])
            self.addMemberButton.clicked.connect(self.addMember)
            self.membersList.addItems(self.web_handler.get_chat_members(self.conversation['_id']))

    def addMember(self):
        result = self.web_handler.add_member_to_chat(self.conversation['_id'], self.memberNickname.text())
        self.dialogWindow = QtWidgets.QMessageBox()
        self.dialogWindow.setStandardButtons(QtWidgets.QMessageBox.Ok)
        self.dialogWindow.setIcon(QtWidgets.QMessageBox.Information)
        self.dialogWindow.setModal(True)
        if result:
            self.dialogWindow.setText('New member successfully added')
            self.membersList.clear()
            self.membersList.addItems(self.web_handler.get_chat_members(self.conversation['_id']))
        else:
            self.dialogWindow.setText('Failed to add new member')
        self.dialogWindow.show()
        self.memberNickname.clear()


class StartConversationWindow(QtWidgets.QDialog, StartConversationForm.Ui_ConversationForm):
    def __init__(self, web_handler):
        super().__init__()
        self.setupUi(self)
        self.web_handler = web_handler
        self.startDialogButton.clicked.connect(self.startDialog)
        self.startChatButton.clicked.connect(self.startChat)
        self.dialogWindow = QtWidgets.QMessageBox()
        self.dialogWindow.setStandardButtons(QtWidgets.QMessageBox.Ok)
        self.dialogWindow.setIcon(QtWidgets.QMessageBox.Information)
        self.dialogWindow.setModal(True)

    def startDialog(self):
        person = self.personNick.text()
        result = self.web_handler.start_dialog(person)
        if result:
            self.dialogWindow.setWindowTitle("Dialog created")
            self.dialogWindow.setText("Dialog started successfully")
            self.dialogWindow.show()
            self.close()
        else:
            self.dialogWindow.setWindowTitle("Couldn't start dialog")
            self.dialogWindow.setText("Failed to start dialog")
            self.dialogWindow.show()

    def startChat(self):
        title = self.chatTitle.text()
        self.web_handler.create_chat(title)
        self.dialogWindow.setWindowTitle("Group chat created")
        self.dialogWindow.setText("Group chat created successfully")
        self.dialogWindow.show()
        self.close()


class MessengerWindow(QtWidgets.QMainWindow, MessengerForm.Ui_MessengerWindow):
    emitter = QtCore.pyqtSignal()

    def __init__(self, web_handler, login):
        super().__init__()
        self.setupUi(self)
        icon = QtGui.QIcon('UI/Upload-Icon-PNG-Image.png')
        self.sendFileButton.setIcon(icon)
        self.chatListUpdateTimer = QtCore.QTimer()
        self.chatListUpdateTimer.timeout.connect(self.updateChatList)
        self.refreshMessagesTimer = QtCore.QTimer()
        self.refreshMessagesTimer.timeout.connect(self.getNewMessages)
        self.activeChat = None
        self.web_handler = web_handler
        self.login = login
        self.chatContainer.hide()
        self.NoChatMessage.show()
        self.updateChatList()
        self.chatsList.itemSelectionChanged.connect(self.selectChat)
        self.chatListUpdateTimer.start(6000)
        self.last_message = 0
        self.sendButton.clicked.connect(self.sendMessage)
        self.startConversationButton.clicked.connect(self.startConversation)
        self.infoButton.clicked.connect(self.showInfo)
        self.sendFileButton.clicked.connect(self.sendFile)

    def sendFile(self):
        filename = QtWidgets.QFileDialog.getOpenFileName(self, 'Select file')[0]
        print(filename)
        with open(filename, 'rb') as file:
            byte_file = file.read()
        filename = os.path.basename(filename)
        if self.activeChat['conversation_type'] == ConversationType.dialog.value:
            result = self.web_handler.send_file_to_dialog(self.activeChat['_id'], filename, byte_file)
        else:
            result = self.web_handler.send_file_to_chat(self.activeChat['_id'], self.activeChat['key'],
                                                        filename, byte_file)
        if result:
            self.getNewMessages()

    def updateChatList(self):
        dialogs = self.web_handler.get_all_dialogs()
        self.chatsList.clear()
        counter = 0
        for dialog in dialogs:
            dialog['conversation_type'] = ConversationType.dialog.value
            dialog_item = QtWidgets.QListWidgetItem()
            dialog_item.setData(QtCore.Qt.UserRole, dialog)
            if dialog['persons'][0] == self.login:
                dialog_item.setText(dialog['persons'][1])
            else:
                dialog_item.setText(dialog['persons'][0])
            self.chatsList.addItem(dialog_item)
            if self.activeChat is not None and self.activeChat['_id'] == dialog['_id']:
                self.chatsList.setCurrentIndex(self.chatsList.indexFromItem(dialog_item))
            counter += 1
        chats = self.web_handler.get_chats()
        for chat in chats:
            chat['conversation_type'] = ConversationType.group.value
            chat_item = QtWidgets.QListWidgetItem()
            chat_item.setData(QtCore.Qt.UserRole, chat)
            chat_item.setText(chat['title'])
            self.chatsList.addItem(chat_item)
            if self.activeChat is not None and self.activeChat['_id'] == chat['_id']:
                self.chatsList.setCurrentIndex(self.chatsList.indexFromItem(chat_item))
            counter += 1

    def selectChat(self):
        selected = self.chatsList.selectedItems()
        if len(selected) > 0:
            if self.activeChat is None or selected[0].data(QtCore.Qt.UserRole)['_id'] != self.activeChat['_id']:
                self.refreshMessagesTimer.stop()
                self.last_message = 0
                self.activeChat = selected[0].data(QtCore.Qt.UserRole)
                for i in reversed(range(self.verticalLayout_4.count())):
                    self.verticalLayout_4.itemAt(i).widget().setParent(None)
                if self.activeChat['conversation_type'] == ConversationType.dialog.value:
                    if self.activeChat['persons'][0] == self.login:
                        self.chatLabel.setText(self.activeChat['persons'][1])
                    else:
                        self.chatLabel.setText(self.activeChat['persons'][0])
                    messages = self.web_handler.get_dialog_messages(self.activeChat['_id'])
                else:
                    self.chatLabel.setText(self.activeChat['title'])
                    messages = self.web_handler.get_chat_messages(self.activeChat['_id'], self.activeChat['key'])
                if len(messages) > 0:
                    for message in messages:
                        self.addMessage(message['sender'], message['content'], message)
                    self.last_message = messages[-1]['_id'] + 1
                self.refreshMessagesTimer.start(3000)
                self.chatContainer.show()
                self.NoChatMessage.hide()

    def addMessage(self, author, message, message_info):
        message_container = QtWidgets.QWidget(self.chatContent)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(message_container.sizePolicy().hasHeightForWidth())
        message_container.setSizePolicy(sizePolicy)
        message_container.setMinimumSize(QtCore.QSize(0, 0))
        verticalLayout_6 = QtWidgets.QVBoxLayout(message_container)
        verticalLayout_6.setContentsMargins(0, -1, 0, -1)
        verticalLayout_6.setSpacing(2)
        nickname_label = QtWidgets.QLabel(message_container)
        nickname_label.setText(author)
        font = QtGui.QFont()
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        nickname_label.setFont(font)
        verticalLayout_6.addWidget(nickname_label)
        message_label = QtWidgets.QLabel(message_container)
        message_label.setText(message)

        if message_info['content_type'] == 1:
            def download_file(argument):
                file = self.web_handler.get_file(message_info['file_id'])
                filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save file')[0]
                print(filename)
                if self.activeChat['conversation_type'] == ConversationType.dialog.value:
                    file = self.web_handler.__decrypt_big_data__(file['file'], self.web_handler.private_key)
                else:
                    cipher = AES.new(self.activeChat['key'], AES.MODE_EAX, nonce=file['nonce'])
                    file = cipher.decrypt(file['file'])
                with open(filename, 'wb') as file_to_write:
                    file_to_write.write(file)
            message_label.mousePressEvent = download_file
            message_label.setStyleSheet("color: rgb(11, 112, 227)")
            message_label.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(message_label.sizePolicy().hasHeightForWidth())
        message_label.setSizePolicy(sizePolicy)
        message_label.setMinimumSize(QtCore.QSize(0, 0))
        font = QtGui.QFont()
        font.setPointSize(10)
        message_label.setFont(font)
        message_label.setWordWrap(True)
        verticalLayout_6.addWidget(message_label, 0, QtCore.Qt.AlignTop)
        self.verticalLayout_4.addWidget(message_container)

    def sendMessage(self):
        message = self.messageField.toPlainText()
        if self.activeChat['conversation_type'] == ConversationType.dialog.value:
            self.web_handler.send_message_to_dialog(self.activeChat['_id'], message)
        else:
            self.web_handler.send_message_to_chat(self.activeChat['_id'], self.activeChat['key'], message)
        self.messageField.clear()
        self.getNewMessages()

    def startConversation(self):
        self.start_conversation_window = StartConversationWindow(self.web_handler)
        self.start_conversation_window.show()

    def getNewMessages(self):
        if self.activeChat['conversation_type'] == ConversationType.dialog.value:
            messages = self.web_handler.get_new_dialog_messages(self.activeChat['_id'], self.last_message)
        else:
            messages = self.web_handler.get_new_chat_messages(self.activeChat['_id'], self.last_message,
                                                              self.activeChat['key'])
        if len(messages) > 0:
            for message in messages:
                self.addMessage(message['sender'], message['content'], message)
            self.last_message = messages[-1]['_id'] + 1

    def showInfo(self):
        self.info_window = InfoWindow(self.web_handler, self.activeChat, self.login)
        self.info_window.show()


class LoginRegisterWindow(QtWidgets.QMainWindow, LoginRegisterForm.Ui_LoginWindow):
    emitter = QtCore.pyqtSignal(str)

    def __init__(self, web_handler):
        super().__init__()
        self.setupUi(self)
        self.web_handler = web_handler
        self.signUpButton.clicked.connect(self.SignUp)
        self.signInButton.clicked.connect(self.SignIn)

    def SignUp(self):
        login = self.loginSignUpField.text()
        password = self.passwordSignUpField.text()
        status = self.web_handler.register(login, password)
        message_box = QtWidgets.QMessageBox()
        message_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        message_box.setIcon(QtWidgets.QMessageBox.Information)
        message_box.setModal(True)
        if status:
            message_box.setWindowTitle("Registration successful")
            message_box.setText("Signed up successfully")
        else:
            message_box.setWindowTitle("Registration failed")
            message_box.setText("Failed to sign up")
        message_box.exec_()

    def SignIn(self):
        login = self.loginSignInField.text()
        password = self.passwordSignInField.text()
        status = self.web_handler.auth(login, password)
        if not status:
            message_box = QtWidgets.QMessageBox()
            message_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
            message_box.setIcon(QtWidgets.QMessageBox.Information)
            message_box.setWindowTitle("Signing in failed")
            message_box.setText("Failed to sign in")
            message_box.setModal(True)
            message_box.exec_()
        else:
            self.emitter.emit(login)


class Controller:
    def __init__(self):
        self.web_handler = WebHandler.Client()
        self.login = None
        self.messenger = None

    def show_login(self):
        self.login = LoginRegisterWindow(self.web_handler)
        self.login.emitter.connect(self.show_messenger)
        self.login.show()

    def show_messenger(self, login):
        self.messenger = MessengerWindow(self.web_handler, login)
        if self.login is not None:
            self.login.close()
        self.messenger.show()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    controller = Controller()
    controller.show_login()
    sys.exit(app.exec_())
