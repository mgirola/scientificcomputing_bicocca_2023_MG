import sys
import numpy as np
import h5py
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QListWidgetItem, QSlider,
                             QLabel, QLineEdit, QFileDialog, QMessageBox, QComboBox, QRadioButton, QAction, QInputDialog,
                             QCheckBox, QGroupBox, QHBoxLayout, QDialog, QCompleter, QListWidget, QColorDialog)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent
from PyQt5.QtGui import QKeyEvent, QIcon
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.markers as mmarkers
from matplotlib.figure import Figure
import numexpr as ne
import re

#import os
#os.environ["QT_DEBUG_PLUGINS"] = "1"

CHUNK_SIZE = 10000
INITIAL_MARKER_SIZE = 1



class LineEditConditionsListComboBox(QLineEdit):
    # Define custom signals
    escPressed = pyqtSignal()
    ctrlBackspacePressed = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            #print("ESC key pressed in QLineEdit")
            self.escPressed.emit()  # Emit the custom signal
            event.ignore()  # Optional: pass the event to the parent widget
        elif (event.key() == Qt.Key_Backspace and 
              (event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier))):
            #print("Control/Command + Backspace pressed in QLineEdit")
            self.ctrlBackspacePressed.emit()  # Emit the custom signal
            event.ignore()
        else:
            #print(f"Other key pressed in QLineEdit: {event.key()} ")
            super().keyPressEvent(event)  # Handle other key events normally

class ConditionsListComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.clearEditText()
        customLineEdit = LineEditConditionsListComboBox(self)
        self.setLineEdit(customLineEdit)

