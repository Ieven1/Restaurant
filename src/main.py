import sys
import re
from datetime import datetime, date, time
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QTime
from pymongo import MongoClient
from bson.objectid import ObjectId

# Подключение к БД
uri = "mongodb+srv://ieven7007:enLm29V3ZMPm1lnu@restaurant.7sxucgj.mongodb.net/?retryWrites=true&w=majority&appName=Restaurant"
client = MongoClient(uri)
db = client["restaurantDB"]

# Коллекции
waiter_collection = db.waiters
table_collection = db.restaurantTables
reservation_collection = db.reservations
customer_collection = db.customers
menu_collection = db.menuItems
order_collection = db.orders
receipt_collection = db.receipts

# --- Окно авторизации / регистрации ---
class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Авторизация")
        self.resize(300, 150)
        layout = QVBoxLayout(self)

        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("Логин")
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Пароль")
        self.pass_input.setEchoMode(QLineEdit.Password)

        btn_login = QPushButton("Войти")
        btn_register = QPushButton("Регистрация")

        layout.addWidget(self.login_input)
        layout.addWidget(self.pass_input)
        layout.addWidget(btn_login)
        layout.addWidget(btn_register)

        btn_login.clicked.connect(self.login)
        btn_register.clicked.connect(self.register)

    def login(self):
        login = self.login_input.text().strip()
        password = self.pass_input.text().strip()

        # Проверка на латиницу и длину
        if not re.fullmatch(r'[A-Za-z0-9]{4,}', login):
            QMessageBox.warning(self, "Ошибка", "Логин должен быть на латинице и не менее 4 символов")
            return
        if not re.fullmatch(r'[A-Za-z0-9]{4,}', password):
            QMessageBox.warning(self, "Ошибка", "Пароль должен быть на латинице и не менее 4 символов")
            return

        user = waiter_collection.find_one({"login": login, "password": password})
        if user:
            self.main_window = MainWindow(user)
            self.main_window.show()
            self.close()
        else:
            QMessageBox.warning(self, "Ошибка", "Неверный логин или пароль")

    def register(self):
        login = self.login_input.text().strip()
        password = self.pass_input.text().strip()

        # Проверка на латиницу и длину
        if not re.fullmatch(r'[A-Za-z0-9]{4,}', login):
            QMessageBox.warning(self, "Ошибка", "Логин должен быть на латинице и не менее 4 символов")
            return
        if not re.fullmatch(r'[A-Za-z0-9]{4,}', password):
            QMessageBox.warning(self, "Ошибка", "Пароль должен быть на латинице и не менее 4 символов")
            return

        if waiter_collection.find_one({"login": login}):
            QMessageBox.warning(self, "Ошибка", "Пользователь с таким логином уже существует")
            return

        waiter_collection.insert_one({
            "login": login,
            "password": password,
            "isAdmin": False
        })
        QMessageBox.information(self, "Успешно", "Пользователь зарегистрирован")


# --- Главное окно ---
class MainWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.setWindowTitle(f"Ресторан — Пользователь: {user['login']}")
        self.resize(1000, 700)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tables_tab = TablesTab(is_admin=user.get("isAdmin", False))
        self.reservations_tab = ReservationsTab()
        self.orders_tab = OrdersTab(user)
        self.receipts_tab = ReceiptsTab()
        self.menu_tab = MenuTab(is_admin=user.get("isAdmin", False))  # Передаем флаг

        self.tabs.addTab(self.tables_tab, "Столы")
        self.tabs.addTab(self.reservations_tab, "Бронирования")
        self.tabs.addTab(self.orders_tab, "Заказы")
        self.tabs.addTab(self.receipts_tab, "Счета")
        self.tabs.addTab(self.menu_tab, "Меню")  # Добавляем вкладку меню

        # Обновление данных между вкладками (пример)
        self.reservations_tab.reservation_created.connect(self.tables_tab.load_tables)
        self.orders_tab.order_updated.connect(self.reservations_tab.load_reservations)
        self.orders_tab.receipt_created.connect(self.receipts_tab.load_receipts)
        self.receipts_tab.receipt_paid.connect(self.orders_tab.load_orders)  # Новая строка

        # Кнопка выхода
        btn_logout = QPushButton("Выйти из аккаунта")
        btn_logout.clicked.connect(self.logout)
        self.addToolBar(Qt.TopToolBarArea, self._make_toolbar(btn_logout))

    def _make_toolbar(self, btn_logout):
        toolbar = QToolBar()
        toolbar.addWidget(btn_logout)
        return toolbar

    def logout(self):
        self.close()
        self.login_window = LoginWindow()
        self.login_window.show()


