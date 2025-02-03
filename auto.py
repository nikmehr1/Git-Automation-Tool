import sys
import random
import string
import subprocess
from hashlib import sha256
import time
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar,
    QComboBox, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer

class Worker(QThread):
    update_log = pyqtSignal(str, str)
    update_progress = pyqtSignal(int)
    update_loading = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.running = True
        self.current_iteration = 0

    
    def run(self):
        try:
            for self.current_iteration in range(self.config['iterations']):
                if not self.running:
                    break
                
                # Generate token
                token = generate_random_string(50)
                write_to_file('key.txt', token)
                self.update_log.emit(f"Generated token: {token}", "blue")
                
                # Base wait time in seconds
                base_wait_seconds = self.config['wait_time'] * (
                    60 if self.config['time_unit'] == 'minutes' else 1
                )

                # Introduce variability
                variation_percentage = 0.2  # Adjust as needed
                min_wait = base_wait_seconds * (1 - variation_percentage)
                max_wait = base_wait_seconds * (1 + variation_percentage)
                total_wait_seconds = random.uniform(min_wait, max_wait)
                
                # Run loading animation with actual waiting
                self.run_loading_animation(total_wait_seconds)
                
                # Git operations with retry
                success = self.git_operations_with_retry()
                
                if not success:
                    # Base problem wait time in seconds
                    base_problem_wait = self.config['problem_wait'] * 60
                    
                    # Introduce variability
                    min_problem_wait = base_problem_wait * (1 - variation_percentage)
                    max_problem_wait = base_problem_wait * (1 + variation_percentage)
                    problem_wait = random.uniform(min_problem_wait, max_problem_wait)
                    
                    self.update_log.emit(
                        f"⏳ Waiting {round(problem_wait / 60, 2)} minutes before next attempt", "red"
                    )
                    self.run_loading_animation(problem_wait)
                
                # Update progress
                progress = int((self.current_iteration + 1) / self.config['iterations'] * 100)
                self.update_progress.emit(progress)
                
            self.finished.emit()
        except Exception as e:
            self.update_log.emit(f"🔥 Critical error: {str(e)}", "red")


    def run_loading_animation(self, duration):
        start_time = time.time()
        while (time.time() - start_time) < duration:
            remaining = duration - (time.time() - start_time)
            self.update_loading.emit(int(remaining))
            time.sleep(0.1)

    def git_operations_with_retry(self):
        for attempt in range(10):
            try:
                self.run_command("git pull origin main")
                self.run_command("git add .")
                self.run_command('git commit -m "update"')
                self.run_command("git push origin main")
                return True
            except Exception as e:
                self.update_log.emit(f"⚠️ Attempt {attempt+1}/10 failed: {str(e)}", "red")
                time.sleep(1)
        return False

    def run_command(self, command):
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr)
        self.update_log.emit(f"✅ Success: {command}", "green")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.worker = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_loading_time)

    def setup_ui(self):
        self.setWindowTitle("Git Automation Tool")
        self.setGeometry(100, 100, 800, 600)

        # Widgets
        self.iterations_input = QLineEdit()
        self.time_input = QLineEdit()
        self.time_unit = QComboBox()
        self.time_unit.addItems(['minutes', 'seconds'])
        self.problem_wait_input = QLineEdit()
        self.start_btn = QPushButton("Start")
        self.log_area = QTextEdit()
        self.progress_bar = QProgressBar()
        self.loading_label = QLabel("Waiting time remaining: --")

        # Layout
        layout = QVBoxLayout()
        form_layout = QHBoxLayout()
        
        form_layout.addWidget(QLabel("Iterations (max 1000):"))
        form_layout.addWidget(self.iterations_input)
        form_layout.addWidget(QLabel("Wait Time:"))
        form_layout.addWidget(self.time_input)
        form_layout.addWidget(self.time_unit)
        form_layout.addWidget(QLabel("Problem Wait (minutes):"))
        form_layout.addWidget(self.problem_wait_input)
        
        layout.addLayout(form_layout)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.loading_label)
        layout.addWidget(self.log_area)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Connections
        self.start_btn.clicked.connect(self.start_process)

    def validate_inputs(self):
        try:
            config = {
                'iterations': min(int(self.iterations_input.text()), 1000),
                'wait_time': float(self.time_input.text()),
                'time_unit': self.time_unit.currentText(),
                'problem_wait': min(int(self.problem_wait_input.text()), 60)
            }

            max_time = 3600 if config['time_unit'] == 'seconds' else 60
            if config['wait_time'] > max_time:
                raise ValueError("Wait time exceeds maximum allowed (1 hour)")

            return config
        except Exception as e:
            QMessageBox.critical(self, "Input Error", str(e))
            return None

    def start_process(self):
        config = self.validate_inputs()
        if not config:
            return

        self.start_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_area.clear()
        self.timer.start(100)

        self.worker = Worker(config)
        self.worker.update_log.connect(self.update_log)
        self.worker.update_progress.connect(self.progress_bar.setValue)
        self.worker.update_loading.connect(self.update_loading_time)
        self.worker.finished.connect(self.process_finished)
        self.worker.start()

    def update_log(self, message, color):
        self.log_area.append(f"<span style='color:{color};font-weight:bold;'>{message}</span>")

    def update_loading_time(self, seconds):
        self.loading_label.setText(f"⏳ Remaining wait time: {seconds:.0f} seconds")


    def process_finished(self):
        self.start_btn.setEnabled(True)
        self.timer.stop()
        self.loading_label.setText("✅ Process completed!")

# Utility functions
def generate_random_string(length):
    # Generate a random number
    random_number = random.randint(0, 1_000_000)  # You can adjust the range as needed
    # Concatenate 'Abinot' with the random number
    abinottext = 'Abinot' + str(random_number)
    # Compute the SHA-256 hash of the string
    hashed_text = sha256(abinottext.encode('utf-8')).hexdigest()
    return hashed_text


def write_to_file(filename, data):
    try:
        with open(filename, 'w') as file:
            file.write(data)
    except IOError as e:
        print(f"Error writing to file {filename}: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