class CustomToolbar(NavigationToolbar):
    def __init__(self, canvas, parent, coordinates=True):
        super().__init__(canvas, parent, coordinates)

        # Add custom button for changing color
        self.addSeparator()
        self.color_button = QAction(QIcon(None), 'Change Color', self)
        self.color_button.triggered.connect(self.change_color)
        self.addAction(self.color_button)

        # Label and slider for point size
        self.label = QLabel(" Point Size: ", self)
        self.addWidget(self.label)
        self.size_slider = QSlider(Qt.Horizontal, self)
        self.size_slider.setMinimum(INITIAL_MARKER_SIZE // 10)  
        self.size_slider.setMaximum(INITIAL_MARKER_SIZE * 10)  
        self.size_slider.setValue(INITIAL_MARKER_SIZE) 
        self.size_slider.setTickInterval(INITIAL_MARKER_SIZE // 100)
        self.size_slider.setTickPosition(QSlider.TicksBelow)
        self.size_slider.valueChanged.connect(self.change_size)
        self.addWidget(self.size_slider)

        # Combo box for selecting marker types
        self.marker_combo = QComboBox(self)
        self.marker_combo.addItems(['o', '^', 's', '*', '+', 'x', ','])  # Example marker types
        self.marker_combo.currentIndexChanged.connect(self.change_marker_type)
        self.addWidget(self.marker_combo)

    def change_color(self):
        if not self.canvas.figure.axes or not hasattr(self.canvas.figure.axes[0], 'collections') or not self.canvas.figure.axes[0].collections:
            QMessageBox.warning(self, "Error", "No scatter plot found to change color.")
            return

        color = QColorDialog.getColor()
        if color.isValid():
            scatter = self.canvas.figure.axes[0].collections[0]
            scatter.set_edgecolor(color.name())
            scatter.set_facecolor(color.name())
            self.canvas.draw()

    def change_size(self, value):
        if not self.canvas.figure.axes or not hasattr(self.canvas.figure.axes[0], 'collections') or not self.canvas.figure.axes[0].collections:
            QMessageBox.warning(self, "Error", "No scatter plot found to change size.")
            return

        scatter = self.canvas.figure.axes[0].collections[0]
        scatter.set_sizes([value ** 2])
        self.canvas.draw()

    def change_marker_type(self):
        if not self.canvas.figure.axes or not hasattr(self.canvas.figure.axes[0], 'collections') or not self.canvas.figure.axes[0].collections:
            QMessageBox.warning(self, "Error", "No scatter plot found to change marker type.")
            return

        marker_type = self.marker_combo.currentText()
        scatter = self.canvas.figure.axes[0].collections[0]
        marker_style = mmarkers.MarkerStyle(marker_type)
        scatter.set_paths([marker_style.get_path()])
        self.canvas.draw()

class PulsePlotWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = CustomToolbar(self.canvas, self)
        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        self.setLayout(layout)
        self.setWindowTitle("Pulse Data Plot")

    def plot_pulse(self, pulse_data):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(pulse_data)
        ax.set_title('Pulse Detail')
        ax.set_xlabel('Sample Index')
        ax.set_ylabel('Pulse Amplitude')
        self.canvas.draw()

class PulseAnalysisWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("iuganaid - a simpler dianagui")
        self.setGeometry(100, 100, 800, 600)
        self.setup_ui()
        self.hdf5_file_path = ""
        self.datasets = []
        self.indices = []
        self.current_pulse_index = 0

    def setup_ui(self):
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)

        self.combo_boxes_with_variables_from_file = []

        self.show_pulses_checkbox = QCheckBox("Show Pulses on Hover", self)
        self.show_pulses_checkbox.setChecked(False)
        self.x_axis_combo_box = self.create_editable_combobox()
        self.y_axis_combo_box = self.create_editable_combobox()
        self.combo_boxes_with_variables_from_file.append(self.x_axis_combo_box)
        self.combo_boxes_with_variables_from_file.append(self.y_axis_combo_box)
        self.mode_group = self.setup_mode_group()

        self.file_label = QLabel("No file selected", self)
        self.file_button = QPushButton("Select HDF5 File", self)
        self.file_button.clicked.connect(self.open_file_dialog)

        #Add a box that contains the conditions while a type or select them from the cut_variables_slect_combo_box
        self.conditions = QListWidget(self)
        self.conditions.setToolTip("Type conditions like Channel == 1 and so on. PRESS ESC or ctrl/cmd + backspace to DELETE A LINE. Use '==' for equality, '!=' for inequality, '>', '<', '>=', '<=' for comparison. Use 'and', 'or' for logical operations. Use 'not' for negation. Use '()' for grouping. Use 'True' and 'False' for boolean values. Use mathematical funtion as abs() to slect only the events meeting a mathematical criteria. e.g. \"abs(BaselineSlope)<0.02\". You can also select on multiple variables by combining them with mathematical operations, e.g. \"sqrt(OF_TVR^2+OF_TVL^2)<1\"")
        self.initiate_dynamic_add_of_conditions()
        

        self.pulse_dataset_input = QLineEdit(self)
        self.pulse_dataset_input.setPlaceholderText("Enter pulse label, e.g. 'pulse'")
        self.pulse_dataset_input.setText("pulse")  # Default value


        self.next_button = QPushButton("Next Pulse", self)
        self.next_button.clicked.connect(self.next_pulse)
        self.prev_button = QPushButton("Previous Pulse", self)
        self.prev_button.clicked.connect(self.prev_pulse)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = CustomToolbar(self.canvas, self)

        for widget in [self.file_button, self.file_label, self.mode_group, 
                       self.conditions, self.pulse_dataset_input, 
                       self.x_axis_combo_box, self.y_axis_combo_box, 
                       self.apply_button, self.show_pulses_checkbox, self.toolbar, 
                       self.canvas, self.next_button, self.prev_button]:
            layout.addWidget(widget)

        self.hover_window = PulsePlotWindow(self)
     
    def initiate_dynamic_add_of_conditions(self):
        list_item = QListWidgetItem(self.conditions)
        condition_combo_box = self.create_editable_combobox(ConditionsListComboBox)
        condition_combo_box.setToolTip("Press ESC to delete this line. Press ctrl/cmd + backspace to delete this line.")
        self.combo_boxes_with_variables_from_file.append(condition_combo_box)
        
        try:
            self.populate_combo_box_with_file_variables(condition_combo_box)
        except AttributeError as e:
            if "no attribute 'hdf5_file_path'" in str(e):
                pass
            else:
                raise

        self.conditions.setItemWidget(list_item, condition_combo_box)
        list_item.setSizeHint(condition_combo_box.sizeHint())

        # Set up interaction triggers
        condition_combo_box.lineEdit().returnPressed.connect(lambda: self.user_finished_editing(condition_combo_box))
        condition_combo_box.completer().activated.connect(lambda: self.user_finished_editing(condition_combo_box))
        condition_combo_box.lineEdit().escPressed.connect(lambda: self.user_deleted_condition(condition_combo_box))
        condition_combo_box.lineEdit().ctrlBackspacePressed.connect(lambda: self.user_deleted_condition(condition_combo_box))

    def user_finished_editing(self, cb):
        # Check if the combo box being interacted with is the last one
        if cb == self.conditions.itemWidget(self.conditions.item(self.conditions.count() - 1)):
            self.initiate_dynamic_add_of_conditions()

    def populate_combo_box_with_file_variables(self, combo_box):
        if self.hdf5_file_path:
            with h5py.File(self.hdf5_file_path, 'r') as file:
                self.datasets = list(file.keys())
            combo_box.clear()
            combo_box.addItems(self.datasets)
            combo_box.completer().setModel(combo_box.model())
        else:
            QMessageBox.warning(self, "Error", "Please open a valid file first.")

    def user_deleted_condition(self, cb):
        # Find the combo box that is being interacted with in the list of conditions
        for i in range(self.conditions.count()):
            if cb is self.conditions.itemWidget(self.conditions.item(i)):
                # Remove the condition from the list unless it is the last one
                if i < self.conditions.count() - 1:
                    self.conditions.takeItem(i)
                break
            else:
                print("Impossible to find the condition to delete")
            
    def create_editable_combobox(self, WhichComboBox=QComboBox):
        combo_box = WhichComboBox(self)
        combo_box.setEditable(True)
        # Adding a completer
        completer = QCompleter(self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        combo_box.setCompleter(completer)
        return combo_box

    def setup_mode_group(self):
        mode_group = QGroupBox("Mode Selection")
        mode_layout = QHBoxLayout()
        self.draw_pulses_checkable = QRadioButton("Draw Pulses")
        self.draw_scatter_checkable = QRadioButton("Draw Scatter")
        mode_layout.addWidget(self.draw_pulses_checkable)
        mode_layout.addWidget(self.draw_scatter_checkable)
        mode_group.setLayout(mode_layout)
        self.draw_pulses_checkable.setChecked(True)
        self.draw_pulses_checkable.toggled.connect(self.switch_mode)
        self.draw_scatter_checkable.toggled.connect(self.switch_mode)
        self.apply_button = QPushButton("Draw Pulse" if self.draw_pulses_checkable.isChecked() else "Draw Scatter", self)
        for xy_combo_box in [self.x_axis_combo_box, self.y_axis_combo_box]:
            xy_combo_box.setDisabled(True) if self.draw_pulses_checkable.isChecked() else xy_combo_box.setDisabled(False)

        self.apply_button.clicked.connect(self.draw)
        self.show_pulses_checkbox.setEnabled(True) if self.draw_scatter_checkable.isChecked() else self.show_pulses_checkbox.setEnabled(False)
        return mode_group

    def open_file_dialog(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Open HDF5 File", "", "HDF5 Files (*.hdf5 *.h5 *.hdf);;All Files (*)", options=options)
        if file_name:
            self.file_label.setText(f"Selected File: {file_name}")
            self.hdf5_file_path = file_name
            for combo_box in self.combo_boxes_with_variables_from_file:
                self.populate_combo_box_with_file_variables(combo_box)

    def switch_mode(self):
        is_scatter = self.draw_scatter_checkable.isChecked()
        is_pulses = self.draw_pulses_checkable.isChecked()
        self.pulse_dataset_input.setEnabled(is_scatter or is_pulses)
        self.show_pulses_checkbox.setEnabled(is_scatter)
        self.x_axis_combo_box.setEnabled(is_scatter)
        self.y_axis_combo_box.setEnabled(is_scatter)
        self.next_button.setEnabled(is_pulses)
        self.prev_button.setEnabled(is_pulses)
        self.apply_button.setText("Draw scatter" if is_scatter else "Draw pulse")

    def draw(self):
        if self.draw_pulses_checkable.isChecked():
            self.handle_draw_pulses()
        elif self.draw_scatter_checkable.isChecked():
            self.handle_draw_scatter()

    def handle_draw_pulses(self):
        try:
            self.select_data_get_selected_indices()
            if not self.indices:
                QMessageBox.information(self, "Info", "No entries passed the condition.")
            else:
                self.current_pulse_index = 0
                self.plot_pulse()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to parse condition: {e}")
    
    def next_pulse(self):
        if self.current_pulse_index < len(self.indices) - 1:
            self.current_pulse_index += 1
            self.plot_pulse()
        else:
            QMessageBox.information(self, "End", "Reached the end of pulses that passed the cut.")

    def prev_pulse(self):
        if self.current_pulse_index > 0:
            self.current_pulse_index -= 1
            self.plot_pulse()
        else:
            QMessageBox.information(self, "Start", "Already at the first pulse.")

    def plot_pulse(self):
        pulse_dataset_name = self.pulse_dataset_input.text().strip()  # Correct attribute name
        if not pulse_dataset_name:
            QMessageBox.warning(self, "Error", "Please enter the pulse samples name")
            return
        if not self.indices or self.current_pulse_index >= len(self.indices):
            QMessageBox.information(self, "End", "No more pulses or reached the end of pulses that passed the cut.")
            return

        index = self.indices[self.current_pulse_index]
        with h5py.File(self.hdf5_file_path, 'r') as hdf5_file:
            if pulse_dataset_name not in hdf5_file:
                QMessageBox.warning(self, "Error", f"Field {pulse_dataset_name} not found in the file.")
                return

            pulse_data = hdf5_file[pulse_dataset_name][index]
            self.hover_window.plot_pulse(pulse_data)
            self.hover_window.show()

    def handle_draw_scatter(self):
        try:
            self.select_data_get_selected_indices()
            if not self.indices:
                QMessageBox.information(self, "Info", "No entries passed the condition.")
            else:
                self.plot_scatter()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to parse condition: {e}")

    def plot_scatter(self):
        x_var = self.x_axis_combo_box.currentText()
        y_var = self.y_axis_combo_box.currentText()

        if not self.hdf5_file_path or not x_var or not y_var:
            QMessageBox.warning(self, "Error", "Please select a valid file and variables for both axes.")
            return
        
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        with h5py.File(self.hdf5_file_path, 'r') as hdf5_file:
            x_data = hdf5_file[x_var][self.indices]
            y_data = hdf5_file[y_var][self.indices]
            ax.scatter(x_data, y_data, s=INITIAL_MARKER_SIZE, picker=5)

        ax.set_xlabel(x_var)
        ax.set_ylabel(y_var)
        self.canvas.draw_idle()

        self.canvas.mpl_connect('pick_event', self.onpick)

    def onpick(self, event):
        if self.show_pulses_checkbox.isChecked() and event.artist:
            picked_index = event.ind[0]  # This is the index in the scatter plot
            if picked_index < len(self.indices):
                original_index = self.indices[picked_index]  # Map to the original dataset index
                with h5py.File(self.hdf5_file_path, 'r') as hdf5_file:
                    pulse_field = self.pulse_dataset_input.text().strip()
                    if pulse_field in hdf5_file:
                        pulse_data = hdf5_file[pulse_field][original_index]
                        self.hover_window.plot_pulse(pulse_data)
                        self.hover_window.show()
                    else:
                        QMessageBox.warning(self, "Data Error", f"The field {pulse_field} does not exist in the file.")
            else:
                QMessageBox.warning(self, "Data Error", "Picked index is out of the valid range.")

    def select_data_get_selected_indices(self, chunk_size=CHUNK_SIZE):
        number_of_conditions = self.conditions.count() - 1
        if number_of_conditions < 1:
            with h5py.File(self.hdf5_file_path, 'r') as hdf5_file:
                num_entries = len(hdf5_file[list(hdf5_file.keys())[0]])
                self.indices = list(range(num_entries))
            return

        # Build the full condition expression with proper replacements and parentheses
        condition_expressions = []
        for i in range(number_of_conditions):
            widget = self.conditions.itemWidget(self.conditions.item(i))
            if widget is not None:
                expr = widget.currentText().strip()
                # Replace logical operators with numexpr-friendly operators and ensure conditions are enclosed
                expr = expr.replace("||", "|").replace("&&", "&").replace("!", "~")
                expr = re.sub(r"(\w+)(==|!=|<=|>=|<|>)(\w+)", r"(\1\2\3)", expr)  # Ensure each comparison is enclosed
                condition_expressions.append(expr)

        full_condition = ' & '.join(f"({expr})" for expr in condition_expressions)  # Enclose each combined condition

        # Regex to extract variable names, avoiding mathematical functions and numbers
        regex_pattern = r'\b(?<!\.\w)[A-Za-z_][A-Za-z0-9_]*\b'
        # Known functions that should not be treated as variable names
        known_functions = {'abs', 'sqrt', 'sin', 'cos', 'tan', 'exp', 'log'}
        
        needed_vars = {match for match in re.findall(regex_pattern, full_condition) if match not in known_functions}

        # Initialize an empty list to collect all valid indices
        valid_indices = []

        try:
            with h5py.File(self.hdf5_file_path, 'r') as hdf5_file:
                # Prepare to load only the necessary variables
                data = {var: hdf5_file[var] for var in needed_vars if var in hdf5_file}
                
                # Determine the length of the data using one dataset (assuming all are of equal length)
                num_entries = len(data[list(needed_vars)[0]])

                # Process data in chunks
                for start in range(0, num_entries, chunk_size):
                    end = min(start + chunk_size, num_entries)
                    chunk_data = {var: data[var][start:end] for var in needed_vars}
                    
                    # Evaluate condition using numexpr on the chunk
                    mask = ne.evaluate(full_condition, local_dict=chunk_data)
                    
                    # Compute actual indices within the full dataset
                    chunk_indices = np.where(mask)[0] + start
                    valid_indices.extend(chunk_indices.tolist())

            self.indices = valid_indices
            print(f"Selected {len(self.indices)} entries")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to parse condition: {e}")
            self.indices = []

def main():
    app = QApplication(sys.argv)
    main_window = PulseAnalysisWindow()
    main_window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
