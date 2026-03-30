import unittest
from unittest.mock import patch
from io import StringIO
from io import BytesIO
import os
import sys
import importlib.util
import glob
from gradescope_utils.autograder_utils.decorators import weight
from gradescope_utils.autograder_utils.decorators import visibility
from gradescope_utils.autograder_utils.json_test_runner import JSONTestRunner
import ast
import tokenize
# from lab7_problem import Resistor
# from lab7_problem import Series
# from lab7_problem import Parallel

SUBMISSION_DIR = '/autograder/submission/'

SUBMISSION_DIR = '/autograder/submission/'

# Step 1: Locate the student's file
def find_student_file():
    python_files = [f for f in os.listdir(SUBMISSION_DIR) if f.endswith('.py')]
    if not python_files:
        raise FileNotFoundError("No Python files found in the submission directory.")
    if len(python_files) > 1:
        raise ValueError("Multiple Python files found. Ensure only the required file is submitted.")
    return python_files[0]

# Step 2: Dynamically import the student's file
student_file_name = find_student_file()
module_name = os.path.splitext(student_file_name)[0]  # Remove '.py' extension
module_path = os.path.join(SUBMISSION_DIR, student_file_name)

spec = importlib.util.spec_from_file_location(module_name, module_path)
student_module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = student_module
spec.loader.exec_module(student_module)

# Step 3: Import the required classes
try:
    Resistor = getattr(student_module, "Resistor")
    Series = getattr(student_module, "Series")
    Parallel = getattr(student_module, "Parallel")
except AttributeError as e:
    raise ImportError(f"Missing required class in the submission file: {e}")
    
class Lab07AutoGrader(unittest.TestCase):
    def setUp(self):
        #Part 2
        self.resistor = Resistor(100)
        self.resistorTwo = Resistor(1000)
        self.resistorThree = Resistor(10000)
        self.resistorFour = Resistor(100000)

        self.R1 = Resistor(10)
        self.R2 = Resistor(20)
        self.R3 = Resistor(30)
        self.R4 = Resistor(40)

        self.series1 = Series([self.R1, self.R2])
        self.parallel1 = Parallel([self.R1, self.R2])

        self.series2 = Series([self.R1, self.R2, self.R3])
        self.parallel2 = Parallel([self.R1, self.R2, self.R3])

        self.parallel3 = Parallel([self.R1, self.R2, self.R3, self.R4])
    
    #Part 2
    @weight(5) # split into 4 test cases worth 5 points each
    @visibility("visible")
    def test_multimeter_range_one(self):
        self.assertEqual(self.resistor.get_multimeter_range(), 200)

    @weight(5) # split into 4 test cases worth 5 points each
    @visibility("visible")
    def test_multimeter_range_two(self):
        self.assertEqual(self.resistorTwo.get_multimeter_range(), 2000)
    
    @weight(5) # split into 4 test cases worth 5 points each
    @visibility("hidden")
    def test_multimeter_range_three(self):
        self.assertEqual(self.resistorThree.get_multimeter_range(), 20000)
    
    @weight(5) # split into 4 test cases worth 5 points each
    @visibility("hidden")
    def test_multimeter_range_four(self):
        self.assertEqual(self.resistorFour.get_multimeter_range(), 200000)
    


    #Part 3
    @weight(5) 
    @visibility("visible")
    def test_set_resistance_one(self):
        self.resistor.set_resistance(200)
        self.assertEqual(self.resistor.get_resistance(), 200)

    @weight(5) 
    @visibility("visible")
    def test_set_resistance_two(self):
        self.resistor.set_resistance(1000)
        self.assertEqual(self.resistor.get_resistance(), 1000)

    @weight(5)
    @visibility("hidden")
    def test_color_code_resistance_one(self):
        self.resistor.set_resistance(None, ['brown', 'black', 'red'])
        self.assertEqual(self.resistor.get_resistance(), 1000)
    
    @weight(5)
    @visibility("hidden")
    def test_color_code_resistance_two(self):
        self.resistor.set_resistance(None, ['red', 'black', 'red'])
        self.assertEqual(self.resistor.get_resistance(), 2000)
    
    @weight(5)
    @visibility("hidden")
    def test_color_code_resistance_three(self):
        self.resistor.set_resistance(None, ['orange', 'brown', 'red'])
        self.assertEqual(self.resistor.get_resistance(), 3100)
    
    @weight(5)
    @visibility("hidden")
    def test_color_code_resistance_four(self):
        self.resistor.set_resistance(None, ['brown', 'yellow', 'blue'])
        self.assertEqual(self.resistor.get_resistance(), 14000000)
    

    #Part 4
    @weight(5)
    @visibility("visible")
    def test_series_one(self):
        total_resistance = 0
        for resistor in self.series1.resistors:
            total_resistance += resistor.get_resistance()
        
        self.assertEqual(self.series1.get_resistance(), total_resistance)
    
    @weight(5)
    @visibility("hidden")
    def test_series_two(self):
        total_resistance = 0
        for resistor in self.series2.resistors:
            total_resistance += resistor.get_resistance()
        
        self.assertEqual(self.series2.get_resistance(), total_resistance)
    
    @weight(5)
    @visibility("visible")
    def test_parellel_one(self):
        total_resistance = 0
        for resistor in self.parallel1.resistors:
            total_resistance += 1 / resistor.get_resistance()
        
        total_resistance = 1/total_resistance
        
        self.assertEqual(self.parallel1.get_resistance(), total_resistance)
    
    @weight(5)
    @visibility("hidden")
    def test_parellel_two(self):
        total_resistance = 0
        for resistor in self.parallel2.resistors:
            total_resistance += 1 / resistor.get_resistance()
        
        total_resistance = 1/total_resistance
        
        self.assertEqual(self.parallel2.get_resistance(), total_resistance)
    
    @weight(5)
    @visibility("hidden")
    def test_parellel_three(self):
        total_resistance = 0
        for resistor in self.parallel3.resistors:
            total_resistance += 1 / resistor.get_resistance()
        
        total_resistance = 1/total_resistance
        
        self.assertEqual(self.parallel3.get_resistance(), total_resistance)
        


    
    


if __name__ == '__main__':
    unittest.main()