# --- Вкладка управления столами ---
class TablesTab(QWidget):
    def __init__(self, is_admin=False):
        super().__init__()
        layout = QVBoxLayout(self)

        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(4)
        self.table_widget.setHorizontalHeaderLabels(["Номер", "Мест", "Доступен", "Статус"])

        btn_add = QPushButton("Добавить стол")
        btn_delete = QPushButton("Удалить стол")
        btn_toggle = QPushButton("Изменить доступность")

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_delete)
        btn_layout.addWidget(btn_toggle)

        layout.addWidget(self.table_widget)
        if is_admin:
            layout.addLayout(btn_layout)  # Только для админа

        btn_add.clicked.connect(self.add_table)
        btn_delete.clicked.connect(self.delete_table)
        btn_toggle.clicked.connect(self.toggle_availability)

        self.load_tables()

    def load_tables(self):
        self.table_widget.setRowCount(0)
        now = datetime.now()
        today = now.date()
        current_time = now.time()

        for table in table_collection.find():
            row = self.table_widget.rowCount()
            self.table_widget.insertRow(row)
            self.table_widget.setItem(row, 0, QTableWidgetItem(str(table["tableNumber"])))
            self.table_widget.setItem(row, 1, QTableWidgetItem(str(table["seats"])))
            self.table_widget.setItem(row, 2, QTableWidgetItem("Да" if table.get("isAvailable", True) else "Нет"))

            # Поиск бронирований на сегодня для этого стола
            reservations = list(reservation_collection.find({
                "tableId": table["_id"],
                "reservationDate": {"$eq": datetime.combine(today, datetime.min.time())},
                "status": {"$ne": "cancelled"}
            }))

            status = table.get("status", "free")
            busy_now = False
            reserved_today = False

            for res in reservations:
                start = datetime.strptime(res["startTime"], "%H:%M").time()
                end = datetime.strptime(res["endTime"], "%H:%M").time()
                if start <= current_time < end:
                    busy_now = True
                    break
                reserved_today = True

            if busy_now:
                status = "занят"
            elif reserved_today:
                status = "забронирован"
            else:
                status = "свободен" if table.get("isAvailable", True) else "недоступен"

            self.table_widget.setItem(row, 3, QTableWidgetItem(status))
            self.table_widget.item(row, 0).setData(Qt.UserRole, table["_id"])

    def add_table(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить стол")
        layout = QFormLayout(dialog)

        spin_num = QSpinBox()
        spin_num.setRange(1, 1000)
        spin_seats = QSpinBox()
        spin_seats.setRange(1, 50)

        layout.addRow("Номер стола:", spin_num)
        layout.addRow("Мест:", spin_seats)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton("Добавить")
        btn_cancel = QPushButton("Отмена")
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addRow(btn_box)

        def on_ok():
            if table_collection.find_one({"tableNumber": spin_num.value()}):
                QMessageBox.warning(dialog, "Ошибка", "Такой стол уже есть")
                return
            table_collection.insert_one({
                "tableNumber": spin_num.value(),
                "seats": spin_seats.value(),
                "isAvailable": True,
                "status": "free"
            })
            self.load_tables()
            dialog.accept()

        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(dialog.reject)

        dialog.exec()

    def delete_table(self):
        selected = self.table_widget.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите стол")
            return
        row = self.table_widget.currentRow()
        table_id = self.table_widget.item(row, 0).data(Qt.UserRole)
        table_collection.delete_one({"_id": table_id})
        reservation_collection.delete_many({"tableId": table_id})
        self.load_tables()

    def toggle_availability(self):
        selected = self.table_widget.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите стол")
            return
        row = self.table_widget.currentRow()
        table_id = self.table_widget.item(row, 0).data(Qt.UserRole)
        table = table_collection.find_one({"_id": table_id})
        new_status = not table.get("isAvailable", True)
        table_collection.update_one({"_id": table_id}, {"$set": {"isAvailable": new_status}})
        self.load_tables()

# --- Вкладка бронирований ---
from PySide6.QtCore import Signal

class ReservationsTab(QWidget):
    reservation_created = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # Форма бронирования
        form_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.table_combo = QComboBox()
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(date.today())
        self.start_time = QTimeEdit()
        self.end_time = QTimeEdit()

        form_layout.addRow("Имя клиента:", self.name_input)
        form_layout.addRow("Телефон клиента:", self.phone_input)
        form_layout.addRow("Стол:", self.table_combo)
        form_layout.addRow("Дата:", self.date_edit)
        form_layout.addRow("Время начала:", self.start_time)
        form_layout.addRow("Время конца:", self.end_time)

        btn_book = QPushButton("Забронировать")
        btn_cancel_res = QPushButton("Отменить бронирование")
        btn_delete_res = QPushButton("Удалить бронирование")
        btn_edit_res = QPushButton("Редактировать бронирование")  # Новая кнопка

        layout.addLayout(form_layout)
        layout.addWidget(btn_book)
        layout.addWidget(btn_cancel_res)
        layout.addWidget(btn_delete_res)
        layout.addWidget(btn_edit_res)  # Добавляем кнопку

        btn_book.clicked.connect(self.book_table)
        btn_cancel_res.clicked.connect(self.cancel_reservation)
        btn_delete_res.clicked.connect(self.delete_reservation)
        btn_edit_res.clicked.connect(self.edit_reservation)  # Привязываем обработчик

        self.reservations_list = QTableWidget()
        self.reservations_list.setColumnCount(6)
        self.reservations_list.setHorizontalHeaderLabels([
            "Клиент", "Телефон", "Стол", "Дата", "Время", "Статус"
        ])
        layout.addWidget(self.reservations_list)

        self.load_tables()
        self.load_reservations()

        # Новые строки для обновления таблицы при изменении даты и времени
        self.date_edit.dateChanged.connect(self.load_tables)
        self.start_time.timeChanged.connect(self.load_tables)
        self.end_time.timeChanged.connect(self.load_tables)

    def load_tables(self):
        self.table_combo.clear()
        res_date = self.date_edit.date().toPython()
        start = self.start_time.time().toPython()
        end = self.end_time.time().toPython()
        if start >= end:
            return

        res_date_dt = datetime.combine(res_date, datetime.min.time())
        for table in table_collection.find({"isAvailable": True}):
            busy = False
            for res in reservation_collection.find({
                "tableId": table["_id"],
                "reservationDate": res_date_dt,
                "status": {"$ne": "cancelled"}
            }):
                res_start = datetime.strptime(res["startTime"], "%H:%M").time()
                res_end = datetime.strptime(res["endTime"], "%H:%M").time()
                # Проверка пересечения интервалов
                if res_start < end and res_end > start:
                    busy = True
                    break
            if not busy:
                self.table_combo.addItem(f"Стол {table['tableNumber']} (мест: {table['seats']})", table["_id"])

    def load_reservations(self):
        self.reservations_list.setRowCount(0)
        for res in reservation_collection.find():
            row = self.reservations_list.rowCount()
            self.reservations_list.insertRow(row)
            customer = customer_collection.find_one({"_id": res["customerId"]})
            table = table_collection.find_one({"_id": res["tableId"]})
            self.reservations_list.setItem(row, 0, QTableWidgetItem(customer.get("name", "") if customer else ""))
            self.reservations_list.setItem(row, 1, QTableWidgetItem(customer.get("phone", "") if customer else ""))
            self.reservations_list.setItem(row, 2, QTableWidgetItem(str(table["tableNumber"]) if table else ""))
            date_value = res["reservationDate"]
            if isinstance(date_value, datetime):
                date_str = date_value.strftime("%Y-%m-%d")
            else:
                date_str = str(date_value)
            self.reservations_list.setItem(row, 3, QTableWidgetItem(date_str))
            self.reservations_list.setItem(row, 4, QTableWidgetItem(f"{res['startTime']} - {res['endTime']}"))
            self.reservations_list.setItem(row, 5, QTableWidgetItem(res.get("status", "confirmed")))
            self.reservations_list.item(row, 0).setData(Qt.UserRole, res["_id"])

    def book_table(self):
        name = self.name_input.text().strip()
        phone = self.phone_input.text().strip()
        table_id = self.table_combo.currentData()
        res_date = self.date_edit.date().toPython()
        start = self.start_time.time().toPython()
        end = self.end_time.time().toPython()

        if not name or not phone or not table_id:
            QMessageBox.warning(self, "Ошибка", "Заполните все поля")
            return
        if start >= end:
            QMessageBox.warning(self, "Ошибка", "Время начала должно быть меньше конца")
            return

        # Преобразуем res_date в datetime
        res_date_dt = datetime.combine(res_date, datetime.min.time())

        # Проверка пересечения бронирований
        overlapping = reservation_collection.find_one({
            "tableId": table_id,
            "reservationDate": res_date_dt,
            "$or": [
                {"startTime": {"$lt": end.strftime("%H:%M")}, "endTime": {"$gt": start.strftime("%H:%M")}}
            ],
            "status": {"$ne": "cancelled"}
        })
        if overlapping:
            QMessageBox.warning(self, "Ошибка", "Стол в это время уже забронирован")
            return

        customer = customer_collection.find_one({"phone": phone})
        if not customer:
            customer_id = customer_collection.insert_one({"name": name, "phone": phone}).inserted_id
        else:
            customer_id = customer["_id"]

        reservation_collection.insert_one({
            "tableId": table_id,
            "customerId": customer_id,
            "reservationDate": res_date_dt,
            "startTime": start.strftime("%H:%M"),
            "endTime": end.strftime("%H:%M"),
            "status": "confirmed"
        })

        QMessageBox.information(self, "Успешно", "Бронирование создано")
        self.load_reservations()
        self.reservation_created.emit()

    def cancel_reservation(self):
        selected = self.reservations_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите бронирование")
            return
        row = self.reservations_list.currentRow()
        res_id = self.reservations_list.item(row, 0).data(Qt.UserRole)
        reservation_collection.update_one({"_id": res_id}, {"$set": {"status": "cancelled"}})
        QMessageBox.information(self, "Отмена", "Бронирование отменено")
        self.load_reservations()
        self.reservation_created.emit()

    def delete_reservation(self):
        selected = self.reservations_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите бронирование")
            return
        row = self.reservations_list.currentRow()
        res_id = self.reservations_list.item(row, 0).data(Qt.UserRole)
        reply = QMessageBox.question(self, "Удалить", "Удалить выбранное бронирование?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            reservation_collection.delete_one({"_id": res_id})
            QMessageBox.information(self, "Удалено", "Бронирование удалено")
            self.load_reservations()
            self.reservation_created.emit()

    def edit_reservation(self):
        selected = self.reservations_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите бронирование")
            return
        row = self.reservations_list.currentRow()
        res_id = self.reservations_list.item(row, 0).data(Qt.UserRole)
        reservation = reservation_collection.find_one({"_id": res_id})
        if not reservation:
            QMessageBox.warning(self, "Ошибка", "Бронирование не найдено")
            return

        # Получаем связанные данные
        customer = customer_collection.find_one({"_id": reservation["customerId"]})

        dialog = QDialog(self)
        dialog.setWindowTitle("Редактировать бронирование")
        layout = QFormLayout(dialog)

        name_edit = QLineEdit(customer.get("name", "") if customer else "")
        phone_edit = QLineEdit(customer.get("phone", "") if customer else "")
        table_combo = QComboBox()
        for t in table_collection.find({"isAvailable": True}):
            table_combo.addItem(f"Стол {t['tableNumber']} (мест: {t['seats']})", t["_id"])
            if t["_id"] == reservation["tableId"]:
                table_combo.setCurrentIndex(table_combo.count() - 1)
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDate(reservation["reservationDate"].date() if isinstance(reservation["reservationDate"], datetime) else reservation["reservationDate"])
        start_time = QTimeEdit()
        end_time = QTimeEdit()
        start_time.setTime(QTime.fromString(reservation["startTime"], "HH:mm"))
        end_time.setTime(QTime.fromString(reservation["endTime"], "HH:mm"))

        layout.addRow("Имя клиента:", name_edit)
        layout.addRow("Телефон клиента:", phone_edit)
        layout.addRow("Стол:", table_combo)
        layout.addRow("Дата:", date_edit)
        layout.addRow("Время начала:", start_time)
        layout.addRow("Время конца:", end_time)

        btn_ok = QPushButton("Сохранить")
        btn_cancel = QPushButton("Отмена")
        btn_box = QHBoxLayout()
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addRow(btn_box)

        def on_ok():
            name = name_edit.text().strip()
            phone = phone_edit.text().strip()
            table_id = table_combo.currentData()
            res_date = date_edit.date().toPython()
            start = start_time.time().toPython()
            end = end_time.time().toPython()

            if not name or not phone or not table_id:
                QMessageBox.warning(dialog, "Ошибка", "Заполните все поля")
                return
            if start >= end:
                QMessageBox.warning(dialog, "Ошибка", "Время начала должно быть меньше конца")
                return

            res_date_dt = datetime.combine(res_date, datetime.min.time())

            # Проверка пересечения бронирований (кроме текущего)
            overlapping = reservation_collection.find_one({
                "tableId": table_id,
                "reservationDate": res_date_dt,
                "$or": [
                    {"startTime": {"$lt": end.strftime("%H:%M")}, "endTime": {"$gt": start.strftime("%H:%M")}}
                ],
                "status": {"$ne": "cancelled"},
                "_id": {"$ne": res_id}
            })
            if overlapping:
                QMessageBox.warning(dialog, "Ошибка", "Стол в это время уже забронирован")
                return

            # Обновляем или создаём клиента с новыми данными
            customer = customer_collection.find_one({"phone": phone})
            if customer:
                customer_collection.update_one(
                    {"_id": customer["_id"]},
                    {"$set": {"name": name, "phone": phone}}
                )
                customer_id = customer["_id"]
            else:
                customer_id = customer_collection.insert_one({"name": name, "phone": phone}).inserted_id

            reservation_collection.update_one(
                {"_id": res_id},
                {"$set": {
                    "tableId": table_id,
                    "customerId": customer_id,
                    "reservationDate": res_date_dt,
                    "startTime": start.strftime("%H:%M"),
                    "endTime": end.strftime("%H:%M"),
                    "status": "confirmed"
                }}
            )
            QMessageBox.information(dialog, "Успешно", "Бронирование обновлено")
            self.load_reservations()
            self.reservation_created.emit()
            dialog.accept()

        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec()


# --- Вкладка заказов ---
from PySide6.QtCore import Signal

class OrdersTab(QWidget):
    order_updated = Signal()
    receipt_created = Signal()

    def __init__(self, user):
        super().__init__()
        self.user = user
        layout = QVBoxLayout(self)

        # Заказы списка
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(6)
        self.orders_table.setHorizontalHeaderLabels([
            "Клиент", "Стол", "Дата", "Блюда", "Статус", "Ответственный"
        ])

        # Кнопки для создания заказа, изменения статуса, выдачи счета и удаления заказа
        btn_new_order = QPushButton("Создать заказ")
        btn_change_status = QPushButton("Изменить статус заказа")
        btn_create_receipt = QPushButton("Выдать счет")
        btn_delete_order = QPushButton("Удалить заказ")  # Новая кнопка

        layout.addWidget(self.orders_table)
        layout.addWidget(btn_new_order)
        layout.addWidget(btn_change_status)
        layout.addWidget(btn_create_receipt)
        layout.addWidget(btn_delete_order)  # Добавляем кнопку

        btn_new_order.clicked.connect(self.create_order)
        btn_change_status.clicked.connect(self.change_status)
        btn_create_receipt.clicked.connect(self.create_receipt)
        btn_delete_order.clicked.connect(self.delete_order)  # Привязываем обработчик

        self.load_orders()

    def delete_order(self):
        selected = self.orders_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите заказ")
            return
        row = self.orders_table.currentRow()
        order_id = self.orders_table.item(row, 0).data(Qt.UserRole)
        reply = QMessageBox.question(self, "Удалить", "Удалить выбранный заказ?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # Удаляем связанные счета
            receipt_collection.delete_many({"orderId": order_id})
            # Удаляем заказ
            order_collection.delete_one({"_id": order_id})
            QMessageBox.information(self, "Удалено", "Заказ удален")
            self.load_orders()
            self.order_updated.emit()

    def load_orders(self):
        self.orders_table.setRowCount(0)
        for order in order_collection.find():
            row = self.orders_table.rowCount()
            self.orders_table.insertRow(row)
            customer = customer_collection.find_one({"_id": order.get("customerId")})
            table = table_collection.find_one({"_id": order.get("tableId")})
            dishes = ", ".join([f"{item['name']} x{item['quantity']}" for item in order.get("dishes", [])])
            self.orders_table.setItem(row, 0, QTableWidgetItem(customer.get("name", "") if customer else ""))
            self.orders_table.setItem(row, 1, QTableWidgetItem(str(table["tableNumber"]) if table else ""))
            self.orders_table.setItem(row, 2, QTableWidgetItem(str(order.get("orderDate", ""))))
            self.orders_table.setItem(row, 3, QTableWidgetItem(dishes))
            self.orders_table.setItem(row, 4, QTableWidgetItem(order.get("status", "new")))
            self.orders_table.setItem(row, 5, QTableWidgetItem(order.get("waiterLogin", "")))

            self.orders_table.item(row, 0).setData(Qt.UserRole, order["_id"])

    def create_order(self):
        dialog = OrderDialog(self.user)
        if dialog.exec():
            self.load_orders()
            self.order_updated.emit()

    def change_status(self):
        selected = self.orders_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите заказ")
            return
        row = self.orders_table.currentRow()
        order_id = self.orders_table.item(row, 0).data(Qt.UserRole)

        order = order_collection.find_one({"_id": order_id})
        if not order:
            QMessageBox.warning(self, "Ошибка", "Заказ не найден")
            return

        statuses = ["new", "preparing", "ready", "delivered", "cancelled", "paid"]  # Добавили "paid"
        current_status = order.get("status", "new")
        # Если статус не в списке, ставим 0
        try:
            current_index = statuses.index(current_status)
        except ValueError:
            current_index = 0
        next_status, ok = QInputDialog.getItem(self, "Изменить статус", "Новый статус", statuses, current_index, False)
        if ok and next_status:
            order_collection.update_one({"_id": order_id}, {"$set": {"status": next_status}})
            self.load_orders()
            self.order_updated.emit()

    def create_receipt(self):
        selected = self.orders_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите заказ")
            return
        row = self.orders_table.currentRow()
        order_id = self.orders_table.item(row, 0).data(Qt.UserRole)
        order = order_collection.find_one({"_id": order_id})
        if not order:
            QMessageBox.warning(self, "Ошибка", "Заказ не найден")
            return

        # Проверяем, есть ли уже счет на этот заказ
        existing = receipt_collection.find_one({"orderId": order_id})
        if existing:
            QMessageBox.information(self, "Инфо", "Счет на этот заказ уже выдан")
            return

        # Считаем сумму заказа
        amount = sum(item["price"] * item["quantity"] for item in order.get("dishes", []))

        # Создаем счет
        receipt_collection.insert_one({
            "orderId": order["_id"],  # обязательно ObjectId, а не строка!
            "date": datetime.now(),
            "amount": amount,
            "paid": False
        })

        QMessageBox.information(self, "Успешно", "Счет выдан")
        self.receipt_created.emit()  # Сигнал о создании счета


class OrderDialog(QDialog):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.setWindowTitle("Создать заказ")
        self.resize(400, 400)

        layout = QVBoxLayout(self)

        self.customer_name = QLineEdit()
        self.customer_phone = QLineEdit()
        self.table_combo = QComboBox()
        self.load_tables()

        self.menu_list = QListWidget()
        self.load_menu()

        self.selected_dishes = []

        btn_add_dish = QPushButton("Добавить в заказ")
        btn_add_dish.clicked.connect(self.add_dish_to_order)

        btn_submit = QPushButton("Создать заказ")
        btn_submit.clicked.connect(self.submit_order)

        layout.addWidget(QLabel("Имя клиента:"))
        layout.addWidget(self.customer_name)
        layout.addWidget(QLabel("Телефон клиента:"))
        layout.addWidget(self.customer_phone)
        layout.addWidget(QLabel("Стол:"))
        layout.addWidget(self.table_combo)
        layout.addWidget(QLabel("Меню:"))
        layout.addWidget(self.menu_list)
        layout.addWidget(btn_add_dish)

        self.order_dishes_list = QListWidget()
        layout.addWidget(QLabel("Выбранные блюда:"))
        layout.addWidget(self.order_dishes_list)

        layout.addWidget(btn_submit)

    def load_tables(self):
        self.table_combo.clear()
        now = datetime.now()
        today = now.date()
        current_time = now.time()
        for table in table_collection.find({"isAvailable": True}):
            # Проверяем, не занят ли стол сейчас
            reservations = reservation_collection.find({
                "tableId": table["_id"],
                "reservationDate": datetime.combine(today, datetime.min.time()),
                "status": {"$ne": "cancelled"}
            })
            busy_now = False
            for res in reservations:
                start = datetime.strptime(res["startTime"], "%H:%M").time()
                end = datetime.strptime(res["endTime"], "%H:%M").time()
                if start <= current_time < end:
                    busy_now = True
                    break
            if not busy_now:
                self.table_combo.addItem(f"Стол {table['tableNumber']} (мест: {table['seats']})", table["_id"])

    def load_menu(self):
        self.menu_list.clear()
        for item in menu_collection.find():
            lw_item = QListWidgetItem(f"{item['name']} - {item['price']} руб.")
            lw_item.setData(Qt.UserRole, item)
            self.menu_list.addItem(lw_item)

    def add_dish_to_order(self):
        selected = self.menu_list.currentItem()
        if not selected:
            return
        item = selected.data(Qt.UserRole)
        quantity, ok = QInputDialog.getInt(self, "Количество", f"Сколько {item['name']} добавить?", 1, 1)
        if ok:
            # Добавляем или увеличиваем количество
            found = False
            for d in self.selected_dishes:
                if d["item"]["_id"] == item["_id"]:
                    d["quantity"] += quantity
                    found = True
                    break
            if not found:
                self.selected_dishes.append({"item": item, "quantity": quantity})
            self.refresh_order_dishes()

    def refresh_order_dishes(self):
        self.order_dishes_list.clear()
        for d in self.selected_dishes:
            self.order_dishes_list.addItem(f"{d['item']['name']} x{d['quantity']}")

    def submit_order(self):
        name = self.customer_name.text().strip()
        phone = self.customer_phone.text().strip()
        table_id = self.table_combo.currentData()

        if not name or not phone or not table_id:
            QMessageBox.warning(self, "Ошибка", "Заполните все поля")
            return
        if not self.selected_dishes:
            QMessageBox.warning(self, "Ошибка", "Добавьте хотя бы одно блюдо")
            return

        customer = customer_collection.find_one({"phone": phone})
        if not customer:
            customer_id = customer_collection.insert_one({"name": name, "phone": phone}).inserted_id
        else:
            customer_id = customer["_id"]

        order_collection.insert_one({
            "customerId": customer_id,
            "tableId": table_id,
            "orderDate": datetime.now(),
            "dishes": [{"name": d["item"]["name"], "price": d["item"]["price"], "quantity": d["quantity"]} for d in self.selected_dishes],
            "status": "new",
            "waiterLogin": self.user["login"]
        })

        QMessageBox.information(self, "Успешно", "Заказ создан")
        self.accept()


# --- Вкладка счетов ---
class ReceiptsTab(QWidget):
    receipt_paid = Signal()  # Новый сигнал

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.receipts_table = QTableWidget()
        self.receipts_table.setColumnCount(5)
        self.receipts_table.setHorizontalHeaderLabels(["Клиент", "Дата", "Заказ", "Сумма", "Оплачен"])

        btn_pay = QPushButton("Оплатить счет")
        layout.addWidget(self.receipts_table)
        layout.addWidget(btn_pay)

        btn_pay.clicked.connect(self.pay_receipt)

        self.load_receipts()

    def load_receipts(self):
        self.receipts_table.setRowCount(0)
        for receipt in receipt_collection.find():
            row = self.receipts_table.rowCount()
            self.receipts_table.insertRow(row)

            # Проверяем наличие orderId
            order = None
            customer = None
            if "orderId" in receipt:
                order = order_collection.find_one({"_id": receipt["orderId"]})
                if order:
                    customer = customer_collection.find_one({"_id": order["customerId"]})

            self.receipts_table.setItem(row, 0, QTableWidgetItem(customer.get("name", "") if customer else ""))
            self.receipts_table.setItem(row, 1, QTableWidgetItem(str(receipt.get("date", ""))))
            self.receipts_table.setItem(row, 2, QTableWidgetItem(str(order["_id"]) if order else ""))
            self.receipts_table.setItem(row, 3, QTableWidgetItem(str(receipt.get("amount", 0))))
            self.receipts_table.setItem(row, 4, QTableWidgetItem("Да" if receipt.get("paid", False) else "Нет"))

            self.receipts_table.item(row, 0).setData(Qt.UserRole, receipt["_id"])

    def pay_receipt(self):
        selected = self.receipts_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите счет")
            return
        row = self.receipts_table.currentRow()
        receipt_id = self.receipts_table.item(row, 0).data(Qt.UserRole)
        receipt = receipt_collection.find_one({"_id": receipt_id})
        if not receipt:
            QMessageBox.warning(self, "Ошибка", "Счет не найден")
            return
        if receipt.get("paid", False):
            QMessageBox.information(self, "Инфо", "Счет уже оплачен")
            return

        # Формируем оплату
        receipt_collection.update_one({"_id": receipt_id}, {"$set": {"paid": True, "paymentDate": datetime.now()}})
        
        # Меняем статус заказа на "paid"
        if "orderId" in receipt:
            order_collection.update_one({"_id": receipt["orderId"]}, {"$set": {"status": "paid"}})

        QMessageBox.information(self, "Оплата", "Счет оплачен")
        self.load_receipts()
        self.receipt_paid.emit()  # Сигнал для обновления заказов


# --- Вкладка меню ---
class MenuTab(QWidget):
    def __init__(self, is_admin=False):
        super().__init__()
        layout = QVBoxLayout(self)

        self.menu_table = QTableWidget()
        self.menu_table.setColumnCount(5)
        self.menu_table.setHorizontalHeaderLabels(["Название", "Описание", "Цена", "Категория", "Ингредиенты"])

        btn_add = QPushButton("Добавить блюдо")
        btn_edit = QPushButton("Редактировать блюдо")
        btn_delete = QPushButton("Удалить блюдо")

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_delete)

        layout.addWidget(self.menu_table)
        if is_admin:
            layout.addLayout(btn_layout)  # Только для админа

        if is_admin:
            btn_add.clicked.connect(self.add_item)
            btn_edit.clicked.connect(self.edit_item)
            btn_delete.clicked.connect(self.delete_item)

        self.setLayout(layout)
        self.load_menu()

    def load_menu(self):
        self.menu_table.setRowCount(0)
        for item in menu_collection.find():
            row = self.menu_table.rowCount()
            self.menu_table.insertRow(row)
            self.menu_table.setItem(row, 0, QTableWidgetItem(item.get("name", "")))
            self.menu_table.setItem(row, 1, QTableWidgetItem(item.get("description", "")))
            self.menu_table.setItem(row, 2, QTableWidgetItem(str(item.get("price", ""))))
            self.menu_table.setItem(row, 3, QTableWidgetItem(str(item.get("category", ""))))
            # Исправление для ingredients:
            ingredients = item.get("ingredients", [])
            ingredients_str = []
            for ing in ingredients:
                if isinstance(ing, dict):
                    ingredients_str.append(ing.get("name", str(ing)))
                else:
                    ingredients_str.append(str(ing))
            self.menu_table.setItem(row, 4, QTableWidgetItem(", ".join(ingredients_str)))
            self.menu_table.item(row, 0).setData(Qt.UserRole, item["_id"])

    def add_item(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить блюдо")
        layout = QFormLayout(dialog)
        name_edit = QLineEdit()
        desc_edit = QLineEdit()
        price_edit = QSpinBox()
        price_edit.setRange(0, 100000)
        category_edit = QLineEdit()
        ingredients_edit = QLineEdit()
        ingredients_edit.setPlaceholderText("Через запятую")

        layout.addRow("Название:", name_edit)
        layout.addRow("Описание:", desc_edit)
        layout.addRow("Цена:", price_edit)
        layout.addRow("Категория:", category_edit)
        layout.addRow("Ингредиенты:", ingredients_edit)

        btn_ok = QPushButton("Добавить")
        btn_cancel = QPushButton("Отмена")
        btn_box = QHBoxLayout()
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addRow(btn_box)

        def on_ok():
            if not name_edit.text().strip():
                QMessageBox.warning(dialog, "Ошибка", "Введите название блюда")
                return
            menu_collection.insert_one({
                "name": name_edit.text().strip(),
                "description": desc_edit.text().strip(),
                "price": price_edit.value(),
                "category": category_edit.text().strip(),
                "ingredients": [i.strip() for i in ingredients_edit.text().split(",") if i.strip()]
            })
            self.load_menu()
            dialog.accept()

        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec()

    def edit_item(self):
        selected = self.menu_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите блюдо")
            return
        row = self.menu_table.currentRow()
        item_id = self.menu_table.item(row, 0).data(Qt.UserRole)
        item = menu_collection.find_one({"_id": item_id})
        if not item:
            QMessageBox.warning(self, "Ошибка", "Блюдо не найдено")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Редактировать блюдо")
        layout = QFormLayout(dialog)
        name_edit = QLineEdit(item.get("name", ""))
        desc_edit = QLineEdit(item.get("description", ""))
        price_edit = QSpinBox()
        price_edit.setRange(0, 100000)
        price_edit.setValue(item.get("price", 0))
        category_edit = QLineEdit(item.get("category", ""))
        ingredients_edit = QLineEdit(", ".join(item.get("ingredients", [])))

        layout.addRow("Название:", name_edit)
        layout.addRow("Описание:", desc_edit)
        layout.addRow("Цена:", price_edit)
        layout.addRow("Категория:", category_edit)
        layout.addRow("Ингредиенты:", ingredients_edit)

        btn_ok = QPushButton("Сохранить")
        btn_cancel = QPushButton("Отмена")
        btn_box = QHBoxLayout()
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addRow(btn_box)

        def on_ok():
            if not name_edit.text().strip():
                QMessageBox.warning(dialog, "Ошибка", "Введите название блюда")
                return
            menu_collection.update_one(
                {"_id": item_id},
                {"$set": {
                    "name": name_edit.text().strip(),
                    "description": desc_edit.text().strip(),
                    "price": price_edit.value(),
                    "category": category_edit.text().strip(),
                    "ingredients": [i.strip() for i in ingredients_edit.text().split(",") if i.strip()]
                }}
            )
            self.load_menu()
            dialog.accept()

        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec()

    def delete_item(self):
        selected = self.menu_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Ошибка", "Выберите блюдо")
            return
        row = self.menu_table.currentRow()
        item_id = self.menu_table.item(row, 0).data(Qt.UserRole)
        reply = QMessageBox.question(self, "Удалить", "Удалить выбранное блюдо?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            menu_collection.delete_one({"_id": item_id})
            self.load_menu()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())
