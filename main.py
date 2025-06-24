import sys
import bcrypt
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QStackedLayout
)
from PySide6.QtGui import QFont
from pymongo import MongoClient

# Подключение к MongoDB
client = MongoClient("mongodb+srv://ieven7007:enLm29V3ZMPm1lnu@restaurant.7sxucgj.mongodb.net/?retryWrites=true&w=majority&appName=Restaurant")
db = client["restaurantDB"]
waiters_collection = db["waiters"]

STYLE = """
    QWidget {
        background-color: #f0f0f0;
        font-family: Arial, sans-serif;
        font-size: 14px;
        color: #000000; /* черный текст */
    }
    QLabel#title {
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 20px;
        color: #000000;
    }
    QLineEdit {
        padding: 10px;
        border: 1px solid #aaa;
        border-radius: 5px;
        margin-bottom: 15px;
        background: white;
        font-size: 16px;
    }
    QPushButton {
        background-color: #4CAF50;
        border: none;
        color: white;
        padding: 10px 0;
        border-radius: 5px;
        font-size: 16px;
        font-weight: bold;
        /* cursor: pointer; -- удалено, чтобы не было предупреждений */
    }
    QPushButton:hover {
        background-color: #45a049;
    }
    QPushButton#switchButton {
        background-color: transparent;
        color: #0078d7;
        font-size: 14px;
        font-weight: normal;
        padding: 5px;
        margin-top: 10px;
        border: none;
        text-decoration: underline;
        /* cursor: pointer; -- удалено */
    }
    QPushButton#switchButton:hover {
        color: #005a9e;
    }
"""

class AuthWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Авторизация и регистрация официанта")
        self.setFixedSize(400, 350)
        self.setStyleSheet(STYLE)

        self.stacked_layout = QStackedLayout()

        self.login_widget = self.create_login_widget()
        self.register_widget = self.create_register_widget()

        self.stacked_layout.addWidget(self.login_widget)
        self.stacked_layout.addWidget(self.register_widget)

        self.setLayout(self.stacked_layout)

    def create_login_widget(self):
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Авторизация")
        title.setObjectName("title")
        layout.addWidget(title)

        self.login_login_input = QLineEdit()
        self.login_login_input.setPlaceholderText("Логин")
        layout.addWidget(self.login_login_input)

        self.login_password_input = QLineEdit()
        self.login_password_input.setPlaceholderText("Пароль")
        self.login_password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.login_password_input)

        login_button = QPushButton("Войти")
        login_button.clicked.connect(self.login_waiter)
        layout.addWidget(login_button)

        switch_to_register_btn = QPushButton("Нет аккаунта? Зарегистрироваться")
        switch_to_register_btn.setObjectName("switchButton")
        switch_to_register_btn.clicked.connect(lambda: self.stacked_layout.setCurrentWidget(self.register_widget))
        layout.addWidget(switch_to_register_btn)

        widget.setLayout(layout)
        return widget

    def create_register_widget(self):
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Регистрация")
        title.setObjectName("title")
        layout.addWidget(title)

        self.reg_login_input = QLineEdit()
        self.reg_login_input.setPlaceholderText("Логин")
        layout.addWidget(self.reg_login_input)

        self.reg_password_input = QLineEdit()
        self.reg_password_input.setPlaceholderText("Пароль")
        self.reg_password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.reg_password_input)

        register_button = QPushButton("Зарегистрироваться")
        register_button.clicked.connect(self.register_waiter)
        layout.addWidget(register_button)

        switch_to_login_btn = QPushButton("Уже есть аккаунт? Войти")
        switch_to_login_btn.setObjectName("switchButton")
        switch_to_login_btn.clicked.connect(lambda: self.stacked_layout.setCurrentWidget(self.login_widget))
        layout.addWidget(switch_to_login_btn)

        widget.setLayout(layout)
        return widget

    def login_waiter(self):
        login = self.login_login_input.text().strip()
        password = self.login_password_input.text()

        waiter = waiters_collection.find_one({"login": login})
        if waiter and bcrypt.checkpw(password.encode("utf-8"), waiter["password"]):
            role = "Администратор" if waiter.get("isAdmin") else "Официант"
            QMessageBox.information(self, "Успешно", f"Добро пожаловать, {role} {login}!")
        else:
            QMessageBox.warning(self, "Ошибка", "Неверный логин или пароль.")

    def register_waiter(self):
        login = self.reg_login_input.text().strip()
        password = self.reg_password_input.text()

        if not login or not password:
            QMessageBox.warning(self, "Ошибка", "Заполните все поля.")
            return

        if waiters_collection.find_one({"login": login}):
            QMessageBox.warning(self, "Ошибка", "Официант с таким логином уже существует.")
            return

        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        waiters_collection.insert_one({
            "login": login,
            "password": hashed_password,
            "isAdmin": False
        })
        QMessageBox.information(self, "Успешно", "Официант зарегистрирован.")
        self.stacked_layout.setCurrentWidget(self.login_widget)
        self.reg_login_input.clear()
        self.reg_password_input.clear()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    auth_window = AuthWindow()
    auth_window.show()
    sys.exit(app.exec())
